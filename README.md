# **Hybride_AI_Soup_Webscraper**

AI & Soup Hybrid Webscraper for News Extraction

## **Introduction**
The **Hybride_AI_Soup_Webscraper** is a cutting-edge tool designed to extract news articles from diversified news portal pages. The unique aspect of this tool lies in its hybrid approach, combining the **legacy CSS-selector method** with the powerful **text-processing capabilities of a Large Language Model (LLM)** to handle one of the biggest challenges in web scraping: **dynamic and varying HTML structures**.

## **Project Overview**
In this project, I have implemented a **dual-method web scraper**:
1. **BeautifulSoup Library**: Initially used to clean and reduce irrelevant HTML components, retaining only the necessary structural components of a page. This reduces the size and complexity of the HTML, making it easier for the next processing step.
2. **LLM Integration**: After cleaning the HTML, the reduced content is passed as tokens into the **OpenAI GPT-4 model**, which processes the content to extract structured news data, such as the article’s **title**, **publication date**, **author**, and **link**.

## **Why This Hybrid Model?**
Most traditional web scrapers struggle with dynamic content and constantly changing HTML structures across different news websites. The combination of **CSS selectors** and **LLM** overcomes this by:
- **Adapting to changing HTML structures**: By leveraging LLMs, the scraper can adjust to HTML changes automatically, extracting relevant data without needing frequent code updates.
- **Efficiently reducing HTML complexity**: BeautifulSoup is used to clean out unnecessary content before passing it to the LLM, which allows the model to focus only on the relevant parts of the page.

## **Key Features**
- **Hybrid Web Scraping**: Utilizes both traditional methods (BeautifulSoup) and modern AI models (GPT-4) to ensure the tool’s robustness across multiple websites.
- **Adaptability**: Can handle variations in HTML structure, including dynamic content, pagination, and content blocks that change with each page load. This tool can also be adapted with its get_and_clean_html() and LLM prompt in extract_news_articles_with_chatgpt to extract other contents or elements on html.
- **Efficient and Clean Data Extraction**: It automatically gains URL of all pages of the news portal and extract on each URL the structured data such as **titles**, **publication dates**, **author names**, and **links** for news articles.

## **How It Works**
1. **Find Pagination URLs**: Using **undetected_chromedriver**, the scraper identifies all pagination URLs on a given webpage, allowing it to navigate through multiple pages and scrape the entire set of articles.
2. **Clean HTML with BeautifulSoup**: The raw HTML is processed by BeautifulSoup to remove unnecessary elements like ads, scripts, and images, leaving only the core content.
3. **Extract News with LLM**: The cleaned HTML is then passed to the LLM (OpenAI GPT-4) to identify and extract the relevant news article data. The LLM is trained to detect the necessary fields regardless of slight variations in HTML structure.
4. **Handle Nested Data**: The extracted data is then flattened and structured for easier access and use.

## **Methods**
### 1. **`find_all_pagination_urls()`**
   - This method identifies all the pagination URLs on a given news webpage using **undetected_chromedriver** and dynamic content handling.
   - **Input**: List of base URLs.
   - **Output**: A list of all discovered pagination URLs.

### 2. **`get_and_clean_html()`**
   - Fetches the raw HTML content from a given URL and cleans it by removing irrelevant elements like ads, images, and scripts using **BeautifulSoup**.
   - **Input**: URL(s) of webpages to scrape.
   - **Output**: Cleaned HTML, preserving the structure and relevant sections (e.g., article bodies).

### 3. **`extract_news_articles_with_chatgpt()`**
   - Uses **OpenAI’s GPT-4 API** to parse cleaned HTML and extract relevant data such as article title, publication date, author, and link.
   - **Input**: Cleaned HTML content.
   - **Output**: A list of dictionaries containing structured news article data.

### 4. **`flatten_news()`**
   - Flattens any nested data into a uniform format, making it easier to work with the extracted data.
   - **Input**: Extracted news articles.
   - **Output**: Flattened and structured list of articles.

## **Special Features**
- **Handling Dynamic HTML Structures**: Traditional web scraping tools often struggle with websites that have frequently changing layouts or dynamically-loaded content. This hybrid approach of combining BeautifulSoup for cleaning and LLM for understanding the content allows the scraper to adapt to these changes without requiring constant updates to the scraping logic.
- **Integration with OpenAI API**: By using the **OpenAI GPT-4** model, the tool can intelligently parse complex HTML and automatically extract the most relevant data, making it suitable for scraping a wide range of news websites without manually coding the extraction rules.

## **Installation and Usage**
1. Install the required dependencies:
   ```bash
   pip install beautifulsoup4 undetected-chromedriver openai requests

2. Set OPENAI_API_KEY environment variable to enable interaction with the GPT-4 model:
- macOS or Linux:
  ```bash
   export OPENAI_API_KEY="your_api_key_here"
- Windows:
  ```bash
   setx OPENAI_API_KEY "your_api_key_here"

4. Use the scraper by providing a list of base URLs:
   ```python
   base_url = {List_base_URL}
   scrapper = NewsScraplerGeneral(base_url)
   scrapper.find_all_pagination_urls()
   scrapper.get_and_clean_html()
   scrapper.extract_news_articles_with_chatgpt()
   scrapper.flatten_news()
   print(json.dumps(scrapper.webpages, indent=4))

## Conclusion

This tool provides a robust, adaptable, and intelligent solution for scraping news articles from a variety of websites. By combining traditional web scraping techniques with modern AI capabilities, the Hybride_AI_Soup_Webscraper overcomes many of the limitations faced by conventional scrapers, particularly when dealing with dynamic or changing HTML structures.
