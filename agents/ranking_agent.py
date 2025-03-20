"""
Ranking Agent for The Second Mind
Scores hypothesis outputs based on reflection results, web data, and Gemini LLM.
"""
import time
from typing import Dict, Any, List, Tuple, Union
import uuid
from .base_agent import BaseAgent
from utils.gemini_client import generate_text
from utils.logger import get_logger
import requests

class RankingAgent(BaseAgent):
    """
    Ranking Agent scores hypotheses based on various criteria including
    coherence, supporting evidence, relevance, and LLM-based credibility assessment.
    Integrated with the Context Protocol Server for storing and retrieving ranking results.
    """
   
    def __init__(self, context_server_url="http://localhost:8000"):
        """
        Initialize the Ranking Agent with Context Protocol Server integration.
        
        Args:
            context_server_url: URL of the Context Protocol Server instance
        """
        super().__init__("ranking", "Ranking Agent")
        self.required_context_keys = ["query", "hypotheses", "reflection_results", "web_data"]
        self.context_server_url = context_server_url
        self.logger = get_logger(__name__)
        
        # Scoring weights for different criteria
        self.weights = {
            "coherence": 0.20,
            "evidence": 0.25,
            "relevance": 0.20,
            "specificity": 0.10,
            "novelty": 0.10,
            "llm_credibility": 0.15  # Weight for LLM-based credibility scoring
        }
    
    def process(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Rank and score the hypotheses based on reflection results, web data, and LLM assessment.
        Store results in the Context Protocol Server.
        
        Args:
            context: Current context containing hypotheses and reflection results
            
        Returns:
            Updated context with ranking results
        """
        start_time = time.time()
        success = False
        session_id = context.get("session_id")
        
        # Generate a session ID if not available
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            context["session_id"] = session_id
            self.logger.info(f"Generated new session ID: {session_id}")
        
        try:
            # Validate context
            is_valid, error_msg = self.validate_context(context, self.required_context_keys)
            if not is_valid:
                self.logger.error(f"Context validation failed: {error_msg}")
                raise ValueError(error_msg)
            
            # Handle case where input is a tuple
            if isinstance(context, tuple) and len(context) > 0:
                context = context[0]  # Extract the dictionary from the tuple
            
            # First, check if we have previous ranking results in the context server
            previous_rankings, item_id = self._get_previous_rankings(session_id, context.get("query", ""))
            
            # If we have previous rankings, consider them in the current ranking process
            if previous_rankings:
                self.logger.info(f"Found previous rankings for session {session_id} with item ID: {item_id}")
                # Logic to incorporate previous rankings could go here
            
            # Perform ranking
            hypotheses = context.get("hypotheses", [])
            reflection_results = context.get("reflection_results", [])
            web_data = context.get("web_data", [])
            query = context.get("query", "")
            
            self.logger.info(f"Ranking {len(hypotheses)} hypotheses")
            
            # Create a mapping of reflection results by hypothesis ID
            reflection_map = {r["hypothesis_id"]: r for r in reflection_results}
            
            # Score and rank hypotheses
            ranked_hypotheses = []
            for hypothesis in hypotheses:
                hypothesis_id = hypothesis.get("id")
                reflection = reflection_map.get(hypothesis_id)
                
                if not reflection:
                    self.logger.warning(f"No reflection found for hypothesis {hypothesis_id}")
                    # Create a default reflection to avoid errors
                    reflection = {
                        "hypothesis_id": hypothesis_id,
                        "coherence_score": 0.5,
                        "supporting_facts": [],
                        "contradictions": []
                    }
                
                # Calculate scores for different criteria
                scores = self._calculate_scores(hypothesis, reflection, web_data, query)
                
                # Calculate overall score (weighted average)
                overall_score = sum(self.weights[criterion] * score for criterion, score in scores.items())
                
                # Round to 1 decimal place (0-10 scale)
                overall_score = round(overall_score * 10, 1)
                
                ranked_hypothesis = {
                    **hypothesis,
                    "scores": scores,
                    "overall_score": overall_score,
                    "rank_explanation": self._generate_explanation(scores, reflection)
                }
                
                ranked_hypotheses.append(ranked_hypothesis)
            
            # Sort hypotheses by overall score (descending)
            ranked_hypotheses.sort(key=lambda h: h["overall_score"], reverse=True)
            
            # Assign ranks
            for i, hyp in enumerate(ranked_hypotheses):
                hyp["rank"] = i + 1
            
            # Update context with ranked hypotheses
            context["ranked_hypotheses"] = ranked_hypotheses
            context["ranking_timestamp"] = time.time()
            
            # Identify top hypothesis
            if ranked_hypotheses:
                context["top_hypothesis"] = ranked_hypotheses[0]
                
            # Store ranking results in Context Protocol Server
            if item_id:
                # Use PUT to update existing ranking
                self._update_ranking_results(item_id, ranked_hypotheses, query)
            else:
                # Use POST to create new ranking
                self._store_ranking_results(session_id, ranked_hypotheses, query)
                
            success = True
            self.logger.info(f"Completed ranking of {len(ranked_hypotheses)} hypotheses")
            
        except Exception as e:
            self.logger.error(f"Error in Ranking Agent: {str(e)}")
            if "ranked_hypotheses" not in context and "hypotheses" in context:
                # Simple fallback ranking
                context["ranked_hypotheses"] = [{
                    **h, 
                    "overall_score": 5.0,
                    "rank": i + 1,
                    "scores": {k: 0.5 for k in self.weights.keys()},
                    "rank_explanation": "Fallback ranking due to processing error"
                } for i, h in enumerate(context["hypotheses"])]
        
        # Update metrics
        processing_time = time.time() - start_time
        self.update_metrics(processing_time, success)
        
        return context
    
    def _get_previous_rankings(self, session_id: str, query: str) -> Tuple[List[Dict[str, Any]], Union[str, None]]:
        """
        Retrieve previous ranking results from the Context Protocol Server.
        
        Args:
            session_id: Current session ID
            query: Current query
            
        Returns:
            Tuple containing:
                - List of previous ranking results, if available
                - Item ID for the most relevant ranking, or None if not found
        """
        try:
            # First try to get by session ID
            response = requests.get(
                f"{self.context_server_url}/context",
                params={"session_id": session_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("context"):
                    # Extract ranking results from session context
                    session_context = data.get("context", {})
                    items = session_context.get("items", {})
                    
                    # Find items with type "ranking_results"
                    ranking_items = []
                    item_id = None
                    
                    for item_id_key, item in items.items():
                        if item.get("type") == "ranking_results":
                            ranking_items.append(item)
                            # Store the most recent item ID
                            if item_id is None or item.get("timestamp", 0) > items.get(item_id, {}).get("timestamp", 0):
                                item_id = item_id_key
                    
                    if ranking_items:
                        return ranking_items, item_id
            
            # If no session-based results, try to find similar based on query
            if query:
                response = requests.get(
                    f"{self.context_server_url}/context/search",
                    params={"query": query}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success" and data.get("results"):
                        # Filter results by type "ranking_results"
                        ranking_results = []
                        item_id = None
                        
                        for result in data.get("results", []):
                            if result.get("type") == "ranking_results":
                                ranking_results.append(result)
                                # Store the most relevant item ID
                                if item_id is None or result.get("relevance", 0) > data.get("results", []).get(item_id, {}).get("relevance", 0):
                                    item_id = result.get("id")
                        
                        if ranking_results:
                            return ranking_results, item_id
            
            return [], None
            
        except Exception as e:
            self.logger.error(f"Error retrieving previous rankings: {str(e)}")
            return [], None
    
    def _store_ranking_results(self, session_id: str, ranked_hypotheses: List[Dict[str, Any]], query: str) -> bool:
        """
        Store new ranking results in the Context Protocol Server using POST.
        
        Args:
            session_id: Current session ID
            ranked_hypotheses: List of ranked hypotheses
            query: Current query
            
        Returns:
            Boolean indicating success
        """
        try:
            # Prepare data for storage
            data = {
                "session_id": session_id,
                "type": "ranking_results",
                "data": {
                    "query": query,
                    "ranked_hypotheses": ranked_hypotheses,
                    "timestamp": time.time()
                },
                "relevance": 1.0,  # High relevance for recent rankings
                "relationships": {
                    "query": query,
                    "top_hypothesis": ranked_hypotheses[0]["id"] if ranked_hypotheses else None
                }
            }
            
            # Send data to Context Protocol Server
            response = requests.post(
                f"{self.context_server_url}/context",
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    self.logger.info(f"Successfully stored ranking results with item ID: {result.get('item_id')}")
                    return True
                else:
                    self.logger.warning(f"Failed to store ranking results: {result.get('message')}")
            else:
                self.logger.warning(f"Failed to store ranking results. Status code: {response.status_code}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error storing ranking results: {str(e)}")
            return False
        
    def _update_ranking_results(self, item_id: str, ranked_hypotheses: List[Dict[str, Any]], query: str) -> bool:
        """
        Update existing ranking results in the Context Protocol Server using PUT.
        
        Args:
            item_id: ID of the existing ranking item to update
            ranked_hypotheses: Updated list of ranked hypotheses
            query: Current query
            
        Returns:
            Boolean indicating success
        """
        try:
            # Prepare data for update
            data = {
                "type": "ranking_results",
                "data": {
                    "query": query,
                    "ranked_hypotheses": ranked_hypotheses,
                    "timestamp": time.time(),
                    "updated": True
                },
                "relevance": 1.0,  # High relevance for recent rankings
                "relationships": {
                    "query": query,
                    "top_hypothesis": ranked_hypotheses[0]["id"] if ranked_hypotheses else None
                }
            }
            
            # Send data to Context Protocol Server using PUT
            response = requests.put(
                f"{self.context_server_url}/context/{item_id}",
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    self.logger.info(f"Successfully updated ranking results with item ID: {item_id}")
                    return True
                else:
                    self.logger.warning(f"Failed to update ranking results: {result.get('message')}")
            else:
                self.logger.warning(f"Failed to update ranking results. Status code: {response.status_code}")
                
                # If PUT fails (e.g., endpoint not supported), fall back to POST
                if response.status_code == 404 or response.status_code == 405:
                    self.logger.info("PUT endpoint not supported. Falling back to POST method.")
                    return self._store_ranking_results(data.get("session_id", ""), ranked_hypotheses, query)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating ranking results: {str(e)}")
            return False
    
    # Rest of the methods remain the same as in your original code
    def _calculate_scores(self, hypothesis: Dict[str, Any], reflection: Dict[str, Any], 
                         web_data: List[Dict[str, Any]], query: str) -> Dict[str, float]:
        """Calculate scores for different criteria."""
        # Extract data
        statement = hypothesis.get("statement", "")
        
        # 1. Coherence score (from reflection)
        coherence_score = reflection.get("coherence_score", 0.5)
        
        # 2. Evidence score
        supporting_facts = reflection.get("supporting_facts", [])
        contradictions = reflection.get("contradictions", [])
        
        # More supporting facts = higher score, contradictions reduce score
        evidence_score = min(1.0, len(supporting_facts) * 0.2) - min(0.5, len(contradictions) * 0.2)
        evidence_score = max(0.1, evidence_score)  # Ensure minimum score of 0.1
        
        # 3. Relevance score (how relevant to the query)
        relevance_score = self._calculate_relevance(statement, query, web_data)
        
        # 4. Specificity score (how specific vs. general)
        specificity_score = self._calculate_specificity(statement)
        
        # 5. Novelty score (how unique compared to web data)
        novelty_score = self._calculate_novelty(statement, web_data)
        
        # 6. LLM credibility score (using Gemini)
        llm_credibility_score = self._calculate_llm_credibility(statement, query, web_data)
        
        return {
            "coherence": coherence_score,
            "evidence": evidence_score,
            "relevance": relevance_score,
            "specificity": specificity_score,
            "novelty": novelty_score,
            "llm_credibility": llm_credibility_score
        }
    
    def _calculate_relevance(self, statement: str, query: str, web_data: List[Dict[str, Any]]) -> float:
        """Calculate relevance score based on query and web data."""
        # Simple approach: check overlap between statement and query terms
        statement_words = set(statement.lower().split())
        query_words = set(query.lower().split())
        
        # Calculate overlap
        overlap = len(statement_words.intersection(query_words)) / max(1, len(query_words))
        
        # Check if key terms from query appear in web data
        query_terms = [w for w in query.lower().split() if len(w) > 3]
        term_appearances = {}
        
        for term in query_terms:
            term_appearances[term] = 0
            for data in web_data:
                content = data.get("content", "")
                if isinstance(content, str) and term in content.lower():
                    term_appearances[term] += 1
        
        # Calculate how many of the query terms that appear in web data also appear in the statement
        query_term_coverage = 0
        relevant_terms = [term for term, count in term_appearances.items() if count > 0]
        
        if relevant_terms:
            statement_lower = statement.lower()
            covered_terms = [term for term in relevant_terms if term in statement_lower]
            query_term_coverage = len(covered_terms) / len(relevant_terms)
        
        # Combine both factors (basic overlap and coverage of relevant terms)
        relevance_score = 0.4 * overlap + 0.6 * query_term_coverage
        
        return min(1.0, relevance_score)
    
    def _calculate_specificity(self, statement: str) -> float:
        """Calculate specificity score based on statement details."""
        # Simple heuristics:
        # 1. Length (longer usually = more specific)
        length_factor = min(1.0, len(statement) / 100)
        
        # 2. Presence of numbers (indicates specificity)
        has_numbers = any(c.isdigit() for c in statement)
        number_factor = 0.2 if has_numbers else 0
        
        # 3. Specific words (technical terms, measurements, etc.)
        specificity_indicators = [
            "specific", "precisely", "exactly", "particularly",
            "uniquely", "distinct", "specialized", "detailed"
        ]
        indicator_factor = 0.1 * sum(1 for word in specificity_indicators if word in statement.lower())
        
        specificity_score = 0.5 * length_factor + 0.3 * number_factor + 0.2 * min(1.0, indicator_factor)
        return min(1.0, specificity_score)
    
    def _calculate_novelty(self, statement: str, web_data: List[Dict[str, Any]]) -> float:
        """Calculate novelty score based on uniqueness compared to web data."""
        if not web_data:
            return 0.5  # Neutral score if no web data
        
        # Calculate similarity to each web content
        similarities = []
        statement_words = set(statement.lower().split())
        
        for data in web_data:
            content = data.get("content", "")
            if not isinstance(content, str):
                continue
                
            content_words = set(content.lower().split())
            
            # Jaccard similarity
            intersection = len(statement_words.intersection(content_words))
            union = len(statement_words.union(content_words))
            
            similarity = intersection / max(1, union)
            similarities.append(similarity)
        
        # Average similarity
        if not similarities:
            return 0.5  # Neutral score if no valid comparisons
            
        avg_similarity = sum(similarities) / len(similarities)
        
        # Novelty is inverse of similarity
        novelty_score = 1.0 - avg_similarity
        
        return novelty_score

    def _calculate_llm_credibility(self, statement: str, query: str, web_data: List[Dict[str, Any]]) -> float:
        """
        Calculate credibility score using Gemini LLM.
        
        Args:
            statement: The hypothesis statement
            query: Original query
            web_data: Available web data for context
            
        Returns:
            Float score between 0-1 representing credibility
        """
        try:
            # Prepare web data context (limit to prevent token overflow)
            web_context = ""
            for i, data in enumerate(web_data):
                if i >= 3:  # Limit to first 3 web results
                    break
                    
                title = data.get('title', 'Untitled')
                content = data.get('content', '')
                
                if not isinstance(content, str):
                    continue
                    
                web_context += f"Source {i+1}: {title}\n"
                web_context += f"{content[:500]}...\n\n"  # Truncate long content
            
            # Create prompt for Gemini
            prompt = f"""
            Task: Evaluate the credibility and accuracy of the following statement in response to a query.
            
            Query: {query}
            
            Statement to evaluate: "{statement}"
            
            Web data context:
            {web_context}
            
            Please evaluate the credibility of the statement based on:
            1. Factual accuracy (compared to web data)
            2. Logical consistency
            3. Alignment with authoritative sources
            4. Presence of verifiable claims
            
            Return a single score between 0.0 and 1.0, where:
            - 0.0 = Completely unreliable/not credible
            - 1.0 = Highly credible/reliable
            
            Only provide the numerical score without any explanation.
            """
            
            # Call Gemini API
            response = generate_text(prompt, temperature=0.2)
            
            # Extract score from response
            if response:
                # Try to extract a float from the response
                try:
                    score = float(response.strip())
                    # Ensure score is within 0-1 range
                    score = max(0.0, min(1.0, score))
                    return score
                except ValueError:
                    self.logger.warning(f"Could not parse credibility score from LLM response: {response}")
                    return 0.5  # Neutral score if parsing fails
            
            return 0.5  # Neutral score if no response
            
        except Exception as e:
            self.logger.error(f"Error in LLM credibility calculation: {str(e)}")
            return 0.5  # Neutral score on error
    
    def _generate_explanation(self, scores: Dict[str, float], reflection: Dict[str, Any]) -> str:
        """Generate explanation for the ranking."""
        explanation_parts = []
        
        # Coherence explanation
        if scores["coherence"] >= 0.8:
            explanation_parts.append("The hypothesis is logically coherent")
        elif scores["coherence"] >= 0.5:
            explanation_parts.append("The hypothesis is somewhat coherent")
        else:
            explanation_parts.append("The hypothesis lacks logical coherence")
        
        # Evidence explanation
        supporting_facts = reflection.get("supporting_facts", [])
        contradictions = reflection.get("contradictions", [])
        
        if len(supporting_facts) > 3:
            explanation_parts.append(f"strongly supported by {len(supporting_facts)} pieces of evidence")
        elif len(supporting_facts) > 0:
            explanation_parts.append(f"supported by {len(supporting_facts)} pieces of evidence")
        else:
            explanation_parts.append("lacks supporting evidence")
            
        if contradictions:
            explanation_parts.append(f"has {len(contradictions)} contradicting points")
        
        # Relevance explanation
        if scores["relevance"] >= 0.8:
            explanation_parts.append("highly relevant to the query")
        elif scores["relevance"] >= 0.5:
            explanation_parts.append("moderately relevant to the query")
        else:
            explanation_parts.append("not very relevant to the query")
        
        # LLM credibility explanation
        if scores["llm_credibility"] >= 0.8:
            explanation_parts.append("assessed as highly credible by LLM")
        elif scores["llm_credibility"] >= 0.6:
            explanation_parts.append("assessed as credible by LLM")
        elif scores["llm_credibility"] >= 0.4:
            explanation_parts.append("has mixed credibility according to LLM")
        else:
            explanation_parts.append("assessed as potentially unreliable by LLM")
        
        # Combine explanation parts
        explanation = ". ".join(explanation_parts)
        return explanation.capitalize() + "."
    
    def rank(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Rank and score hypotheses based on given context.
        
        Args:
            context: Context containing hypotheses and necessary data.
        
        Returns:
            List of ranked hypotheses.
        """
        hypotheses = context["hypotheses"]
        reflection_results = context["reflection_results"]
        web_data = context["web_data"]
        query = context["query"]
        
        self.logger.info(f"Ranking {len(hypotheses)} hypotheses")
        
        # Create a mapping of reflection results by hypothesis ID
        reflection_map = {r["hypothesis_id"]: r for r in reflection_results}
        
        ranked_hypotheses = []
        for hypothesis in hypotheses:
            reflection = reflection_map.get(hypothesis["id"])
            if not reflection:
                self.logger.warning(f"No reflection found for hypothesis {hypothesis['id']}")
                continue
            
            # Calculate scores for different criteria
            scores = self._calculate_scores(hypothesis, reflection, web_data, query)
            
            # Calculate overall score (weighted average)
            overall_score = sum(self.weights[criterion] * score for criterion, score in scores.items())
            
            # Round to 1 decimal place (0-10 scale)
            overall_score = round(overall_score * 10, 1)
            
            ranked_hypothesis = {
                **hypothesis,
                "scores": scores,
                "overall_score": overall_score,
                "rank_explanation": self._generate_explanation(scores, reflection)
            }
            
            ranked_hypotheses.append(ranked_hypothesis)
        
        # Sort hypotheses by overall score (descending)
        ranked_hypotheses.sort(key=lambda h: h["overall_score"], reverse=True)
        
        # Assign ranks
        for i, hyp in enumerate(ranked_hypotheses):
            hyp["rank"] = i + 1
        
        return ranked_hypotheses