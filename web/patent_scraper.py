"""
Patent Database Scraper for The Second Mind project.
This module provides functions to scrape patent information from various patent databases.
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import re
import logging
from datetime import datetime
from urllib.parse import quote_plus

# Configure logging
logger = logging.getLogger(__name__)

class PatentScraper:
    """Scraper for obtaining patent information from various patent databases."""
    
    def __init__(self, rate_limit=1):
        """
        Initialize the patent scraper.
        
        Args:
            rate_limit (float): Minimum time between requests in seconds
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.rate_limit = rate_limit
        self.last_request_time = 0
    
    def _respect_rate_limit(self):
        """Ensure we don't exceed the rate limit"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit:
            time.sleep(self.rate_limit - time_since_last_request)
        
        self.last_request_time = time.time()
    
    def search_google_patents(self, query, max_results=10):
        """
        Search Google Patents for the specified query.
        
        Args:
            query (str): The search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of patent dictionaries containing metadata
        """
        self._respect_rate_limit()
        
        base_url = "https://patents.google.com/xhr/query"
        params = {
            "url": f"q={quote_plus(query)}",
            "exp": "",
            "json": ""
        }
        
        try:
            response = self.session.get(base_url, params=params)
            response.raise_for_status()
            
            # Google Patents returns JSON
            data = response.json()
            
            if "results" not in data:
                logger.warning("No results found in Google Patents response")
                return []
            
            patents = []
            for i, result in enumerate(data["results"]["cluster"]):
                if i >= max_results:
                    break
                    
                patent_info = {
                    "title": result.get("title", ""),
                    "patent_id": result.get("patent_id", ""),
                    "abstract": result.get("abstract", ""),
                    "inventors": result.get("inventor", []),
                    "assignee": result.get("assignee", []),
                    "filing_date": result.get("filing_date", ""),
                    "publication_date": result.get("publication_date", ""),
                    "source": "Google Patents",
                    "url": f"https://patents.google.com/patent/{result.get('patent_id', '')}"
                }
                patents.append(patent_info)
                
            return patents
            
        except Exception as e:
            logger.error(f"Error searching Google Patents: {e}")
            return []
    
    def search_uspto(self, query, max_results=10):
        """
        Search the USPTO Patent Database.
        
        Args:
            query (str): The search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of patent dictionaries containing metadata
        """
        self._respect_rate_limit()
        
        # USPTO Advanced Search URL
        base_url = "https://ppubs.uspto.gov/dirsearch-public/searches/publication"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        payload = {
            "searchText": query,
            "fq": [],
            "fl": "*",
            "mm": "100%",
            "df": "patentTitle",
            "qf": "patentTitle^5.0 inventorName^2.0 assigneeEntityName^2.0 abstractText",
            "sort": "applFilingDate desc",
            "rows": max_results
        }
        
        try:
            response = self.session.post(base_url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if "response" not in data or "docs" not in data["response"]:
                logger.warning("No results found in USPTO response")
                return []
            
            patents = []
            for doc in data["response"]["docs"]:
                patent_info = {
                    "title": doc.get("patentTitle", ""),
                    "patent_id": doc.get("patentNumber", ""),
                    "abstract": doc.get("abstractText", ""),
                    "inventors": doc.get("inventorName", []),
                    "assignee": doc.get("assigneeEntityName", []),
                    "filing_date": doc.get("applFilingDate", ""),
                    "publication_date": doc.get("patentIssueDate", ""),
                    "source": "USPTO",
                    "url": f"https://ppubs.uspto.gov/dirbrowser/html/pat/{doc.get('patentNumber', '')}.html"
                }
                patents.append(patent_info)
                
            return patents
            
        except Exception as e:
            logger.error(f"Error searching USPTO: {e}")
            return []
    
    def search_espacenet(self, query, max_results=10):
        """
        Search the European Patent Office's Espacenet database.
        
        Args:
            query (str): The search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of patent dictionaries containing metadata
        """
        self._respect_rate_limit()
        
        # Espacenet uses GraphQL API
        base_url = "https://worldwide.espacenet.com/3.2/rest-services/search"
        
        payload = {
            "query": {
                "SearchQuery": {
                    "simpleSearchQuery": query,
                    "resultsPerPage": max_results,
                    "sortBy": "RELEVANCE"
                }
            }
        }
        
        try:
            response = self.session.post(base_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if "results" not in data:
                logger.warning("No results found in Espacenet response")
                return []
            
            patents = []
            for result in data["results"]:
                biblio = result.get("biblio", {})
                patent_info = {
                    "title": biblio.get("title", ""),
                    "patent_id": biblio.get("publicationNumber", ""),
                    "abstract": biblio.get("abstract", ""),
                    "inventors": [inv.get("name", "") for inv in biblio.get("inventors", [])],
                    "assignee": [app.get("name", "") for app in biblio.get("applicants", [])],
                    "filing_date": biblio.get("filingDate", ""),
                    "publication_date": biblio.get("publicationDate", ""),
                    "source": "Espacenet",
                    "url": f"https://worldwide.espacenet.com/patent/search/family/{biblio.get('familyId', '')}"
                }
                patents.append(patent_info)
                
            return patents
            
        except Exception as e:
            logger.error(f"Error searching Espacenet: {e}")
            return []
    
    def search_patents(self, query, sources=None, max_results=10):
        """
        Search multiple patent databases and combine results.
        
        Args:
            query (str): The search query
            sources (list): List of sources to search ('google', 'uspto', 'espacenet')
            max_results (int): Maximum results per source
            
        Returns:
            list: Combined list of patent results from all sources
        """
        if sources is None:
            sources = ['google', 'uspto', 'espacenet']
        
        results = []
        
        if 'google' in sources:
            google_results = self.search_google_patents(query, max_results)
            results.extend(google_results)
            logger.info(f"Found {len(google_results)} patents from Google Patents")
        
        if 'uspto' in sources:
            uspto_results = self.search_uspto(query, max_results)
            results.extend(uspto_results)
            logger.info(f"Found {len(uspto_results)} patents from USPTO")
        
        if 'espacenet' in sources:
            espacenet_results = self.search_espacenet(query, max_results)
            results.extend(espacenet_results)
            logger.info(f"Found {len(espacenet_results)} patents from Espacenet")
        
        # Filter duplicates based on patent_id
        unique_results = []
        seen_ids = set()
        
        for patent in results:
            if patent['patent_id'] not in seen_ids:
                seen_ids.add(patent['patent_id'])
                unique_results.append(patent)
        
        logger.info(f"Total unique patents found: {len(unique_results)}")
        return unique_results

    def get_patent_details(self, patent_id, source='google'):
        """
        Get detailed information for a specific patent.
        
        Args:
            patent_id (str): The patent identifier
            source (str): Source database ('google', 'uspto', 'espacenet')
            
        Returns:
            dict: Detailed patent information
        """
        if source == 'google':
            return self._get_google_patent_details(patent_id)
        elif source == 'uspto':
            return self._get_uspto_patent_details(patent_id)
        elif source == 'espacenet':
            return self._get_espacenet_patent_details(patent_id)
        else:
            logger.error(f"Unknown patent source: {source}")
            return {}
    
    def _get_google_patent_details(self, patent_id):
        """Get detailed information from Google Patents"""
        self._respect_rate_limit()
        
        url = f"https://patents.google.com/patent/{patent_id}/en"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract detailed information using BeautifulSoup
            title = soup.select_one('meta[name="DC.title"]')
            title = title['content'] if title else ""
            
            abstract = soup.select_one('meta[name="DC.description"]')
            abstract = abstract['content'] if abstract else ""
            
            inventor_tags = soup.select('meta[name="DC.contributor"]')
            inventors = [tag['content'] for tag in inventor_tags]
            
            assignee = soup.select_one('dd[itemprop="assigneeCurrent"]')
            assignee = assignee.text.strip() if assignee else ""
            
            filing_date = soup.select_one('time[itemprop="filing"]')
            filing_date = filing_date.text.strip() if filing_date else ""
            
            publication_date = soup.select_one('time[itemprop="publicationDate"]')
            publication_date = publication_date.text.strip() if publication_date else ""
            
            # Extract claims
            claims_section = soup.select_one('section[itemprop="claims"]')
            claims = []
            if claims_section:
                claim_elements = claims_section.select('div[itemprop="claim"]')
                for claim in claim_elements:
                    claims.append(claim.text.strip())
            
            # Extract description
            description_section = soup.select_one('section[itemprop="description"]')
            description = description_section.text.strip() if description_section else ""
            
            # Extract drawing URLs if available
            drawings = []
            drawings_section = soup.select('figure[itemprop="drawings"] img')
            for img in drawings_section:
                if 'src' in img.attrs:
                    drawings.append(img['src'])
            
            return {
                "title": title,
                "patent_id": patent_id,
                "abstract": abstract,
                "inventors": inventors,
                "assignee": assignee,
                "filing_date": filing_date,
                "publication_date": publication_date,
                "claims": claims,
                "description": description,
                "drawings": drawings,
                "source": "Google Patents",
                "url": url
            }
            
        except Exception as e:
            logger.error(f"Error getting Google patent details: {e}")
            return {"patent_id": patent_id, "error": str(e)}
    
    def _get_uspto_patent_details(self, patent_id):
        """Get detailed information from USPTO"""
        # Similar implementation to Google Patents but for USPTO
        # Implement as needed
        return {"patent_id": patent_id, "source": "USPTO", "status": "not_implemented"}
    
    def _get_espacenet_patent_details(self, patent_id):
        """Get detailed information from Espacenet"""
        # Similar implementation to Google Patents but for Espacenet
        # Implement as needed
        return {"patent_id": patent_id, "source": "Espacenet", "status": "not_implemented"}