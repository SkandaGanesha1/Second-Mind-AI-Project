"""
Proximity Agent for The Second Mind
Links current hypotheses to past interactions and existing knowledge.
"""
import time
import requests
from typing import Dict, Any, List, Tuple
import math
import re
import json

from utils.logger import get_logger

from .base_agent import BaseAgent
from utils.gemini_client import generate_text

class ProximityAgent(BaseAgent):
    """
    Proximity Agent evaluates the proximity of hypotheses to known facts,
    previous research results, and past interactions for better context continuity.
    """
    
    def __init__(self, storage_manager, mcps_url="http://localhost:8000"):
        """
        Initialize the Proximity Agent.
        
        Args:
            storage_manager: Storage manager for retrieving past interactions
            mcps_url: URL of the Model Context Protocol Server
        """
        super().__init__("proximity", "Proximity Agent")
        self.storage_manager = storage_manager
        self.mcps_url = mcps_url
        self.logger = get_logger(__name__)
        self.required_context_keys = ["query", "evolved_hypotheses", "cycle"]
    
    def get_past_analogies(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve past analogies from the Model Context Protocol Server.
        
        Args:
            query: Query string to search for analogies
            limit: Maximum number of analogies to return
            
        Returns:
            List of past analogies with their metadata
        """
        try:
            # Prepare the MCPS GET request
            params = {
                'query': query,
                'limit': limit
            }
            
            # Make the GET request to MCPS
            response = requests.get(f"{self.mcps_url}/context/search", params=params)
            
            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return data.get('results', [])
                else:
                    self.logger.warning(f"MCPS returned error: {data.get('message', 'Unknown error')}")
                    return []
            else:
                self.logger.error(f"Failed to retrieve past analogies from MCPS: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error retrieving past analogies from MCPS: {str(e)}")
            return []
    
    def process(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process data to evaluate proximity to known facts and link hypotheses to past interactions.

        Args:
            context: Current context containing evolved hypotheses.

        Returns:
            Updated context with proximity connections and enhanced hypotheses.
        """
        start_time = time.time()
        success = False

        try:
            self.logger.info("ProximityAgent processing context data")
            
            # Debugging input type
            print(f"[DEBUG] Received context type: {type(context)}")
            
            if isinstance(context, tuple):  # Handle tuple case
                if len(context) >= 2 and isinstance(context[0], dict):
                    context = context[0]
                else:
                    context = {"query": "", "evolved_hypotheses": [], "cycle": 0}
            elif isinstance(context, list):
                context = {"query": "", "evolved_hypotheses": context, "cycle": 0}
            elif not isinstance(context, dict):
                raise ValueError(f"Unexpected data type in ProximityAgent: {type(context)}")

            # Validate context
            is_valid, error_msg = self.validate_context(context, self.required_context_keys)
            if not is_valid:
                self.logger.error(f"Context validation failed: {error_msg}")
                raise ValueError(error_msg)

            evolved_hypotheses = context.get("evolved_hypotheses", [])
            query = context.get("query", "")
            cycle = context.get("cycle", 0)
            
            # Retrieve past interactions from storage
            past_interactions = self.storage_manager.retrieve_past_interactions(limit=20)
            
            # NEW: Retrieve past analogies from MCPS
            past_analogies = self.get_past_analogies(query, limit=10)
            self.logger.info(f"Retrieved {len(past_analogies)} past analogies from MCPS")
            
            # NEW: Combine past interactions with past analogies
            combined_interactions = past_interactions.copy()
            
            # Transform analogies to match the format of past interactions
            for analogy in past_analogies:
                analogy_data = analogy.get('data', {})
                if isinstance(analogy_data, str):
                    try:
                        analogy_data = json.loads(analogy_data)
                    except:
                        analogy_data = {"statement": analogy_data}
                
                interaction = {
                    "id": analogy.get('key', f"analogy_{len(combined_interactions)}"),
                    "query": analogy_data.get('query', ''),
                    "proximitized_hypotheses": [],
                    "evolved_hypotheses": [],
                    "hypotheses": [
                        {
                            "id": f"analogy_hypothesis_{i}",
                            "statement": statement if isinstance(statement, str) else statement.get('statement', ''),
                            "confidence": statement.get('confidence', 0.7) if isinstance(statement, dict) else 0.7
                        }
                        for i, statement in enumerate(analogy_data.get('statements', []))
                    ]
                }
                
                # If hypotheses is empty, create one from the analogy itself
                if not interaction["hypotheses"] and 'statement' in analogy_data:
                    interaction["hypotheses"] = [{
                        "id": f"analogy_hypothesis_main",
                        "statement": analogy_data['statement'],
                        "confidence": analogy_data.get('confidence', 0.7)
                    }]
                
                combined_interactions.append(interaction)
            
            # Store web data, hypothesis, and reflection results
            results = context.get('web_data', [])
            for result in results:
                self.storage_manager.store_result(result)
            if 'hypotheses' in context:
                for hypothesis in context['hypotheses']:
                    self.storage_manager.store_result(hypothesis)
            if 'reflection_results' in context:
                for result in context['reflection_results']:
                    self.storage_manager.store_result(result)
            
            # Find connections between hypotheses and past interactions
            proximity_results = []
            for hypothesis in evolved_hypotheses:
                # Use combined_interactions instead of just past_interactions
                connections = self._find_connections_with_embeddings(hypothesis, combined_interactions, query)
                proximity_result = {
                    "hypothesis_id": hypothesis.get("id", "unknown"),
                    "connections": connections,
                    "has_connections": len(connections) > 0,
                    "proximity_score": self._calculate_proximity_score(connections)
                }
                proximity_results.append(proximity_result)
            
            # Ensure correct format
            if not isinstance(proximity_results, list):
                self.logger.error(f"Proximity results have invalid format: {type(proximity_results)}")
                proximity_results = []

            # Update context
            context["proximity_results"] = proximity_results
            context["proximity_timestamp"] = time.time()
            context["proximitized_hypotheses"] = (
                self._enhance_hypotheses(evolved_hypotheses, proximity_results)
                if combined_interactions else evolved_hypotheses
            )
            
            # NEW: Store the proximity results in MCPS
            self._store_proximity_results_in_mcps(context, proximity_results)

            success = True
            found_connections = sum(1 for result in proximity_results if result["has_connections"])
            self.logger.info(f"Found connections for {found_connections}/{len(evolved_hypotheses)} hypotheses")
        
        except Exception as e:
            self.logger.error(f"Error in ProximityAgent: {str(e)}")
            if "proximitized_hypotheses" not in context and "evolved_hypotheses" in context:
                context["proximitized_hypotheses"] = context["evolved_hypotheses"]
            context["proximity_results"] = []

        # Update metrics
        processing_time = time.time() - start_time
        self.update_metrics(processing_time, success)
        
        return context  # Ensure returning a dictionary
    
    def _store_proximity_results_in_mcps(self, context: Dict[str, Any], proximity_results: List[Dict[str, Any]]) -> None:
        """
        Store proximity results in the Model Context Protocol Server.
        
        Args:
            context: Current context
            proximity_results: Proximity analysis results
        """
        try:
            session_id = context.get("session_id", f"proximity_session_{int(time.time())}")
            
            # Prepare data for MCPS
            data = {
                "session_id": session_id,
                "type": "proximity_results",
                "data": {
                    "query": context.get("query", ""),
                    "cycle": context.get("cycle", 0),
                    "timestamp": time.time(),
                    "results": proximity_results
                },
                "relevance": 0.9,  # High relevance for recent results
                "relationships": {
                    "query": context.get("query", "")
                }
            }
            
            # Send POST request to MCPS
            response = requests.post(f"{self.mcps_url}/context", json=data)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully stored proximity results in MCPS: {response.json().get('item_id')}")
            else:
                self.logger.warning(f"Failed to store proximity results in MCPS: {response.status_code}")
        
        except Exception as e:
            self.logger.error(f"Error storing proximity results in MCPS: {str(e)}")
    
    def _calculate_proximity_score(self, connections):
        """
        Calculate a proximity score based on connections.
        
        Args:
            connections: List of connection dictionaries
            
        Returns:
            Float score representing proximity strength
        """
        if not connections:
            return 0.0
            
        # Calculate average similarity score of connections
        avg_similarity = sum(conn.get("similarity_score", 0) for conn in connections) / len(connections)
        
        # Weight by number of connections (capped at 3)
        connection_weight = min(len(connections), 3) / 3
        
        return avg_similarity * connection_weight
  
    def _find_connections_with_embeddings(self, hypothesis: dict[str, Any], 
                                         past_interactions: List[dict[str, Any]], 
                                         query: str) -> List[dict[str, Any]]:
        """
        Find connections between a hypothesis and past interactions using vector embeddings.
        
        Args:
            hypothesis: Current hypothesis
            past_interactions: List of past interactions
            query: Current query
            
        Returns:
            List of connection dictionaries
        """
        if not past_interactions:
            return []
        
        statement = hypothesis["statement"]
        connections = []
        
        try:
            # Generate embeddings for current hypothesis and query using Gemini
            current_embeddings = self._generate_embeddings(statement, query)
            
            # Process past interactions to find connections
            for interaction in past_interactions:
                past_query = interaction.get("query", "")
                past_hypotheses = interaction.get("proximitized_hypotheses", [])
                
                if not past_hypotheses:
                    past_hypotheses = interaction.get("evolved_hypotheses", [])
                    
                if not past_hypotheses:
                    past_hypotheses = interaction.get("hypotheses", [])
                
                # Skip if no hypotheses in past interaction
                if not past_hypotheses:
                    continue
                
                # Process each past hypothesis
                for past_hypothesis in past_hypotheses:
                    past_statement = past_hypothesis.get("statement", "")
                    
                    # Skip if statement is empty
                    if not past_statement:
                        continue
                    
                    # Calculate semantic similarity using embeddings
                    similarity_score = self._calculate_embedding_similarity(
                        current_embeddings, past_statement, past_query
                    )
                    
                    # If similarity is strong enough, record connection
                    if similarity_score >= 0.35:
                        connection = {
                            "past_interaction_id": interaction.get("id", "unknown"),
                            "past_query": past_query,
                            "past_hypothesis_id": past_hypothesis.get("id", "unknown"),
                            "past_statement": past_statement,
                            "similarity_score": round(similarity_score, 2),
                            "connection_type": self._determine_connection_type(
                                statement, past_statement, similarity_score
                            )
                        }
                        connections.append(connection)
            
        except Exception as e:
            self.logger.error(f"Error in embedding-based connection finding: {str(e)}")
            # Fall back to keyword-based method if embedding fails
            return self._find_connections_keyword_based(hypothesis, past_interactions, query)
        
        # Sort connections by similarity score (descending)
        connections.sort(key=lambda c: c["similarity_score"], reverse=True)
        
        # Limit to top connections
        return connections[:3]
    
    def _generate_embeddings(self, statement: str, query: str) -> str:
        """
        Generate embeddings representation for a statement and query using Gemini LLM.
        
        Args:
            statement: Hypothesis statement
            query: Current query
            
        Returns:
            Embedding representation as a string for later comparison
        """
        # Create a prompt for embedding generation
        prompt = f"""
        Task: Generate a semantic embedding representation for the following hypothesis and query. 
        Extract the core concepts, entities, and relationships that define the meaning.
        
        Query: "{query}"
        Hypothesis: "{statement}"
        
        Format the output as a concise, structured semantic representation with key concepts and their relationships.
        Focus on the most salient and distinctive elements of meaning.
        """
        
        # Generate embeddings using Gemini
        embedding = generate_text(prompt, temperature=0.1)
        
        # If embedding generation fails, return the original text
        if not embedding:
            return statement + " " + query
            
        return embedding
    
    def _calculate_embedding_similarity(self, current_embeddings: str, 
                                      past_statement: str, past_query: str) -> float:
        """
        Calculate semantic similarity between current and past statements using embeddings.
        
        Args:
            current_embeddings: Embeddings for current hypothesis
            past_statement: Past hypothesis statement
            past_query: Past query
            
        Returns:
            Similarity score between 0 and 1
        """
        # Create a prompt for similarity calculation
        prompt = f"""
        Task: Calculate the semantic similarity between the following pairs of statements.
        
        Pair 1: "{current_embeddings}"
        Pair 2: "{past_statement} {past_query}"
        
        Score the similarity on a scale from 0.0 to 1.0, where:
        - 0.0 means completely unrelated
        - 0.5 means somewhat related
        - 1.0 means identical in meaning
        
        Return only the similarity score as a decimal number between 0.0 and 1.0.
        """
        
        # Generate similarity score using Gemini
        similarity_response = generate_text(prompt, temperature=0.1)
        
        try:
            # Extract the similarity score from the response
            similarity = float(similarity_response.strip())
            # Ensure score is between 0 and 1
            similarity = max(0.0, min(1.0, similarity))
            return similarity
        except:
            # If parsing fails, use a fallback method
            return self._calculate_fallback_similarity(current_embeddings, past_statement + " " + past_query)
    
    def _calculate_fallback_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using a fallback method."""
        # Extract keywords from both texts
        keywords1 = self._extract_keywords(text1)
        keywords2 = self._extract_keywords(text2)
        
        # Calculate Jaccard similarity
        intersection = set(keywords1).intersection(set(keywords2))
        union = set(keywords1).union(set(keywords2))
        
        if not union:
            return 0.0
            
        return len(intersection) / len(union)
    
    def _find_connections_keyword_based(self, hypothesis: dict[str, Any], 
                                     past_interactions: List[dict[str, Any]], 
                                     query: str) -> List[dict[str, Any]]:
        """
        Fallback method to find connections using keywords.
        
        Args:
            hypothesis: Current hypothesis
            past_interactions: List of past interactions
            query: Current query
            
        Returns:
            List of connection dictionaries
        """
        if not past_interactions:
            return []
        
        statement = hypothesis["statement"]
        connections = []
        
        # Extract keywords from statement
        statement_keywords = self._extract_keywords(statement)
        query_keywords = self._extract_keywords(query)
        
        # Find connections in past interactions
        for interaction in past_interactions:
            past_query = interaction.get("query", "")
            past_hypotheses = interaction.get("proximitized_hypotheses", [])
            
            if not past_hypotheses:
                past_hypotheses = interaction.get("evolved_hypotheses", [])
                
            if not past_hypotheses:
                past_hypotheses = interaction.get("hypotheses", [])
            
            # Skip if no hypotheses in past interaction
            if not past_hypotheses:
                continue
            
            # Check similarity between current query and past query
            query_similarity = self._calculate_similarity(
                query_keywords, self._extract_keywords(past_query)
            )
            
            # Check each past hypothesis
            for past_hypothesis in past_hypotheses:
                past_statement = past_hypothesis.get("statement", "")
                
                # Skip if statement is empty
                if not past_statement:
                    continue
                
                # Calculate similarity between current hypothesis and past hypothesis
                hypothesis_similarity = self._calculate_similarity(
                    statement_keywords, self._extract_keywords(past_statement)
                )
                
                # Calculate overall connection strength
                connection_strength = 0.7 * hypothesis_similarity + 0.3 * query_similarity
                
                # If connection is strong enough, record it
                if connection_strength >= 0.3:
                    connection = {
                        "past_interaction_id": interaction.get("id", "unknown"),
                        "past_query": past_query,
                        "past_hypothesis_id": past_hypothesis.get("id", "unknown"),
                        "past_statement": past_statement,
                        "similarity_score": round(connection_strength, 2),
                        "connection_type": self._determine_connection_type(
                            statement, past_statement, connection_strength
                        )
                    }
                    connections.append(connection)
        
        # Sort connections by similarity score (descending)
        connections.sort(key=lambda c: c["similarity_score"], reverse=True)
        
        # Limit to top connections
        return connections[:3]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for similarity comparison."""
        # Remove stop words and punctuation, convert to lowercase
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", 
                      "for", "of", "in", "to", "with", "by", "about", "could", "would"}
        
        # Clean text
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)  # Replace punctuation with space
        
        # Extract words
        words = text.split()
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Add bigrams (two-word combinations)
        bigrams = []
        for i in range(len(words) - 1):
            if words[i] not in stop_words and words[i+1] not in stop_words:
                bigram = f"{words[i]} {words[i+1]}"
                bigrams.append(bigram)
        
        return list(set(keywords + bigrams))
    
    def _calculate_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        """Calculate similarity between two sets of keywords."""
        if not keywords1 or not keywords2:
            return 0.0
        
        # Calculate Jaccard similarity (intersection over union)
        intersection = set(keywords1).intersection(set(keywords2))
        union = set(keywords1).union(set(keywords2))
        
        if not union:
            return 0.0
            
        jaccard = len(intersection) / len(union)
        
        # Calculate overlap coefficient (intersection over smaller set)
        overlap = len(intersection) / min(len(set(keywords1)), len(set(keywords2)))
        
        # Combine both metrics
        similarity = 0.5 * jaccard + 0.5 * overlap
        
        return similarity
    
    def _determine_connection_type(self, current_statement: str, past_statement: str, 
                                 similarity_score: float) -> str:
        """Determine the type of connection between two statements."""
        # Determine connection type based on similarity score and content analysis
        if similarity_score > 0.7:
            return "Strong semantic similarity"
        elif similarity_score > 0.5:
            return "Moderate semantic similarity"
        elif similarity_score > 0.35:
            return "Topical semantic relation"
        else:
            return "Weak semantic connection"
    
    def _enhance_hypotheses(self, hypotheses: List[dict[str, Any]], 
                          proximity_results: List[dict[str, Any]]) -> List[dict[str, Any]]:
        """
        Enhance hypotheses with connection information.
        
        Args:
            hypotheses: List of hypotheses
            proximity_results: Proximity analysis results
            
        Returns:
            Enhanced list of hypotheses
        """
        # Create a mapping of proximity results by hypothesis ID
        proximity_map = {r["hypothesis_id"]: r for r in proximity_results}
        
        # Enhance each hypothesis
        enhanced_hypotheses = []
        
        for hypothesis in hypotheses:
            hypothesis_id = hypothesis["id"]
            proximity_result = proximity_map.get(hypothesis_id)
            
            enhanced = hypothesis.copy()
            
            if proximity_result and proximity_result["has_connections"]:
                # Get the best connection
                best_connection = max(
                    proximity_result["connections"], 
                    key=lambda c: c["similarity_score"]
                )
                
                # Add connection information
                enhanced["has_past_connections"] = True
                enhanced["strongest_connection"] = {
                    "past_query": best_connection["past_query"],
                    "past_statement": best_connection["past_statement"],
                    "similarity_score": best_connection["similarity_score"],
                    "connection_type": best_connection["connection_type"]
                }
                
                # Adjust confidence based on connection strength
                confidence_boost = min(0.1, best_connection["similarity_score"] / 10)
                enhanced["confidence"] = min(1.0, hypothesis.get("confidence", 0.5) + confidence_boost)
                
                # Generate context note using LLM
                enhanced["context_note"] = self._generate_context_note(
                    hypothesis["statement"],
                    best_connection["past_statement"],
                    best_connection["connection_type"]
                )
            else:
                enhanced["has_past_connections"] = False
            
            enhanced_hypotheses.append(enhanced)
        
        return enhanced_hypotheses
    
    def _generate_context_note(self, current_statement: str, past_statement: str, 
                             connection_type: str) -> str:
        """
        Generate a contextual note explaining the connection using LLM.
        
        Args:
            current_statement: Current hypothesis statement
            past_statement: Past hypothesis statement
            connection_type: Type of connection
            
        Returns:
            Contextual note
        """
        prompt = f"""
        Task: Generate a brief context note explaining the relationship between these two statements.
        
        Current statement: "{current_statement}"
        Past statement: "{past_statement}"
        Connection type: {connection_type}
        
        Create a concise note (max 100 characters) that helps contextualize the current statement in relation to the past finding.
        Start with "Similar to previous finding:" or "Builds upon previous insight:"
        """
        
        try:
            context_note = generate_text(prompt, temperature=0.3)
            
            # Ensure note is not too long
            if context_note and len(context_note) > 120:
                context_note = context_note[:117] + "..."
                
            # If LLM fails, provide a fallback
            if not context_note:
                return f"Similar to previous finding: {past_statement[:100]}..."
                
            return context_note
            
        except Exception as e:
            self.logger.warning(f"Error generating context note: {str(e)}")
            return f"Similar to previous finding: {past_statement[:100]}..."
    
    def analyze(self, data):
        """
        Analyze proximity between evolved outputs to check for redundancy, similarity, or novelty.
        """
        print(f"[DEBUG] ProximityAgent received data type: {type(data)}")
        
        # Handle different input types
        if isinstance(data, tuple):
            # Extract properly formatted data from tuple
            if len(data) >= 2:
                # If the first element is a list, use it
                if isinstance(data[0], list):
                    items = data[0]
                # If the first element is a dict with relevant keys, extract items
                elif isinstance(data[0], dict) and "results" in data[0]:
                    items = data[0].get("results", [])
                else:
                    items = []
            else:
                items = []
        elif isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "results" in data:
            items = data.get("results", [])
        else:
            print("[WARNING] Unexpected data format in ProximityAgent. Using fallback.")
            return {"proximity_results": [{"item": {"item": [], "proximity_score": 0.0}, "review_score": 0.0}]}

        # NEW: Attempt to retrieve related past analogies from MCPS
        past_analogies = []
        try:
            # Try to extract a query from the data for analogy retrieval
            query = ""
            if isinstance(data, dict):
                query = data.get("query", "")
            elif items and isinstance(items[0], dict):
                # Try to extract query from first item
                if "statement" in items[0]:
                    query = items[0]["statement"]
                elif "text" in items[0]:
                    query = items[0]["text"]
            
            if query:
                past_analogies = self.get_past_analogies(query, limit=5)
        except Exception as e:
            self.logger.error(f"Error retrieving past analogies in analyze method: {str(e)}")
        
        # Calculate proximity scores for each item
        proximity_results = []
        for item in items:
            # NEW: Include influence from past analogies
            analogy_influence = 0.0
            if past_analogies and isinstance(item, dict):
                item_text = item.get("statement", item.get("text", ""))
                for analogy in past_analogies:
                    analogy_data = analogy.get("data", {})
                    if isinstance(analogy_data, str):
                        try:
                            analogy_data = json.loads(analogy_data)
                        except:
                            analogy_data = {"statement": analogy_data}
                    
                    analogy_text = analogy_data.get("statement", "")
                    if analogy_text and item_text:
                        similarity = self._calculate_fallback_similarity(item_text, analogy_text)
                        analogy_influence = max(analogy_influence, similarity)
            
            # Process each item
            result = {
                "item": item, 
                "proximity_score": analogy_influence,
                "has_past_analogies": analogy_influence > 0.3
            }
            proximity_results.append(result)

        # Handle empty case
        if not proximity_results:
            proximity_results = [{"item": {"item": [], "proximity_score": 0.0}, "review_score": 0.0}]

        return {"proximity_results": proximity_results}