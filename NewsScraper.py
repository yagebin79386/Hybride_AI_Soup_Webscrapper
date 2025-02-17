import os
import openai
import json
from urllib.parse import urlparse, urljoin
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver.v2 as uc
from bs4 import BeautifulSoup


class NewsScrapperGeneral:
    def __init__(self, base_urls):
        """
        Initialize hte NewsScraplerGeneral with a list of base URLs.
        Each base URL entry contains lts own paginated url listand cleaned HTML list.

        Parameters:
            base_url(list): A list of URLs to scrape.
        """
        self.webpages = [
            {"base_url": url, "paginated_url": [], "html": [], "extracted_news": []}
            for url in base_urls
        ]
        
    
    def find_all_pagination_urls(self):
        """
        Uses undetected_chromedriver to find all pagination URLs on a given webpage 
        and extract the pattern until no more pages are found.

        Parameters:
            start_url (str): The initial URL of the webpage.

        Returns:
            list: A list of all discovered pagination URLs.
        """
        options = uc.ChromeOptions()
        options.headless = True  # Change to True for faster execution
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        driver = uc.Chrome(options=options)

        for page in self.webpages:
            current_url = page["base_url"]
            page["paginated_url"].append(current_url)

            try:
                driver.get(current_url)
                wait = WebDriverWait(driver, 5)

                while True:
                    time.sleep(2)  # Allow minimal time for dynamic content to load

                    # First try JavaScript-based detection for the "Next" button
                    next_page_url = driver.execute_script("""
                        let next = document.querySelector('a.next.page-numbers');
                        return next ? next.href : null;
                    """)

                    # If JavaScript fails, fallback to explicit Selenium search
                    if not next_page_url:
                        try:
                            next_page_element = wait.until(
                                EC.presence_of_element_located(
                                    (By.XPATH, '//a[contains(text(), "Nächste") or contains(@aria-label, "Next") or contains(@rel, "next") or contains(text(), "Next") or contains(@class, "pagination-next")]')
                                )
                            )
                            next_page_url = next_page_element.get_attribute("href")
                        except:
                            pass  # No element found

                    # If no "Next" button found, try to find the next numbered page
                    if not next_page_url:
                        try:
                            # Get the currently active page number
                            active_page_element = driver.find_element(By.XPATH, '//span[contains(@class, "current")]')
                            current_page = int(active_page_element.text.strip())

                            # Find the next numbered page
                            next_page_element = driver.find_element(By.XPATH, f'//a[text()="{current_page + 1}"]')
                            next_page_url = next_page_element.get_attribute("href")
                        except:
                            pass  # No numbered pagination found either

                    # If next page URL is found, navigate to it
                    if next_page_url and next_page_url not in page["paginated_url"]:
                        print("Next page URL found:", next_page_url)
                        page["paginated_url"].append(next_page_url)
                        driver.get(next_page_url)
                    else:
                        print("No new next page found, stopping...")
                        break  # Stop when no new page is found

            except Exception as e:
                print(f"Error during pagination search: {e}")

        driver.quit()  # Close the driver only after the loop completes

        
    def get_and_clean_html(self):
        """
        Fetches raw HTML from URLs using undetected_chromedriver,
        removes redundant attributes and safely irrelevant elements 
        while keeping the general HTML structure.
        
        Returns:
            None (Stores minimized cleaned HTML in self.webpages)
        """
        options = uc.ChromeOptions()
        options.headless = True  # Run in headless mode
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = uc.Chrome(options=options)
        
        

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

                # Parse the HTML
                soup = BeautifulSoup(raw_html, "html.parser")

                # **Step 1: Remove Irrelevant Elements**
                for tag in soup([
                    "script", "style", "meta", "noscript", "iframe", "svg", "path", "link",
                    "header", "footer", "aside", "nav", "form", "button", "object",
                    "embed", "picture", "video", "audio", "source", "input",
                    "ins", "del", "noscript"
                ]):
                    tag.decompose()

                # **Step 2: Remove Empty & Decorative Elements**
                for tag in soup.find_all():
                    if not tag.get_text(strip=True):  # Remove empty elements
                        tag.decompose()

                # **Step 3: Remove Non-Informative Attributes**
                for tag in soup.find_all(True):
                    attrs_to_remove = ["class", "id", "role", "data-*", "aria-*", "onclick", "onload", "style"]
                    for attr in list(tag.attrs):
                        if any(re.match(pattern.replace("*", ".*"), attr) for pattern in attrs_to_remove):
                            del tag[attr]

                # **Step 4: Minimize Extra Whitespaces**
                cleaned_html = str(soup)
                cleaned_html = re.sub(r">\s+<", "><", cleaned_html)  # Remove spaces between tags
                cleaned_html = re.sub(r"\n+", "", cleaned_html)  # Remove new lines
                cleaned_html = re.sub(r"\s{2,}", " ", cleaned_html)  # Reduce multiple spaces

                # **Step 5: Store Minimized HTML**
                page["html"].append(cleaned_html)

        driver.quit()

    
    def extract_news_articles_with_chatgpt(self):
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        """
        Extracts title, publication date, author, and link of each news thumbnail embedded in the given HTML of a news board using OpenAI's API.
        Automatically detects and appends the base URL if necessary.
        
        Parameters:
        - html (str): The raw HTML of the news page.
        - page_url (str): The original URL of the webpage being scraped.

        Returns:
        - list: A list of dictionaries containing extracted news details.
        """
        # Identify base URL from <base> tag or derive from page_url
        for page in self.webpages:
            for html_content in page["html"]:
                if not isinstance(html_content, str):
                    print("Skipping Nnon-string content in HTML")
                    continue
                
                raw_html = html_content[:100000]
            
                # Extract base URL
                if '<base href="' in html_content:
                    start_idx = html_content.find('<base href="') + len('<base href="')
                    end_idx = html_content.find('"', start_idx)
                    base_url = html_content[start_idx:end_idx]
                else:
                    parsed_url = urlparse(page["base_url"])
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"  # Extract base URL from page URL


                prompt = f"""
                You are an AI that extracts structured data from raw HTML of a news portal. The HTML contains multiple news article elements.

                Your task is to identify each complete news article element and extract the following information for each article:

                - **Title**: the title of the news.
                - **Publication Date**: the date when the news was published (e.g., "Jan 24, 2025"). Use the text within the <time> element or any available date attribute.
                - **Author**: the name of the news’s author.
                - **Link**: the article’s link (either full or relative).

                Return the extracted data as a JSON array of objects in the following format:

                ```json
                [
                    {{"title": "Article Title", "publication_date": "Jan 24, 2025", "author": "Author Name", "link": "/news/article-123"}},
                    {{"title": "Another Article Title", "publication_date": "Jan 23, 2025", "author": "Another Author", "link": "https://example.com/full-article"}}
                ]
                ```

                If any field is missing for an article, set its value to null.

                Extract this information from the following HTML:

                ```html
                {raw_html}
                ```
                """

                try:
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)

                    response = client.chat.completions.create(
                        model="gpt-4-turbo",
                        messages=[{"role": "system", "content": prompt}],
                        temperature=0.2
                    )

                    extracted_info = json.loads(response.choices[0].message.content.strip())

                    # **Fix relative URLs by prepending the base URL**
                    for article in extracted_info:
                        if article["link"] and not article["link"].startswith("http"):
                            article["link"] = urljoin(base_url, article["link"])

                    page["extracted_news"] = extracted_info

                except json.JSONDecodeError as e:
                    print(f"JSON parsing error: {e}")
                except Exception as e:
                    print(f"Error processing content with ChatGPT: {e}")
        
    def flatten_news(self):
        """
        Ensure the extracted news data follows a uniform format and unfolds nested lists.

        Parameters:
            news_data(list): A potentially nested list of news articles.json

        Returns:
            list: A flattened and structured list of news articles.
        """
        flattened_list = []
        def extract_articles(item):
            """Recursively extract articles from nested structures."""
            if isinstance(item, list):
                for sub_item in item:
                    extract_articles(sub_item)
            elif isinstance(item, dict) and all(key in item for key in ["title", "publication_date", "author", "link"]):
                flattened_list.append(item)
        
            return flattened_list
        
        for page in self.webpages:
            for news in page["extracted_news"]:
                news = extract_articles(news)
    

if __name__ == "__main__":
    base_url = {Your_list_of_webURLs}
    scrapper = NewsScrapperGeneral(base_url)
    scrapper.find_all_pagination_urls()
    scrapper.get_and_clean_html()
    scrapper.extract_news_articles_with_chatgpt()
    scrapper.flatten_news()
    print(json.dumps(scrapper.webpages, indent=4))

    




