import os
import logging
import time
import json
from datetime import datetime
from serpapi import GoogleSearch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SearchAPI:
    """
    Wrapper for SerpAPI integration to perform web searches efficiently.
    """

    def __init__(self):
        """
        Initialize the Search API with SerpAPI key from environment variables.
        """
        self.logger = logging.getLogger(__name__)
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        
        if not self.serpapi_key:
            self.logger.error("SerpAPI key not found in environment variables.")
            raise ValueError("SerpAPI key is required.")
        
        # Rate limiting variables
        self.last_request_time = 0
        self.min_request_interval = 1  # seconds
        self.retry_attempts = 3  # Number of retries for failed requests
    
    def search(self, query, num_results=10, search_type="web", **kwargs):
        """
        Perform a search using SerpAPI.

        Args:
            query: Search query string
            num_results: Number of results to return
            search_type: Type of search ('web', 'news', 'scholar', 'patents')
            **kwargs: Additional search parameters

        Returns:
            Dictionary containing search results
        """
        self._apply_rate_limit()
        results = self._serpapi_search(query, num_results, search_type, **kwargs)
        # Return results as a list to match expected structure in the logs
        return results
    
    def fetch_web_data(self, query, num_results=10):
        """
        Fetch web data from SerpAPI.

        Args:
            query: Search query string
            num_results: Number of results to return

        Returns:
            List of search results
        """
        return self._serpapi_search(query, num_results, search_type="web")

    def _apply_rate_limit(self):
        """Apply rate limiting to avoid hitting API limits."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)

        self.last_request_time = time.time()

    def _serpapi_search(self, query, num_results=10, search_type="web", **kwargs):
        """
        Perform a search using SerpAPI.

        Args:
            query: Search query string
            num_results: Number of results to return
            search_type: Type of search ('web', 'news', 'scholar', 'patents')
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        for attempt in range(self.retry_attempts):
            try:
                search_params = {
                    "q": query,
                    "api_key": self.serpapi_key,
                    "num": num_results,
                    "engine": "google"
                }

                # Add additional parameters from kwargs
                search_params.update(kwargs)

                if search_type == "news":
                    search_params["tbm"] = "nws"
                elif search_type == "scholar":
                    search_params["engine"] = "google_scholar"
                elif search_type == "patents":
                    search_params["q"] = f"{query} site:patents.google.com"

                search = GoogleSearch(search_params)
                response = search.get_dict()

                # Check if results exist
                if not response or "error" in response:
                    error_msg = response.get("error", "Unknown error") if "error" in response else "No response"
                    self.logger.warning(f"[Attempt {attempt + 1}] Search error: {error_msg} for query: {query}")
                    time.sleep(2)  # Small delay before retrying
                    continue

                results = self._extract_results(response, search_type)
                
                # Return early if we got results
                if results:
                    return results[:num_results]
                else:
                    self.logger.warning(f"[Attempt {attempt + 1}] No results extracted for query: {query}")
                    time.sleep(1)  # Small delay before retrying

            except Exception as e:
                self.logger.error(f"[Attempt {attempt + 1}] Error in SerpAPI search: {e}")
                time.sleep(2)  # Delay before retrying

        # Return empty list after retries are exhausted
        self.logger.warning(f"All {self.retry_attempts} attempts failed for query: {query}")
        return []

    def _extract_results(self, response, search_type):
        """
        Extract relevant search results from SerpAPI response.

        Args:
            response: API response from SerpAPI
            search_type: The type of search performed

        Returns:
            List of formatted search results
        """
        results = []

        try:
            # Extract organic search results
            if "organic_results" in response:
                for item in response["organic_results"]:
                    results.append(self._format_result(item, search_type))

            # Extract news results if applicable
            if search_type == "news" and "news_results" in response:
                for item in response["news_results"]:
                    results.append(self._format_result(item, "news"))
            
            # Extract scholar results if applicable
            if search_type == "scholar" and "organic_results" in response:
                for item in response["organic_results"]:
                    results.append(self._format_result(item, "scholar"))

            # Handle knowledge graph if present
            if "knowledge_graph" in response:
                kg = response["knowledge_graph"]
                if kg:
                    kg_result = {
                        "title": kg.get("title", ""),
                        "link": kg.get("website", ""),
                        "snippet": kg.get("description", ""),
                        "source": "serpapi_knowledge_graph",
                        "type": search_type,
                        "timestamp": datetime.now().isoformat()
                    }
                    results.append(kg_result)
        except Exception as e:
            self.logger.error(f"Error extracting results from response: {e}")
            
        return results

    def _format_result(self, item, search_type):
        """
        Format a single search result item.

        Args:
            item: A single result from SerpAPI
            search_type: The type of search

        Returns:
            Dictionary containing formatted result
        """
        try:
            return {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", item.get("description", "")),  # Fallback to description if snippet not available
                "source": "serpapi",
                "type": search_type,
                "timestamp": datetime.now().isoformat(),
                "position": item.get("position", 0)  # Include position in results
            }
        except Exception as e:
            self.logger.warning(f"Error formatting search result: {e}")
            return {
                "title": "Error formatting result",
                "link": "",
                "snippet": "",
                "source": "serpapi_error",
                "type": search_type,
                "timestamp": datetime.now().isoformat()
            }
            
    def safe_json_parse(self, json_string):
        """
        Safely parse a JSON string, handling potential formatting errors.
        
        Args:
            json_string: The JSON string to parse
            
        Returns:
            Parsed JSON object or None if parsing fails
        """
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}. Response: {json_string}")
            
            # Attempt to fix common JSON errors - missing quotes, incorrect quotes, etc.
            try:
                # Try to fix missing quotes around properties
                fixed_json = self._attempt_fix_json(json_string)
                if fixed_json:
                    return json.loads(fixed_json)
            except Exception as fix_error:
                self.logger.error(f"Failed to fix JSON: {fix_error}")
                
            return None
            
    def _attempt_fix_json(self, json_string):
        """
        Attempt to fix common JSON formatting errors.
        
        Args:
            json_string: The potentially malformed JSON string
            
        Returns:
            Fixed JSON string or None if fixing fails
        """
        try:
            # This is a simple approach that may work for minor issues
            # For more complex issues, consider using a more robust JSON repair library
            
            # Replace single quotes with double quotes (common Python -> JSON issue)
            fixed = json_string.replace("'", '"')
            
            # Try to fix unquoted property names
            import re
            fixed = re.sub(r'([{,])\s*(\w+):', r'\1"\2":', fixed)
            
            return fixed
        except Exception as e:
            self.logger.error(f"Error attempting to fix JSON: {e}")
            return None