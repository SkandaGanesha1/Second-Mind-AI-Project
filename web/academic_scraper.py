import time
import logging
from typing import Dict, List, Optional, Tuple, Union
from bs4 import BeautifulSoup
import requests
from scholarly import scholarly
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import re

from web.scraper import WebScraper

logger = logging.getLogger(__name__)

class AcademicScraper(WebScraper):
    """Scraper for academic repositories and scholarly articles"""
    
    def __init__(self, use_selenium: bool = True):
        super().__init__(use_selenium=use_selenium)
        self.repositories = {
            'arxiv': 'https://arxiv.org/search/',
            'ieee': 'https://ieeexplore.ieee.org/search/searchresult.jsp',
            'pubmed': 'https://pubmed.ncbi.nlm.nih.gov/?term=',
            'google_scholar': 'https://scholar.google.com/scholar?q='
        }
    
    def search_arxiv(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search ArXiv for academic papers
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of dictionaries containing paper information
        """
        base_url = 'https://arxiv.org/search/'
        search_url = f"{base_url}?query={query.replace(' ', '+')}&searchtype=all"
        
        _, soup = self.get_page_content(search_url)
        if not soup:
            return []
        
        results = []
        paper_elements = soup.select('.arxiv-result')
        
        for i, element in enumerate(paper_elements):
            if i >= max_results:
                break
                
            try:
                title_element = element.select_one('.title')
                authors_element = element.select_one('.authors')
                abstract_element = element.select_one('.abstract-full')
                pdf_link_element = element.select_one('a.download-pdf')
                published_element = element.select_one('.is-size-7')
                
                title = title_element.text.strip() if title_element else "No title"
                authors = authors_element.text.strip() if authors_element else "No authors"
                abstract = abstract_element.text.strip() if abstract_element else "No abstract"
                pdf_link = pdf_link_element['href'] if pdf_link_element else ""
                published = published_element.text.strip() if published_element else ""
                
                # Extract paper ID from URL
                paper_id_match = re.search(r'abs/([^/]+)', pdf_link)
                paper_id = paper_id_match.group(1) if paper_id_match else ""
                
                results.append({
                    'title': title,
                    'authors': authors,
                    'abstract': abstract,
                    'url': f"https://arxiv.org/abs/{paper_id}",
                    'pdf_url': f"https://arxiv.org/pdf/{paper_id}.pdf",
                    'published': published,
                    'source': 'arxiv'
                })
            except Exception as e:
                logger.error(f"Error parsing ArXiv result: {e}")
        
        return results
    
    def search_google_scholar(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search Google Scholar for academic papers
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of dictionaries containing paper information
        """
        if not self.use_selenium:
            logger.warning("Google Scholar scraping requires Selenium. Enabling Selenium.")
            self._setup_selenium()
        
        search_url = f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}"
        
        try:
            self.driver.get(search_url)
            time.sleep(3)  # Wait for page to load
            
            results = []
            paper_elements = self.driver.find_elements(By.CSS_SELECTOR, '.gs_ri')
            
            for i, element in enumerate(paper_elements):
                if i >= max_results:
                    break
                
                try:
                    title_element = element.find_element(By.CSS_SELECTOR, '.gs_rt')
                    title = title_element.text.strip()
                    
                    # Check if title has a link
                    link_element = title_element.find_elements(By.TAG_NAME, 'a')
                    url = link_element[0].get_attribute('href') if link_element else ""
                    
                    authors_element = element.find_elements(By.CSS_SELECTOR, '.gs_a')
                    authors = authors_element[0].text.strip() if authors_element else "No authors"
                    
                    snippet_element = element.find_elements(By.CSS_SELECTOR, '.gs_rs')
                    snippet = snippet_element[0].text.strip() if snippet_element else "No snippet"
                    
                    results.append({
                        'title': title,
                        'authors': authors,
                        'snippet': snippet,
                        'url': url,
                        'source': 'google_scholar'
                    })
                except Exception as e:
                    logger.error(f"Error parsing Google Scholar result: {e}")
            
            return results
        except Exception as e:
            logger.error(f"Error searching Google Scholar: {e}")
            return []
    
    def search_pubmed(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search PubMed for academic papers
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of dictionaries containing paper information
        """
        search_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={query.replace(' ', '+')}"
        
        _, soup = self.get_page_content(search_url)
        if not soup:
            return []
        
        results = []
        paper_elements = soup.select('.docsum-content')
        
        for i, element in enumerate(paper_elements):
            if i >= max_results:
                break
                
            try:
                title_element = element.select_one('.docsum-title')
                authors_element = element.select_one('.docsum-authors')
                citation_element = element.select_one('.docsum-journal-citation')
                
                title = title_element.text.strip() if title_element else "No title"
                authors = authors_element.text.strip() if authors_element else "No authors"
                citation = citation_element.text.strip() if citation_element else ""
                
                # Extract paper ID
                paper_id_element = element.parent.get('data-article-id')
                paper_id = paper_id_element if paper_id_element else ""
                
                results.append({
                    'title': title,
                    'authors': authors,
                    'citation': citation,
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{paper_id}/",
                    'source': 'pubmed'
                })
            except Exception as e:
                logger.error(f"Error parsing PubMed result: {e}")
        
        return results
    
    def search_scholarly(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search for academic papers using scholarly (Google Scholar API)
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of dictionaries containing paper information
        """
        try:
            search_query = scholarly.search_pubs(query)
            results = []
            
            for i in range(max_results):
                try:
                    publication = next(search_query)
                    
                    # Extract basic information
                    title = publication.get('bib', {}).get('title', '')
                    authors = publication.get('bib', {}).get('author', [])
                    abstract = publication.get('bib', {}).get('abstract', '')
                    year = publication.get('bib', {}).get('pub_year', '')
                    venue = publication.get('bib', {}).get('venue', '')
                    
                    # Extract citation information
                    num_citations = publication.get('num_citations', 0)
                    
                    # Extract URLs
                    url = publication.get('pub_url', '')
                    
                    results.append({
                        'title': title,
                        'authors': authors,
                        'abstract': abstract,
                        'year': year,
                        'venue': venue,
                        'num_citations': num_citations,
                        'url': url,
                        'source': 'scholarly'
                    })
                except StopIteration:
                    break
                except Exception as e:
                    logger.error(f"Error processing scholarly result: {e}")
            
            return results
        except Exception as e:
            logger.error(f"Error searching scholarly: {e}")
            return []
    
    def get_paper_details(self, url: str) -> Dict:
        """
        Get detailed information about a specific paper
        
        Args:
            url: URL of the paper
            
        Returns:
            Dictionary containing paper details
        """
        _, soup = self.get_page_content(url)
        if not soup:
            return {}
        
        # Identify the source based on URL
        source = None
        for repo_name, repo_url in self.repositories.items():
            if repo_url.split('//')[1].split('/')[0] in url:
                source = repo_name
                break
        
        if source == 'arxiv':
            return self._parse_arxiv_paper(soup, url)
        elif source == 'pubmed':
            return self._parse_pubmed_paper(soup, url)
        else:
            # Fall back to generic content extraction
            return self.extract_main_content(url)
    
    def _parse_arxiv_paper(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse ArXiv paper details"""
        title = soup.select_one('h1.title').text.replace('Title:', '').strip() if soup.select_one('h1.title') else ""
        authors = soup.select_one('div.authors').text.replace('Authors:', '').strip() if soup.select_one('div.authors') else ""
        abstract = soup.select_one('blockquote.abstract').text.replace('Abstract:', '').strip() if soup.select_one('blockquote.abstract') else ""
        
        # Extract paper ID from URL
        paper_id_match = re.search(r'abs/([^/]+)', url)
        paper_id = paper_id_match.group(1) if paper_id_match else ""
        
        # Extract additional metadata
        comments = soup.select_one('td.comments')
        subjects = soup.select_one('td.subjects')
        
        return {
            'title': title,
            'authors': authors,
            'abstract': abstract,
            'url': url,
            'pdf_url': f"https://arxiv.org/pdf/{paper_id}.pdf",
            'comments': comments.text.strip() if comments else "",
            'subjects': subjects.text.strip() if subjects else "",
            'source': 'arxiv'
        }
    
    def _parse_pubmed_paper(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse PubMed paper details"""
        title = soup.select_one('h1.heading-title').text.strip() if soup.select_one('h1.heading-title') else ""
        authors = [author.text.strip() for author in soup.select('div.authors-list span.authors-list-item')]
        abstract = soup.select_one('div#abstract').text.strip() if soup.select_one('div#abstract') else ""
        
        # Extract journal information
        journal_element = soup.select_one('button.journal-actions-trigger')
        journal = journal_element.text.strip() if journal_element else ""
        
        # Extract publication date
        pub_date_element = soup.select_one('span.cit')
        pub_date = pub_date_element.text.strip() if pub_date_element else ""
        
        return {
            'title': title,
            'authors': authors,
            'abstract': abstract,
            'journal': journal,
            'publication_date': pub_date,
            'url': url,
            'source': 'pubmed'
        }
    
    def search_academic_repositories(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search multiple academic repositories for papers
        
        Args:
            query: Search query
            max_results: Maximum number of results to return per repository
            
        Returns:
            List of dictionaries containing paper information
        """
        results = []
        
        # Search ArXiv
        arxiv_results = self.search_arxiv(query, max_results)
        results.extend(arxiv_results)
        
        # Search PubMed
        pubmed_results = self.search_pubmed(query, max_results)
        results.extend(pubmed_results)
        
        # Search Google Scholar
        try:
            scholar_results = self.search_google_scholar(query, max_results)
            results.extend(scholar_results)
        except Exception as e:
            logger.error(f"Error searching Google Scholar: {e}")
        
        return results