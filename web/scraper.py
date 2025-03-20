import requests
from bs4 import BeautifulSoup
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from newspaper import Article
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.parse import urljoin
import traceback
import json
import re

logger = logging.getLogger(__name__)

class WebScraper:
    """Base web scraping class with common utilities"""

    def __init__(self, use_selenium: bool = False, headless: bool = True):
        """
        Initialize the web scraper

        Args:
            use_selenium: Whether to use Selenium for JavaScript-heavy websites
            headless: Whether to run browser in headless mode
        """
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.use_selenium = use_selenium
        self.driver = None

        if use_selenium:
            try:
                self._setup_selenium(headless)
            except Exception as e:
                logger.error(f"Failed to initialize Selenium: {str(e)}")
                logger.error(traceback.format_exc())
                # Fallback to non-Selenium mode
                self.use_selenium = False

    def _setup_selenium(self, headless: bool = True):
        """Set up Selenium WebDriver with improved error handling"""
        options = Options()
        if headless:
            options.add_argument("--headless=new")  # Updated headless argument for newer Chrome versions

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument(f"user-agent={self.headers['User-Agent']}")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        capabilities = DesiredCapabilities.CHROME
        capabilities["goog:loggingPrefs"] = {"performance": "ALL"}

        try:
            # Try to use ChromeDriverManager for automatic driver management
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("Selenium WebDriver initialized successfully.")
        except Exception as e:
            # Fallback to using a local ChromeDriver if available
            logger.warning(f"ChromeDriverManager failed: {e}, trying local ChromeDriver")
            try:
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("Selenium WebDriver initialized with local ChromeDriver.")
            except Exception as e2:
                logger.error(f"Failed to initialize WebDriver: {e2}")
                raise

    def _request_with_retry(self, url: str, max_retries: int = 3, wait_time: int = 2) -> Optional[requests.Response]:
        """Improved request retry mechanism with better anti-detection techniques"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        ]
        
        headers = self.headers.copy()
        
        for attempt in range(max_retries):
            try:
                # Rotate user agents
                headers['User-Agent'] = random.choice(user_agents)
                
                # Add referrer to look more like a browser
                headers['Referer'] = 'https://www.google.com/'
                
                # Add a random delay between requests
                time.sleep(random.uniform(2, 5))
                
                logger.info(f"Attempting request to {url} (Try {attempt + 1}/{max_retries})")
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Too many requests
                    wait_time = wait_time * (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                    logger.warning(f"Rate limited. Waiting {wait_time:.2f} seconds before retry.")
                    time.sleep(wait_time)
                elif response.status_code == 403:  # Forbidden
                    logger.warning(f"Access forbidden (403). Site may be blocking scrapers.")
                    
                    # Try with a different approach if available
                    if not self.use_selenium:  # If not already using Selenium, try to use it temporarily
                        logger.info("Attempting to use Selenium for 403 response")
                        try:
                            if not self.driver:
                                self._setup_selenium(True)
                                
                            self.driver.get(url)
                            time.sleep(random.uniform(3, 7))  # Wait longer for JS to load
                            return type('obj', (object,), {
                                'status_code': 200,
                                'text': self.driver.page_source
                            })
                        except Exception as selenium_error:
                            logger.error(f"Selenium fallback failed: {selenium_error}")
                    
                    # If we've tried all approaches, give up on this URL
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to access {url} after {max_retries} attempts (403 Forbidden)")
                        return None
                        
                    # Otherwise, wait longer before retry
                    wait_time = wait_time * (2 ** attempt) + random.uniform(5, 10)
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Request failed with status code {response.status_code}")
                    time.sleep(wait_time)
            except requests.exceptions.Timeout:
                logger.warning(f"Request timed out. Retrying in {wait_time} seconds.")
                time.sleep(wait_time)
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error. Retrying in {wait_time} seconds.")
                time.sleep(wait_time)
            except requests.RequestException as e:
                logger.error(f"Request error: {e}")
                time.sleep(wait_time)

        logger.error(f"Failed to retrieve {url} after {max_retries} attempts")
        return None

    def get_page_content(self, url: str) -> Tuple[Optional[str], Optional[BeautifulSoup]]:
        """
        Retrieve content from a URL using either requests or Selenium

        Args:
            url: The URL to scrape

        Returns:
            Tuple of (raw_html, BeautifulSoup object) or (None, None) if failed
        """
        if not url or not url.startswith('http'):
            logger.warning(f"Invalid URL: {url}")
            return None, None

        logger.info(f"Fetching page content: {url}")

        if self.use_selenium and self.driver:
            try:
                self.driver.get(url)
                # Random delay to avoid detection
                time.sleep(random.uniform(2, 5))

                try:
                    # Wait for the body element to be present
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    # Scroll down to load lazy content
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(1)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Wait or scroll error: {e}, continuing anyway")

                raw_html = self.driver.page_source
                soup = BeautifulSoup(raw_html, 'html.parser')
                return raw_html, soup
            except Exception as e:
                logger.error(f"Selenium error: {e}")
                # Try to reset the driver if it fails
                self._reset_selenium_driver()
                return None, None
        else:
            response = self._request_with_retry(url)
            if response:
                try:
                    raw_html = response.text
                    soup = BeautifulSoup(raw_html, 'html.parser')
                    return raw_html, soup
                except Exception as e:
                    logger.error(f"Error parsing HTML: {e}")
                    return None, None
            
            logger.error(f"Failed to retrieve page content for {url}")
            return None, None

    def _reset_selenium_driver(self):
        """Reset the Selenium driver if it encounters issues"""
        logger.info("Attempting to reset Selenium driver")
        self.close()
        try:
            headless = True  # Assume we want headless mode during reset
            self._setup_selenium(headless)
            logger.info("Selenium driver reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset Selenium driver: {e}")
            self.use_selenium = False  # Fallback to non-Selenium mode

    def extract_main_content(self, url: str) -> Dict[str, Any]:
        """
        Extract main content using newspaper3k with improved error handling

        Args:
            url: The URL to extract content from

        Returns:
            Dictionary with extracted content
        """
        logger.info(f"Extracting main content from: {url}")

        try:
            article = Article(url)
            article.download()
            
            # Check download state
            download_attempts = 0
            while article.download_state != 2 and download_attempts < 3:
                logger.warning(f"Article download state {article.download_state}, retrying...")
                time.sleep(2)
                article.download()
                download_attempts += 1
            
            if article.download_state != 2:
                logger.error(f"Failed to download article: {url}")
                
                # Try to get content directly if available
                raw_html, soup = self.get_page_content(url)
                if soup:
                    # Basic extraction if newspaper3k fails
                    title = soup.find('title').text if soup.find('title') else "Unknown title"
                    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
                    text = main_content.get_text(separator=' ', strip=True) if main_content else ""
                    
                    if not text and soup:
                        # If no main content found, get text from body
                        text = soup.body.get_text(separator=' ', strip=True) if soup.body else ""
                    
                    logger.info(f"Basic content extraction: Found title and {len(text)} characters of text")
                    
                    return {
                        'title': title,
                        'text': text[:5000],  # Limit text length
                        'summary': "Summary not available",
                        'keywords': [],
                        'publish_date': None,
                        'authors': [],
                        'url': url,
                        'extraction_method': 'fallback'
                    }
                logger.error(f"No content found in extracted data for URL: {url}")
                return {'error': 'Failed to download article', 'url': url, 'text': ''}

            article.parse()
            
            # Run NLP operations with improved error handling
            summary = "Summary not available"
            keywords = []
            
            try:
                # Disable NLP operations that cause numpy errors
                # article.nlp()
                # summary = article.summary
                # keywords = article.keywords
                
                # Create a simple summary without NLP
                text = article.text
                summary = text[:200] + "..." if len(text) > 200 else text
                
                # Extract basic keywords from title and text
                if article.title:
                    potential_keywords = re.findall(r'\b\w{4,}\b', article.title.lower())
                    keywords = list(set(potential_keywords))[:10]  # Take up to 10 unique words
                
            except Exception as nlp_error:
                logger.warning(f"NLP processing failed: {nlp_error}")

            return {
                'title': article.title or "Unknown title",
                'text': article.text,
                'summary': summary,
                'keywords': keywords,
                'publish_date': article.publish_date.isoformat() if article.publish_date else None,
                'authors': article.authors or [],
                'url': url,
                'extraction_method': 'newspaper3k'
            }
        except Exception as e:
            logger.error(f"Error extracting content with newspaper3k: {e}")
            logger.error(traceback.format_exc())
            return {'error': str(e), 'url': url, 'text': ''}
            
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract all links from a BeautifulSoup object with improved filtering

        Args:
            soup: BeautifulSoup object
            base_url: Base URL to resolve relative links

        Returns:
            List of extracted links
        """
        if not soup:
            logger.warning("Cannot extract links from None soup object")
            return []
            
        logger.info(f"Extracting links from base URL: {base_url}")

        links = []
        try:
            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href'].strip()
                
                # Skip empty links, javascript links, and anchor links
                if not link or link.startswith('javascript:') or link == '#':
                    continue
                    
                # Convert to absolute URL
                absolute_link = urljoin(base_url, link)
                
                # Skip mailto and tel links
                if absolute_link.startswith(('mailto:', 'tel:')):
                    continue
                    
                # Filter out non-http links
                if absolute_link.startswith(('http://', 'https://')):
                    links.append(absolute_link)
            
            # Remove duplicates while preserving order
            unique_links = []
            seen = set()
            for link in links:
                if link not in seen:
                    seen.add(link)
                    unique_links.append(link)
            
            logger.debug(f"Extracted {len(unique_links)} unique links from page.")
            return unique_links
        except Exception as e:
            logger.error(f"Error extracting links: {e}")
            return []

    def wait_for_element(self, selector: str, timeout: int = 10):
        """
        Wait for an element to be present in the page (Selenium only)

        Args:
            selector: CSS selector
            timeout: Maximum time to wait in seconds
        """
        if not self.use_selenium or not self.driver:
            logger.warning("This method can only be used with Selenium")
            return None

        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element
        except Exception as e:
            logger.error(f"Element not found: {selector} - {e}")
            return None

    def close(self):
        """Close the Selenium WebDriver if it's open"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Closed Selenium WebDriver.")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None

    def __del__(self):
        """Ensure the driver is closed when the object is deleted"""
        self.close()
        
    def _fix_json_escape_chars(self, json_str):
        """
        Fix common JSON escape character issues
        
        Args:
            json_str: JSON string with potential escape character issues
            
        Returns:
            Fixed JSON string
        """
        try:
            # Try to parse as is
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}. Attempting to fix...")
            
            # Remove code blocks if present
            json_str = re.sub(r'```json\s*', '', json_str)
            json_str = re.sub(r'\s*```', '', json_str)
            
            # Fix common escape issues
            # Replace invalid \escapes with proper ones
            json_str = re.sub(r'\\([^"\\/bfnrtu])', r'\\\\\1', json_str)
            
            # Try with eval (safer than eval in this context since we know it's JSON)
            try:
                # Handle cases where the JSON string is malformed in a way that json.loads can't handle
                import ast
                # First replace double quotes with single quotes inside strings
                # This can help with nested quote issues
                json_str = re.sub(r'(?<!\\)"([^"]*)":', r"'\1':", json_str)
                
                # Parse string to literal Python object (safer than eval)
                result = ast.literal_eval(json_str)
                return result
            except (SyntaxError, ValueError) as e:
                logger.error(f"Failed to fix JSON with ast.literal_eval: {e}")
                
                # Last resort: manual regex-based extraction
                try:
                    # Extract statement/confidence pairs
                    statements = re.findall(r'"statement":\s*"([^"]+)"', json_str)
                    confidences = re.findall(r'"confidence":\s*([\d.]+)', json_str)
                    rationales = re.findall(r'"rationale":\s*"([^"]+)"', json_str)
                    
                    # Create a list of dictionaries
                    result = []
                    for i in range(min(len(statements), len(confidences), len(rationales))):
                        result.append({
                            "statement": statements[i],
                            "confidence": float(confidences[i]),
                            "rationale": rationales[i]
                        })
                    
                    if result:
                        logger.info(f"Successfully extracted {len(result)} items from malformed JSON using regex")
                        return result
                    else:
                        logger.error("Failed to extract content using regex")
                        return []
                except Exception as regex_error:
                    logger.error(f"Failed to extract JSON content with regex: {regex_error}")
                    return []
                    
    def scrape(self, url: str, parse_json: bool = False) -> Dict[str, Any]:
        """
        Main method to scrape a URL and extract content and/or JSON data
        
        Args:
            url: The URL to scrape
            parse_json: Whether to attempt to parse the response as JSON
            
        Returns:
            Dictionary with scraped content or JSON data
        """
        logger.info(f"Scraping URL: {url}")
        
        if not url or url == "Unknown URL":
            logger.error(f"Invalid URL provided: {url}")
            return {
                'success': False,
                'error': 'Invalid URL',
                'url': url,
                'content': None
            }
            
        try:
            if parse_json:
                # Try to get JSON directly
                response = self._request_with_retry(url)
                if response:
                    try:
                        # Use the improved JSON parsing method
                        json_data = self._fix_json_escape_chars(response.text)
                        
                        if json_data:
                            return {
                                'success': True,
                                'url': url,
                                'content': json_data,
                                'content_type': 'json'
                            }
                        else:
                            logger.warning("JSON parsing failed, falling back to HTML parsing")
                    except Exception as json_error:
                        logger.error(f"JSON processing error: {json_error}")
                        logger.warning("Falling back to HTML parsing")
                
            # Get page content (either as fallback for JSON or as primary method)
            raw_html, soup = self.get_page_content(url)
            
            if not soup:
                logger.warning(f"Failed to get soup object for {url}")
                return {
                    'success': False,
                    'error': 'Failed to retrieve content',
                    'url': url,
                    'content': None
                }
                
            # Extract the main content
            try:
                content = self.extract_main_content(url)
            except Exception as content_error:
                logger.error(f"Error extracting main content: {content_error}")
                # Create a minimal content dictionary if extraction fails
                content = {
                    'title': soup.find('title').text if soup.find('title') else "Unknown title",
                    'text': soup.get_text()[:5000] if soup else "No content extracted",
                    'extraction_method': 'fallback_minimal'
                }
            
            # Extract links for potential future use
            links = self.extract_links(soup, url)
            
            return {
                'success': True,
                'url': url,
                'content': content,
                'links': links[:100],  # Limit to 100 links
                'raw_html': raw_html[:10000] if raw_html else None,  # Store a sample of raw HTML
                'content_type': 'html'
            }
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'url': url,
                'content': None
            }