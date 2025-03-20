import time
import random
import requests
import json
from typing import Dict, Any, List, Optional, Tuple, Set

from .base_agent import BaseAgent
from web.google_search_wrapper import SearchAPI
from web.scraper import WebScraper
from utils.logger import get_logger

class EvolutionAgent(BaseAgent):
    """
    Evolution Agent refines hypotheses based on reflection results, ranking scores,
    and additional targeted web data to improve their quality and relevance.
    """
    
    def __init__(self, web_scraper: WebScraper, search_api: SearchAPI, mcps_url: str = "http://localhost:8000"):
        """
        Initialize the Evolution Agent.
        
        Args:
            web_scraper: Web scraper instance for extracting data
            search_api: Search API instance for web queries
            mcps_url: URL for the Model Context Protocol Server
        """
        super().__init__("evolution", "Evolution Agent")
        self.web_scraper = web_scraper
        self.search_api = search_api
        self.mcps_url = mcps_url
        self.required_context_keys = ["query", "ranked_hypotheses", "reflection_results", "cycle", "session_id"]
        self.logger = get_logger(__name__)
    
    def process(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Refine hypotheses based on reflection results and ranking.
        
        Args:
            context: Current context containing ranked hypotheses
            
        Returns:
            Updated context with evolved hypotheses
        """
        start_time = time.time()
        success = False
        
        try:
            # Validate context
            is_valid, error_msg = self.validate_context(context, self.required_context_keys)
            if not is_valid:
                self.logger.error(f"Context validation failed: {error_msg}")
                raise ValueError(error_msg)
            
            ranked_hypotheses = context["ranked_hypotheses"]
            reflection_results = context["reflection_results"]
            query = context["query"]
            cycle = context["cycle"]
            session_id = context["session_id"]
            
            # Create a mapping of reflection results by hypothesis ID
            reflection_map = {r["hypothesis_id"]: r for r in reflection_results}
            
            self.logger.info(f"Evolving {len(ranked_hypotheses)} hypotheses (Cycle {cycle})")
            
            # Select hypotheses to evolve
            hypotheses_to_evolve = self._select_hypotheses_to_evolve(ranked_hypotheses)
            
            # Evolve selected hypotheses
            evolved_hypotheses, evolution_details = self.evolve(ranked_hypotheses, hypotheses_to_evolve, reflection_map, query, cycle)
            
            # Update context with evolved hypotheses
            context["evolved_hypotheses"] = evolved_hypotheses
            context["evolution_details"] = evolution_details
            context["evolution_timestamp"] = time.time()
            
            # Send evolved hypotheses to MCPS
            self._update_mcps(evolved_hypotheses, evolution_details, session_id)
            
            success = True
            self.logger.info(f"Evolved {len(hypotheses_to_evolve)} hypotheses and updated MCPS")
            
        except Exception as e:
            self.logger.error(f"Error in Evolution Agent: {str(e)}")
            if "evolved_hypotheses" not in context and "ranked_hypotheses" in context:
                context["evolved_hypotheses"] = context["ranked_hypotheses"]
        
        # Update metrics
        processing_time = time.time() - start_time
        self.update_metrics(processing_time, success)
        
        return context
    
    def _update_mcps(self, evolved_hypotheses: List[Dict[str, Any]], 
                    evolution_details: List[Dict[str, Any]], 
                    session_id: str) -> None:
        """
        Update the Model Context Protocol Server with evolved hypotheses.
        
        Args:
            evolved_hypotheses: List of evolved hypotheses
            evolution_details: Details about the evolution process
            session_id: Current session ID
        """
        for hypothesis in evolved_hypotheses:
            # Only update evolved hypotheses (those with parent_id)
            if "parent_id" in hypothesis:
                try:
                    # Find the matching evolution detail
                    detail = next((d for d in evolution_details if d["evolved_id"] == hypothesis["id"]), None)
                    
                    # Prepare data for MCPS update
                    update_data = {
                        "data": {
                            "statement": hypothesis["statement"],
                            "confidence": hypothesis["confidence"],
                            "evolution_cycle": hypothesis.get("evolution_cycle", 0),
                            "evolution_reason": detail["evolution_reason"] if detail else "Hypothesis evolved"
                        },
                        "relevance": min(1.0, 0.7 + (hypothesis.get("confidence", 0.5) * 0.3))  # Scale relevance based on confidence
                    }
                    
                    # Send PUT request to update the hypothesis in MCPS
                    item_id = hypothesis["parent_id"]  # Original hypothesis ID
                    response = requests.put(
                        f"{self.mcps_url}/context/{item_id}",
                        json=update_data,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        self.logger.info(f"Successfully updated hypothesis {item_id} in MCPS")
                    else:
                        self.logger.warning(f"Failed to update hypothesis {item_id} in MCPS: {response.status_code}, {response.text}")
                        
                        # If the item doesn't exist in MCPS, create a new one
                        if response.status_code == 404:
                            self._create_new_hypothesis_in_mcps(hypothesis, detail, session_id)
                            
                except Exception as e:
                    self.logger.error(f"Error updating MCPS for hypothesis {hypothesis['id']}: {str(e)}")
    
    def _create_new_hypothesis_in_mcps(self, hypothesis: Dict[str, Any], 
                                      detail: Dict[str, Any], 
                                      session_id: str) -> None:
        """
        Create a new hypothesis entry in MCPS if update fails.
        
        Args:
            hypothesis: The evolved hypothesis
            detail: Evolution details
            session_id: Current session ID
        """
        try:
            # Prepare data for new hypothesis
            new_data = {
                "session_id": session_id,
                "type": "evolved_hypothesis",
                "data": {
                    "id": hypothesis["id"],
                    "parent_id": hypothesis.get("parent_id"),
                    "statement": hypothesis["statement"],
                    "confidence": hypothesis["confidence"],
                    "sources": hypothesis.get("sources", []),
                    "evolution_cycle": hypothesis.get("evolution_cycle", 0),
                    "original_statement": detail["original_statement"] if detail else "",
                    "evolution_reason": detail["evolution_reason"] if detail else "Hypothesis evolved"
                },
                "relevance": min(1.0, 0.7 + (hypothesis.get("confidence", 0.5) * 0.3)),  # Scale relevance based on confidence
                "relationships": {
                    "parent": hypothesis.get("parent_id", "")
                }
            }
            
            # Send POST request to create new hypothesis in MCPS
            response = requests.post(
                f"{self.mcps_url}/context",
                json=new_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                self.logger.info(f"Successfully created new evolved hypothesis {hypothesis['id']} in MCPS")
            else:
                self.logger.warning(f"Failed to create new hypothesis in MCPS: {response.status_code}, {response.text}")
                
        except Exception as e:
            self.logger.error(f"Error creating new hypothesis in MCPS: {str(e)}")
    
    def _select_hypotheses_to_evolve(self, ranked_hypotheses: List[Dict[str, Any]]) -> List[str]:
        """
        Select which hypotheses to evolve based on their ranking.
        
        Args:
            ranked_hypotheses: List of ranked hypotheses
            
        Returns:
            List of hypothesis IDs to evolve
        """
        # Always evolve the top hypothesis
        to_evolve = []
        
        if ranked_hypotheses:
            # Always include the top hypothesis
            to_evolve.append(ranked_hypotheses[0]["id"])
            
            # Include some lower-ranked hypotheses with good potential
            for hyp in ranked_hypotheses[1:]:
                # Criteria: Good evidence score but lower overall score (room for improvement)
                scores = hyp.get("scores", {})
                evidence_score = scores.get("evidence", 0)
                overall_score = hyp.get("overall_score", 0)
                
                if evidence_score > 0.6 and overall_score < 8.0:
                    # Good evidence but needs improvement
                    to_evolve.append(hyp["id"])
                    
                # Limit to top 3 hypotheses
                if len(to_evolve) >= 3:
                    break
        
        return to_evolve
    
    def _refine_hypothesis(self, hypothesis: Dict[str, Any], reflection: Dict[str, Any], 
                         query: str, cycle: int) -> str:
        """
        Refine a hypothesis based on reflection results and additional web data.
        
        Args:
            hypothesis: Original hypothesis
            reflection: Reflection results for this hypothesis
            query: Original query
            cycle: Current cycle number
            
        Returns:
            Refined hypothesis statement
        """
        statement = hypothesis["statement"]
        
        # Extract issues from reflection
        issues = []
        if not reflection["is_coherent"]:
            issues.append("coherence")
        if not reflection["has_supporting_evidence"]:
            issues.append("evidence")
        if reflection["contradictions"]:
            issues.append("contradictions")
        
        # Address different issues with different strategies
        if "coherence" in issues:
            # Make the statement more coherent
            statement = self._improve_coherence(statement)
            
        if "evidence" in issues or "contradictions" in issues:
            # Perform targeted search to gather more evidence
            search_terms = self._generate_targeted_search_terms(statement, query)
            additional_data = self._gather_additional_data(search_terms)
            
            # Use additional data to refine the hypothesis
            statement = self._incorporate_evidence(statement, additional_data, reflection)
        
        # If no specific issues, but we're in later cycles, make hypothesis more specific
        if cycle > 1 and not issues:
            statement = self._make_more_specific(statement, query)
        
        return statement
    
    def _improve_coherence(self, statement: str) -> str:
        """Improve the coherence of a hypothesis statement."""
        # Simplify complex statements
        if len(statement.split()) > 20:
            # Break into parts and reconstruct
            parts = statement.split(",")
            if len(parts) > 2:
                # Keep main part and the most specific detail
                longest_part = max(parts, key=len)
                statement = longest_part.strip()
                
                # Add clarifying phrases
                clarifiers = ["specifically", "in particular", "notably", "especially"]
                statement = f"{statement}, {random.choice(clarifiers)}"
        
        # Add logical connectors if missing
        logical_connectors = ["because", "therefore", "consequently", "as a result"]
        if not any(connector in statement.lower() for connector in logical_connectors):
            # Append a logical connector to make causality clearer
            statement += f" {random.choice(['because', 'which'])}"
        
        return statement
    
    def _generate_targeted_search_terms(self, statement: str, query: str) -> List[str]:
        """Generate targeted search terms to gather additional evidence."""
        # Extract key terms from statement
        words = statement.lower().split()
        key_terms = [word for word in words if len(word) > 4 and word not in 
                    ["could", "would", "should", "might", "because", "therefore"]]
        
        # Combine with query terms
        query_terms = query.lower().split()
        
        # Generate search terms
        search_terms = []
        
        # Evidence-focused search terms
        search_terms.append(f"evidence {' '.join(key_terms[:2])} {query_terms[0]}")
        
        # Research-focused search terms
        search_terms.append(f"research {' '.join(key_terms[:2])} {query_terms[0]}")
        
        # Example-focused search terms
        search_terms.append(f"example {' '.join(key_terms[:2])} {query_terms[0]}")
        
        return search_terms
    
    def _gather_additional_data(self, search_terms: List[str]) -> List[Dict[str, str]]:
        """Gather additional data using targeted search terms."""
        additional_data = []
        
        for term in search_terms:
            try:
                # Search for additional information
                search_results = self.search_api.search(term, max_results=2)
                
                for result in search_results:
                    try:
                        # Extract data from search result
                        extracted = self.web_scraper.scrape(result["url"])
                        if extracted:
                            additional_data.append({
                                "source": result["url"],
                                "title": result["title"],
                                "content": extracted["content"][:500]  # Limit content size
                            })
                    except Exception as e:
                        self.logger.warning(f"Error scraping {result['url']}: {str(e)}")
            except Exception as e:
                self.logger.warning(f"Error searching for '{term}': {str(e)}")
        
        return additional_data
    
    def _incorporate_evidence(self, statement: str, additional_data: List[Dict[str, str]], 
                            reflection: Dict[str, Any]) -> str:
        """Incorporate additional evidence into the hypothesis."""
        if not additional_data:
            return statement
        
        # Extract relevant sentences from additional data
        relevant_sentences = []
        
        # Extract keywords from statement
        statement_words = set(statement.lower().split())
        
        for data in additional_data:
            content = data["content"]
            sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 10]
            
            for sentence in sentences:
                # Check if sentence is relevant to statement
                sentence_words = set(sentence.lower().split())
                overlap = len(statement_words.intersection(sentence_words))
                
                if overlap >= 2 or any(word in sentence.lower() for word in statement_words if len(word) > 5):
                    relevant_sentences.append(sentence)
        
        # Select the most relevant sentence
        if relevant_sentences:
            # Choose the sentence with the highest word overlap
            best_sentence = max(relevant_sentences, 
                               key=lambda s: len(set(s.lower().split()).intersection(statement_words)))
            
            # Incorporate the evidence
            evidence_phrases = [
                f"Research indicates that",
                f"Evidence suggests that",
                f"Studies have shown that",
                f"According to research,"
            ]
            
            # If there are contradictions, address them
            if reflection["contradictions"]:
                # Create a more nuanced statement that acknowledges contradictions
                return f"{random.choice(evidence_phrases)} {statement}, although some limitations exist."
            else:
                # Strengthen the statement with evidence
                return f"{random.choice(evidence_phrases)} {statement}."
        
        return statement
    
    def _make_more_specific(self, statement: str, query: str) -> str:
        """Make a hypothesis more specific in later cycles."""
        # Add qualifiers or specific examples
        specificity_phrases = [
            f"especially in the context of {query}",
            f"particularly when considering {query}",
            f"with notable impact on {query}",
            f"which is critical for {query}"
        ]
        
        # Check if statement already ends with punctuation
        if statement.endswith(('.', '!', '?')):
            statement = statement[:-1]
        
        return f"{statement}, {random.choice(specificity_phrases)}."
    
    def _get_evolution_reason(self, hypothesis: Dict[str, Any], reflection: Dict[str, Any]) -> str:
        """Generate a reason explaining why and how the hypothesis was evolved."""
        reasons = []
        
        if not reflection["is_coherent"]:
            reasons.append("improved logical coherence")
        
        if not reflection["has_supporting_evidence"]:
            reasons.append("added supporting evidence")
        
        if reflection["contradictions"]:
            reasons.append("addressed contradictions")
        
        if not reasons:
            if hypothesis.get("overall_score", 0) < 7.0:
                reasons.append("enhanced overall quality")
            else:
                reasons.append("refined with more specific details")
        
        return "Evolution based on " + " and ".join(reasons)
    
    def evolve(self, ranked_hypotheses: List[Dict[str, Any]], hypotheses_to_evolve: List[str], 
              reflection_map: Dict[str, Dict[str, Any]], query: str, cycle: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Evolves the given hypotheses by refining them based on reflection results.
        
        Args:
            ranked_hypotheses: List of ranked hypotheses.
            hypotheses_to_evolve: List of hypothesis IDs to evolve.
            reflection_map: Mapping of reflection results by hypothesis ID.
            query: Original query.
            cycle: Current evolution cycle.
            
        Returns:
            A tuple containing the evolved hypotheses list and evolution details.
        """
        evolved_hypotheses = []
        evolution_details = []
        
        for hypothesis in ranked_hypotheses:
            hypothesis_id = hypothesis["id"]
            reflection = reflection_map.get(hypothesis_id)
            
            if not reflection:
                self.logger.warning(f"No reflection found for hypothesis {hypothesis_id}")
                evolved_hypotheses.append(hypothesis)  # Keep unchanged
                continue
            
            if hypothesis_id in hypotheses_to_evolve:
                # Gather more information through targeted search
                refined_statement = self._refine_hypothesis(hypothesis, reflection, query, cycle)
                
                # Create evolved hypothesis
                evolved_hypothesis = {
                    "id": f"{hypothesis_id}-evolved-{cycle}",
                    "parent_id": hypothesis_id,
                    "statement": refined_statement,
                    "confidence": min(1.0, hypothesis.get("confidence", 0.5) + 0.1),
                    "sources": hypothesis.get("sources", []),
                    "evolved_at": time.time(),
                    "evolution_cycle": cycle
                }
                
                # Record evolution details
                detail = {
                    "original_id": hypothesis_id,
                    "evolved_id": evolved_hypothesis["id"],
                    "original_statement": hypothesis["statement"],
                    "evolved_statement": refined_statement,
                    "evolution_reason": self._get_evolution_reason(hypothesis, reflection)
                }
                evolution_details.append(detail)
                
                evolved_hypotheses.append(evolved_hypothesis)
            else:
                # Keep unchanged
                evolved_hypotheses.append(hypothesis)
        
        return evolved_hypotheses, evolution_details