"""
News Scraper for The Second Mind project.
This module provides functions to scrape tech news from various sources.
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import logging
from datetime import datetime, timedelta
import newspaper
from newspaper import Article, Source
from urllib.parse import urlparse, urljoin

# Configure logging
logger = logging.getLogger(__name__)

class NewsScraper:
    """Scraper for obtaining tech news from various sources."""
    
    def __init__(self, rate_limit=1):
        """
        Initialize the news scraper.
        
        Args:
            rate_limit (float): Minimum time between requests in seconds
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        # List of tech news sources
        self.tech_news_sources = {
            "techcrunch": "https://techcrunch.com/",
            "wired": "https://www.wired.com/",
            "ars_technica": "https://arstechnica.com/",
            "the_verge": "https://www.theverge.com/",
            "engadget": "https://www.engadget.com/",
            "venturebeat": "https://venturebeat.com/",
            "zdnet": "https://www.zdnet.com/",
            "mit_tech_review": "https://www.technologyreview.com/",
            "cnet": "https://www.cnet.com/"
        }
    
    def _respect_rate_limit(self):
        """Ensure we don't exceed the rate limit"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit:
            time.sleep(self.rate_limit - time_since_last_request)
        
        self.last_request_time = time.time()
    
    def search_news_by_keyword(self, query, max_results=10, days=7):
        """
        Search tech news for the specified query across multiple sources.
        
        Args:
            query (str): The search query
            max_results (int): Maximum number of results to return
            days (int): Look for news within this many past days
            
        Returns:
            list: List of news article dictionaries
        """
        all_results = []
        
        # Search across all sources
        for source_name, source_url in self.tech_news_sources.items():
            try:
                source_results = self._search_source(source_url, query, max_results, days)
                all_results.extend(source_results)
                logger.info(f"Found {len(source_results)} articles from {source_name}")
                
                # Stop if we have enough results
                if len(all_results) >= max_results:
                    break
            except Exception as e:
                logger.error(f"Error searching {source_name}: {e}")
        
        # Sort by date (most recent first) and limit results
        all_results.sort(key=lambda x: x.get('date', ''), reverse=True)
        return all_results[:max_results]
    
    def _search_source(self, source_url, query, max_results=10, days=7):
        """
        Search a specific news source for articles matching the query.
        
        Args:
            source_url (str): Base URL of the news source
            query (str): The search query
            max_results (int): Maximum number of results to return
            days (int): Look for news within this many past days
            
        Returns:
            list: List of news article dictionaries from this source
        """
        self._respect_rate_limit()
        
        # Parse the domain for source identification
        domain = urlparse(source_url).netloc
        source_name = domain.replace('www.', '').split('.')[0]
        
        # Build newspaper Source object
        source = newspaper.build(source_url, memoize_articles=False, language='en')
        
        # Filter for recent articles containing the query
        matching_articles = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get article URLs from the source
        for article_url in source.article_urls():
            if len(matching_articles) >= max_results:
                break
                
            try:
                # Create and parse article
                article = Article(article_url, language='en')
                article.download()
                article.parse()
                article.nlp()  # This extracts keywords, summary, etc.
                
                # Check if article has a valid date and is recent enough
                if article.publish_date and article.publish_date >= cutoff_date:
                    # Check if query appears in title, text, or keywords
                    if (query.lower() in article.title.lower() or 
                        query.lower() in article.text.lower() or
                        any(query.lower() in kw.lower() for kw in article.keywords)):
                        
                        # Extract relevant information
                        article_info = {
                            "title": article.title,
                            "url": article_url,
                            "text": article.text[:1000] + ("..." if len(article.text) > 1000 else ""),
                            "summary": article.summary,
                            "keywords": article.keywords,
                            "date": article.publish_date.isoformat() if article.publish_date else "",
                            "authors": article.authors,
                            "source": source_name,
                            "domain": domain
                        }
                        
                        matching_articles.append(article_info)
                        logger.debug(f"Found matching article: {article.title}")
            
            except Exception as e:
                logger.debug(f"Error processing article {article_url}: {e}")
                continue
        
        return matching_articles
    
    def get_trending_tech_news(self, max_results=10, days=3):
        """
        Get trending tech news from multiple sources.
        
        Args:
            max_results (int): Maximum number of results to return
            days (int): Look for news within this many past days
            
        Returns:
            list: List of trending news article dictionaries
        """
        all_trending = []
        
        # Get trending news from each source
        for source_name, source_url in self.tech_news_sources.items():
            try:
                source_trending = self._get_trending_from_source(source_url, max_results // len(self.tech_news_sources) + 1, days)
                all_trending.extend(source_trending)
                logger.info(f"Found {len(source_trending)} trending articles from {source_name}")
            except Exception as e:
                logger.error(f"Error getting trending news from {source_name}: {e}")
        
        # Sort by date (most recent first) and limit results
        all_trending.sort(key=lambda x: x.get('date', ''), reverse=True)
        return all_trending[:max_results]
    
    def _get_trending_from_source(self, source_url, max_results=5, days=3):
        """
        Get trending articles from a specific news source.
        
        Args:
            source_url (str): Base URL of the news source
            max_results (int): Maximum number of results to return
            days (int): Look for news within this many past days
            
        Returns:
            list: List of trending news article dictionaries from this source
        """
        self._respect_rate_limit()
        
        # Parse the domain for source identification
        domain = urlparse(source_url).netloc
        source_name = domain.replace('www.', '').split('.')[0]
        
        # Build newspaper Source object
        source = newspaper.build(source_url, memoize_articles=False, language='en')
        
        # Get the most prominent articles (usually featured on homepage)
        trending_articles = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Process the top articles from the source
        for i, article_url in enumerate(source.article_urls()):
            if i >= max_results * 3:  # Check more than we need to account for filtering
                break
                
            try:
                # Create and parse article
                article = Article(article_url, language='en')
                article.download()
                article.parse()
                article.nlp()  # Extract keywords, summary
                
                # Check if article has a valid date and is recent enough
                if article.publish_date and article.publish_date >= cutoff_date:
                    # Extract relevant information
                    article_info = {
                        "title": article.title,
                        "url": article_url,
                        "text": article.text[:1000] + ("..." if len(article.text) > 1000 else ""),
                        "summary": article.summary,
                        "keywords": article.keywords,
                        "date": article.publish_date.isoformat() if article.publish_date else "",
                        "authors": article.authors,
                        "source": source_name,
                        "domain": domain
                    }
                    
                    trending_articles.append(article_info)
                    
                    if len(trending_articles) >= max_results:
                        break
            
            except Exception as e:
                logger.debug(f"Error processing article {article_url}: {e}")
                continue
        
        return trending_articles
    
    def search_hackernews(self, query, max_results=10):
        """
        Search Hacker News for tech-related discussions.
        
        Args:
            query (str): The search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of Hacker News posts matching the query
        """
        self._respect_rate_limit()
        
        # Hacker News Algolia API
        url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&numericFilters=points>50"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            if "hits" not in data:
                logger.warning("No results found in Hacker News response")
                return []
            
            results = []
            for hit in data["hits"][:max_results]:
                post_info = {
                    "title": hit.get("title", ""),
                    "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
                    "points": hit.get("points", 0),
                    "num_comments": hit.get("num_comments", 0),
                    "author": hit.get("author", ""),
                    "created_at": hit.get("created_at", ""),
                    "objectID": hit.get("objectID", ""),
                    "source": "Hacker News"
                }
                results.append(post_info)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Hacker News: {e}")
            return []
    
    def get_full_article_content(self, url):
        """
        Extract the full content of an article from its URL.
        
        Args:
            url (str): The URL of the article
            
        Returns:
            dict: Article content and metadata
        """
        self._respect_rate_limit()
        
        try:
            article = Article(url, language='en')
            article.download()
            article.parse()
            article.nlp()  # Extract keywords, summary
            
            return {
                "title": article.title,
                "url": url,
                "text": article.text,
                "summary": article.summary,
                "keywords": article.keywords,
                "date": article.publish_date.isoformat() if article.publish_date else "",
                "authors": article.authors,
                "top_image": article.top_image,
                "domain": urlparse(url).netloc
            }
            
        except Exception as e:
            logger.error(f"Error extracting article content from {url}: {e}")
            return {"url": url, "error": str(e)}