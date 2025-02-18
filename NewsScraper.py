import os
import openai
import json
from urllib.parse import urlparse, urljoin
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta
import sqlite3  # For database operations
from newspaper import Article  # Requires: pip install newspaper3k

class NewsScrapperGeneral:
    def __init__(self, base_urls):
        """
        Initialize the NewsScrapperGeneral with a list of base URLs.
        For each base URL, we maintain:
          - paginated_url: a list of discovered URLs (pages)
          - html: a dict mapping each paginated URL to its cleaned HTML
          - extracted_news: a dict mapping each paginated URL to the raw extracted text (markdown)
        """
        self.webpages = [
            {
                "base_url": url,
                "paginated_url": [],
                "html": {},           # {paginated_url: cleaned_html, ...}
                "extracted_news": {}  # {paginated_url: extracted_text, ...}
            }
            for url in base_urls
        ]

    def find_all_pagination_urls(self):
        """
        Extracts pagination URLs from different webpage structures.
        Stops after finding 10 additional pages per base URL (total 11 pages).
        """
        options = uc.ChromeOptions()
        options.headless = False  # Change to True for silent mode
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")

        driver = uc.Chrome(options=options)
        max_pages = 11  # base URL + 10 additional pages

        for page in self.webpages:
            current_url = page["base_url"]
            page["paginated_url"].append(current_url)
            try:
                driver.get(current_url)
                wait = WebDriverWait(driver, 5)
                while True:
                    if len(page["paginated_url"]) >= max_pages:
                        print("🚫 Reached the maximum page limit for", page["base_url"])
                        break
                    time.sleep(2)
                    next_page_url = None
                    try:
                        next_button = driver.find_element(By.XPATH, '//a[contains(@class, "Pagination-Link") and contains(@href, "page=")]')
                        next_page_url = next_button.get_attribute("href")
                        print("✅ Found 'Next' button:", next_page_url)
                    except:
                        print("❌ No explicit 'Next' button found.")
                    if not next_page_url:
                        try:
                            next_button = driver.find_element(By.XPATH, '//a[@rel="next"]')
                            next_page_url = next_button.get_attribute("href")
                        except:
                            print("❌ No `rel=next` button found.")
                    if next_page_url and not next_page_url.startswith("http"):
                        next_page_url = urljoin(current_url, next_page_url)
                    if next_page_url and next_page_url not in page["paginated_url"]:
                        print("✅ Next page URL found:", next_page_url)
                        page["paginated_url"].append(next_page_url)
                        driver.get(next_page_url)
                    else:
                        print("🚫 No new next page found, stopping pagination.")
                        break
            except Exception as e:
                print(f"🔥 Error during pagination search: {e}")
        driver.quit()

    def get_and_clean_html(self):
        """
        Fetches raw HTML from each paginated URL using undetected_chromedriver,
        cleans it, and stores the cleaned HTML in the 'html' dict keyed by the paginated URL.
        """
        options = uc.ChromeOptions()
        options.headless = True  
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = uc.Chrome(options=options)
        try:
            for page in self.webpages:
                if page['base_url'] not in page["paginated_url"]:
                    page["paginated_url"].append(page["base_url"])
                for single_url in page["paginated_url"]:
                    try:
                        driver.get(single_url)
                        raw_html = driver.page_source
                    except Exception as e:
                        print(f"Failed to fetch {single_url}: {e}")
                        continue
                    soup = BeautifulSoup(raw_html, "html.parser")
                    for tag in soup(["script", "style", "noscript", "iframe", "svg", "path", "object",
                                      "embed", "picture", "video", "audio", "source", "input",
                                      "ins", "del", "form", "button"]):
                        tag.decompose()
                    for tag in soup.find_all():
                        if not tag.get_text(strip=True):
                            tag.decompose()
                    for tag in soup.find_all(True):
                        attrs_to_remove = ["class", "id", "role", "data-*", "aria-*", "onclick", "onload", "style"]
                        for attr in list(tag.attrs):
                            if tag.name == "a" and attr == "href":
                                continue
                            if any(re.match(pattern.replace("*", ".*"), attr) for pattern in attrs_to_remove):
                                del tag[attr]
                    cleaned_html = str(soup)
                    cleaned_html = re.sub(r">\s+<", "><", cleaned_html)
                    cleaned_html = re.sub(r"\n+", "", cleaned_html)
                    cleaned_html = re.sub(r"\s{2,}", " ", cleaned_html)
                    page["html"][single_url] = cleaned_html
        finally:
            driver.quit()

    def extract_news_articles_with_chatgpt(self):
        """
        For each cleaned HTML (keyed by URL in the 'html' dict),
        uses the Corcel API to extract news article information.
        The extracted markdown is accumulated per URL and stored in the 'extracted_news' dict.
        """
        CORCEL_API_KEY = {CORCEL_API_KEY}
        for page in self.webpages:
            for url_key, html_content in page["html"].items():
                if not isinstance(html_content, str):
                    print("Skipping non-string content for URL:", url_key)
                    continue
                raw_html = html_content[:100000]
                parsed_url = urlparse(page["base_url"])
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
                prompt = f"""
                You are an AI that extracts structured data from raw HTML of a news portal.
                Extract the following details for each news article:
                - **Title**: the title of the article.
                - **Publication Date**: If no date is explicitly given, return null.
                - **Author**: the name(s) of the author(s).
                - **Link**: the article’s hyperlink (if relative, return as-is).
                Extract this from the following HTML:
                ```html
                {raw_html}
                ```
                """
                try:
                    api_url = "https://api.corcel.io/v1/chat/completions"
                    payload = {
                        "model": "gpt-4o",
                        "messages": [{"role": "system", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 10000,
                        "stream": True
                    }
                    headers = {
                        "Authorization": f"Bearer {CORCEL_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    response = requests.post(api_url, json=payload, headers=headers, stream=True)
                    extracted_text = ""
                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if line:
                                try:
                                    json_line = json.loads(line.decode("utf-8").replace("data: ", ""))
                                    if "choices" in json_line and json_line["choices"]:
                                        extracted_text += json_line["choices"][0]["delta"].get("content", "")
                                except json.JSONDecodeError:
                                    continue
                        print(f"Extracted text for {url_key}:\n{extracted_text}\n")
                    else:
                        print(f"API error for {url_key}: {response.status_code}, {response.text}")
                except Exception as e:
                    print(f"Error processing content with ChatGPT for {url_key}: {e}")
                page["extracted_news"][url_key] = extracted_text.strip()

    def flatten_news(self):
        """
        Processes the extracted markdown text for each URL in 'extracted_news'
        and converts it into a list of article dictionaries.
        The final structure for each page's extracted_news is a dict mapping each URL
        to a list of article dicts.
        Articles with a missing or empty Link are dropped, and relative links are converted to absolute.
        """
        def convert_markdown_to_articles(markdown_text):
            blocks = re.split(r"\n(?=\d+\.)", markdown_text.strip())
            articles = []
            for block in blocks:
                title_match = re.search(r"\d+\.\s*\*\*Title\*\*:\s*(.*)", block)
                pub_date_match = re.search(r"-\s*\*\*Publication Date\*\*:\s*(.*)", block)
                author_match = re.search(r"-\s*\*\*Author\*\*:\s*(.*)", block)
                link_match = re.search(r"-\s*\*\*Link\*\*:\s*(.*)", block)
                if title_match and link_match:
                    article = {}
                    article["Title"] = title_match.group(1).strip()
                    article["Publication Date"] = pub_date_match.group(1).strip() if pub_date_match else None
                    article["Author"] = author_match.group(1).strip() if author_match else None
                    article["Link"] = link_match.group(1).strip()
                    if article["Link"]:
                        articles.append(article)
            return articles

        for page in self.webpages:
            new_extracted = {}
            for url_key, news_data in page.get("extracted_news", {}).items():
                if not news_data:
                    continue
                news_data = news_data.strip()
                if news_data.startswith("```json"):
                    news_data = news_data[len("```json"):].strip()
                    if news_data.endswith("```"):
                        news_data = news_data[:-3].strip()
                if not news_data.startswith("[") and not news_data.startswith("{"):
                    articles = convert_markdown_to_articles(news_data)
                else:
                    try:
                        articles = json.loads(news_data)
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Error decoding JSON from extracted_news for {url_key}: {e}")
                        print(f"Problematic content:\n{news_data}")
                        continue
                base_url = page.get("base_url", "")
                valid_articles = []
                for article in articles:
                    link = article.get("Link", "").strip()
                    if not link:
                        continue
                    if not link.startswith("http"):
                        article["Link"] = urljoin(base_url, link)
                    valid_articles.append(article)
                new_extracted[url_key] = valid_articles
                print(f"✅ Successfully flattened {len(valid_articles)} articles for {url_key}")
            page["extracted_news"] = new_extracted

    def save_to_db(self, db_path="news.db"):
        """
        Saves the extracted news data into a SQLite database table called 'news'.
        The table has the following schema:
            - Title (TEXT PRIMARY KEY)
            - Author (TEXT, nullable)
            - Publication_Date (TEXT, nullable)
            - Link (TEXT NOT NULL)
            - base_url (TEXT NOT NULL)
            - paginated_url (TEXT NOT NULL)
            - created_time (TEXT NOT NULL)
            - article (TEXT, nullable)
        Data is saved for each article from each paginated URL.
        """
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS news (
            Title TEXT PRIMARY KEY,
            Author TEXT,
            Publication_Date TEXT,
            Link TEXT NOT NULL,
            base_url TEXT NOT NULL,
            paginated_url TEXT NOT NULL,
            created_time TEXT NOT NULL,
            article TEXT
        );
        """
        c.execute(create_table_sql)
        conn.commit()
        created_time = datetime.now().isoformat()
        for page in self.webpages:
            base_url = page.get("base_url")
            for paginated_url, articles in page.get("extracted_news", {}).items():
                for article in articles:
                    title = article.get("Title")
                    author = article.get("Author")
                    pub_date = article.get("Publication Date")
                    link = article.get("Link")
                    if not (title and link and base_url and paginated_url):
                        continue
                    insert_sql = """
                    INSERT OR IGNORE INTO news (Title, Author, Publication_Date, Link, base_url, paginated_url, created_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                    c.execute(insert_sql, (title, author, pub_date, link, base_url, paginated_url, created_time))
        conn.commit()
        conn.close()
        print("✅ Data saved to SQLite database:", db_path)

    def update_article_details(self, db_path="news.db"):
        """
        For each record in the 'news' table where the article text, Author, or Publication_Date is NULL,
        scrape the main article text from the Link using Newspaper3k, and update the record.
        The scraped main text is saved under the 'article' column, and if Author or Publication_Date
        are missing, they are updated as well.
        """
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(news);")
        columns = [col[1] for col in c.fetchall()]
        if "article" not in columns:
            try:
                c.execute("ALTER TABLE news ADD COLUMN article TEXT;")
            except Exception as e:
                print("Error adding column 'article':", e)
        conn.commit()
        c.execute("SELECT Title, Link, Author, Publication_Date FROM news WHERE article IS NULL OR Author IS NULL OR Publication_Date IS NULL;")
        rows = c.fetchall()
        for row in rows:
            title, link, db_author, db_pub_date = row
            try:
                art = Article(link)
                art.download()
                art.parse()
                main_text = art.text
                scraped_author = ", ".join(art.authors) if art.authors else db_author
                scraped_pub_date = art.publish_date.isoformat() if art.publish_date else db_pub_date
                update_sql = """
                UPDATE news 
                SET article = ?, Author = COALESCE(?, Author),
                    Publication_Date = COALESCE(?, Publication_Date)
                WHERE Title = ?;
                """
                c.execute(update_sql, (main_text, scraped_author, scraped_pub_date, title))
                print(f"Updated details for article: {title}")
            except Exception as e:
                print(f"Error scraping article at {link}: {e}")
        conn.commit()
        conn.close()
        print("✅ Article details updated in the database.")


if __name__ == "__main__":
    base_url = {baseURL_list}
    scrapper = NewsScrapperGeneral(base_url)
    scrapper.find_all_pagination_urls()
    scrapper.get_and_clean_html()
    scrapper.extract_news_articles_with_chatgpt()
    scrapper.flatten_news()
    scrapper.save_to_db()
    scrapper.update_article_details()

