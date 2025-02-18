import json
import sqlite3
import requests
from pydantic import BaseModel, Field
from typing import List
from urllib.parse import urljoin
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# Define the Pydantic model for extraction response
class ArticleExtractionResponse(BaseModel):
    keywords: List[str] = Field(..., description="Keywords extracted from the article.")
    main_category: str = Field(..., description="The main category of the article.")
    subcategories: List[str] = Field(..., description="A list of subcategories the article belongs to.")
    summary: str = Field(..., description="A brief summary of the article in a personal blogger's style.")

class ArticleExtractor:
    def __init__(self, db_path: str, corcel_api_key: str):
        """
        Initialize with the path to the SQLite database and the Corcel API key.
        """
        self.db_path = db_path
        self.corcel_api_key = corcel_api_key
        self.api_url = "https://api.corcel.io/v1/chat/completions"

        # ✅ Improved system prompt for strict JSON format
        self.system_prompt = """
            You are an AI assistant for article classification and extraction. Your task is to analyze an article and extract structured information, ensuring that the extracted data **strictly** follows the provided JSON schema. 

            📌 **Guidelines:**
            - **Keywords:** Extract relevant terms from the article.
            - **Main Category:** Select **ONLY** from the following categories:
            1. "New Smart Home Devices"
            2. "Smart Home Protocols and Standards"
            3. "Smart Device Installation and Setup"
            4. "Home Automation and Ecosystem Integration"
            5. "Energy Efficiency and Sustainability"
            6. "IoT Security and Privacy"
            7. "Emerging Technologies and Trends"
            8. "Troubleshooting and Maintenance"
            9. "Lifestyle Applications of Smart Homes"
            10. "Developer and Industry News"
            - **Subcategories:** Select relevant subcategories from the predefined list.
            - **Summary:** Write a personal-blogger-style summary that explains the **main idea** and **significance** of the article in an engaging way.
            
            ❌ **Strict Rules:**
            - The `main_category` **must be one of the provided categories**.
            - If an article seems to belong to a broader topic like "Technology," **map it to the closest relevant category** from the list above.
            - If the main category **does not match any of the predefined categories**, choose `"Emerging Technologies and Trends"` as a fallback.
        """

        self.response_format = {
            "name": "article_extraction",
            "schema": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "description": "Keywords extracted from the article.",
                        "items": {"type": "string"}
                    },
                    "main_category": {
                        "type": "string",
                        "description": "The main category of the article.",
                        "enum": [
                            "New Smart Home Devices",
                            "Smart Home Protocols and Standards",
                            "Smart Device Installation and Setup",
                            "Home Automation and Ecosystem Integration",
                            "Energy Efficiency and Sustainability",
                            "IoT Security and Privacy",
                            "Emerging Technologies and Trends",
                            "Troubleshooting and Maintenance",
                            "Lifestyle Applications of Smart Homes",
                            "Developer and Industry News"
                        ]
                    },
                    "subcategories": {
                        "type": "array",
                        "description": "A list of subcategories.",
                        "items": {"type": "string"}
                    },
                    "summary": {
                        "type": "string",
                        "description": "A concise, engaging summary in a personal blogger's style."
                    }
                },
                "required": ["keywords", "main_category", "subcategories", "summary"],
                "additionalProperties": False
            }
        }

        # Connect to the SQLite database.
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_columns_exist()

    def _ensure_columns_exist(self):
        """Ensure required columns exist in the database."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(news)")
        columns = [row["name"] for row in cursor.fetchall()]

        # Add missing columns
        for col in ["keywords", "main_category", "subcategories", "summary"]:
            if col not in columns:
                cursor.execute(f"ALTER TABLE news ADD COLUMN {col} TEXT")
        self.conn.commit()

    def _call_llm(self, article_text: str) -> ArticleExtractionResponse:
        """
        Call the Corcel API (using streaming) with the GPT-4o model and return the parsed extraction response.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": article_text},
        ]
        response_format_payload = {"type": "json_schema", "json_schema": self.response_format}
        payload = {
            "model": "gpt-4o",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 10000,
            "stream": True,
            "response_format": response_format_payload
        }
        headers = {
            "Authorization": f"Bearer {self.corcel_api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(self.api_url, json=payload, headers=headers, stream=True)

        extracted_text = ""
        accumulated_chunks = []

        if response.status_code == 200:
            # Process each streamed line
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8").strip()
                    
                    # Ignore stream control messages like "[DONE]"
                    if decoded_line == "data: [DONE]":
                        break
                    
                    # Remove the "data: " prefix if present
                    if decoded_line.startswith("data: "):
                        decoded_line = decoded_line[len("data: "):]

                    try:
                        json_line = json.loads(decoded_line)

                        # Extract delta content
                        if "choices" in json_line and json_line["choices"]:
                            delta = json_line["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            # Accumulate JSON chunks
                            accumulated_chunks.append(content)

                    except json.JSONDecodeError as e:
                        print("⚠ JSON decode error:", e, "for line:", decoded_line)
                        continue

        else:
            raise Exception(f"🔥 API error: {response.status_code}, {response.text}")

        # Join accumulated JSON chunks to form a complete JSON string
        extracted_text = "".join(accumulated_chunks).strip()

        # Remove markdown code fences if present
        if extracted_text.startswith("```"):
            lines = extracted_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            extracted_text = "\n".join(lines).strip()

        # Debugging output (print extracted text)
        print("📝 Extracted JSON Text:", extracted_text)

        # Try parsing the full JSON at once
        try:
            parsed_response = json.loads(extracted_text)
            extraction = ArticleExtractionResponse(**parsed_response)
            return extraction
        except Exception as e:
            raise Exception(f"⚠ Failed to parse LLM response: {str(e)}. Extracted text: {extracted_text}")

    def process_articles(self):
        """
        Extract information from articles and update the database.
        """
        articles = self.load_articles()
        cursor = self.conn.cursor()

        for row in articles:
            article_title = row["Title"]
            article_text = row["article"]

            try:
                extraction = self._call_llm(article_text)
                
                cursor.execute(
                    """
                    UPDATE news
                    SET keywords = ?, main_category = ?, subcategories = ?, summary = ?
                    WHERE Title = ?
                    """,
                    (json.dumps(extraction.keywords), extraction.main_category, json.dumps(extraction.subcategories), extraction.summary, article_title)
                )
                self.conn.commit()
                print(f"✅ Processed article: {article_title}")
            except Exception as e:
                print(f"❌ Error processing '{article_title}': {e}")

    def load_articles(self):
        """Load articles missing extracted data."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT Title, article FROM news 
            WHERE summary IS NULL OR keywords IS NULL OR main_category IS NULL OR subcategories IS NULL
        """)
        return cursor.fetchall()

    def close(self):
        """Close the database connection."""
        self.conn.close()

# --- Example Usage ---
if __name__ == "__main__":
    DB_PATH = "news.db"
    CORCEL_API_KEY = "fd0e2098-520e-476d-b62e-f14bdeb6fd5d"

    extractor = ArticleExtractor(db_path=DB_PATH, corcel_api_key=CORCEL_API_KEY)
    try:
        extractor.process_articles()
    finally:
        extractor.close()
