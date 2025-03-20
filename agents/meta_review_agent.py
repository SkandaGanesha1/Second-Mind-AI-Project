import time
from datetime import datetime
import logging
import json
from agents.base_agent import BaseAgent
from utils.gemini_client import generate_text
from typing import Dict, Any, List, Tuple
import uuid


class MetaReviewAgent(BaseAgent):
    """
    Meta Review Agent evaluates the entire process flow and generates feedback
    for system improvement. This agent acts as a quality control mechanism that
    ensures continuous refinement of the overall system.
    """
    
    def __init__(self, context_manager, storage):
        """
        Initialize the Meta Review Agent.

        Args:
            context_manager: The context manager for accessing and updating shared context
            storage: The storage system for retrieving historical data
        """
        super().__init__("meta_review", storage)  # Pass only "meta_review" and storage
        self.context_manager = context_manager  # Store context_manager separately
        
        # Add MCPS configuration
        self.mcps_host = "localhost"  # Default, should be configurable
        self.mcps_port = 8000  # Default, should be configurable
        self.mcps_base_url = f"http://{self.mcps_host}:{self.mcps_port}"

        self.metrics = {
            "cycle_duration": [],
            "agent_performance": {},
            "web_data_quality": [],
            "hypothesis_improvement": []
        }
        self.logger = logging.getLogger(__name__)

    
    def process(self, task_data):
        """
        Evaluate the entire research cycle and provide feedback for improvement.
        
        Args:
            task_data: Dictionary containing cycle information, agent outputs, and timings
            
        Returns:
            Dictionary with feedback, recommendations, and process metrics
        """
        self.logger.info("Meta Review Agent processing cycle evaluation")
        start_time = time.time()
        
        # Safely extract cycle data with default values
        cycle_id = task_data.get("cycle_id", 0)
        cycle_data = task_data.get("cycle_data", {})
        query = task_data.get("query", "")
        
        # Safely get previous cycles with error handling
        try:
            previous_cycles = self.storage.get_previous_cycles(query, cycle_id)
        except Exception as e:
            self.logger.error(f"Error retrieving previous cycles: {e}")
            previous_cycles = []
        
        # Analyze cycle performance
        try:
            performance_metrics = self._analyze_cycle_performance(cycle_data)
        except Exception as e:
            self.logger.error(f"Error analyzing cycle performance: {e}")
            performance_metrics = {"total_cycle_time": 0, "agent_times": {}, "bottlenecks": [], 
                                "successful_agents": [], "failed_agents": []}
        
        # Evaluate web data quality with error handling
        try:
            web_data_quality = self._evaluate_web_data_quality(cycle_data)
        except Exception as e:
            self.logger.error(f"Error evaluating web data quality: {e}")
            web_data_quality = {"sources_count": 0, "data_freshness": 0, "data_relevance": 0,
                                "data_diversity": 0, "successful_extractions": 0, "failed_extractions": 0}
        
        # Measure hypothesis improvement with error handling
        try:
            hypothesis_improvement = self._measure_hypothesis_improvement(cycle_data, previous_cycles)
        except Exception as e:
            self.logger.error(f"Error measuring hypothesis improvement: {e}")
            hypothesis_improvement = {"current_score": 0, "previous_score": 0, "score_delta": 0,
                                    "complexity_increase": 0, "refinement_count": 0, "improvement_percentage": 0}
        
        # Update metrics history
        self._update_metrics(performance_metrics, web_data_quality, hypothesis_improvement)
        
        # Use Gemini LLM to generate insights and recommendations
        try:
            llm_insights = self._generate_llm_insights(cycle_data, performance_metrics, previous_cycles)
        except Exception as e:
            self.logger.error(f"Error generating LLM insights: {e}")
            llm_insights = {"insights": ["LLM processing failed"], 
                            "recommendations": ["Check LLM service connection"], 
                            "bottlenecks": ["LLM processing"]}
        
        # Prepare meta review result
        meta_review_result = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now().isoformat(),
            "performance_metrics": performance_metrics,
            "web_data_quality": web_data_quality,
            "hypothesis_improvement": hypothesis_improvement,
            "insights": llm_insights.get("insights", []),
            "recommendations": llm_insights.get("recommendations", []),
            "bottlenecks": llm_insights.get("bottlenecks", []),
            "execution_time": time.time() - start_time
        }
        
        # Update context with meta review results
        try:
            # Replace this context_manager.update_context call with a PUT request to the Context Protocol Server
            meta_review_context_data = {
                "session_id": task_data.get("cycle_id", str(uuid.uuid4())),
                "type": "meta_review",
                "data": meta_review_result,
                "relevance": 0.9,  # High relevance for meta insights
                "relationships": {
                    "query": task_data.get("query", ""),
                    "cycle_id": task_data.get("cycle_id", 0)
                }
            }
            
            # Make PUT request to Context Protocol Server
            self._put_meta_insights_to_mcps(meta_review_context_data)
        except Exception as e:
            self.logger.error(f"Error updating context via MCPS: {e}")
        
        # Save meta review to storage with error handling
        try:
            self.storage.save_meta_review(query, cycle_id, meta_review_result)
        except Exception as e:
            self.logger.error(f"Error saving meta review to storage: {e}")
        
        self.logger.info(f"Meta Review completed in {meta_review_result['execution_time']:.2f}s")
        return meta_review_result
    
    def _put_meta_insights_to_mcps(self, context_data):
        """
        Send meta insights to the Model Context Protocol Server using PUT request.
        
        Args:
            context_data: Dictionary containing meta review data to be stored
        """
        try:
            import requests
            
            # Generate a unique item_id if not provided
            item_id = context_data.get("item_id", f"meta_review_{context_data['session_id']}_{uuid.uuid4().hex[:8]}")
            
            # MCPS server URL
            mcps_url = f"http://localhost:8000/context/{item_id}"  # Update with your actual MCPS URL
            
            # Make PUT request to MCPS
            response = requests.put(
                mcps_url,
                json={
                    "data": context_data["data"],
                    "relevance": context_data.get("relevance", 0.9)
                },
                timeout=10  # Add timeout to avoid hanging
            )
            
            if response.status_code == 200:
                self.logger.info(f"Successfully updated meta insights to MCPS with item_id: {item_id}")
                return True
            else:
                self.logger.error(f"Failed to update meta insights to MCPS. Status code: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error in PUT request to MCPS: {e}")
            return False
        
    def _post_meta_insights_to_mcps(self, context_data):
        """
        Create new meta insights in the Model Context Protocol Server using POST request.
        
        Args:
            context_data: Dictionary containing meta review data to be stored
            
        Returns:
            str: Item ID if successful, None otherwise
        """
        try:
            import requests
            
            # MCPS server URL
            mcps_url = "http://localhost:8000/context"  # Update with your actual MCPS URL
            
            # Make POST request to MCPS
            response = requests.post(
                mcps_url,
                json=context_data,
                timeout=10  # Add timeout to avoid hanging
            )
            
            if response.status_code == 200:
                response_data = response.json()
                item_id = response_data.get("item_id")
                self.logger.info(f"Successfully posted meta insights to MCPS with item_id: {item_id}")
                return item_id
            else:
                self.logger.error(f"Failed to post meta insights to MCPS. Status code: {response.status_code}, Response: {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Error in POST request to MCPS: {e}")
            return None
    
    def _analyze_cycle_performance(self, cycle_data):
        """
        Analyze the performance of the current cycle.
        
        Args:
            cycle_data: Dictionary containing cycle information and agent outputs
            
        Returns:
            Dictionary with performance metrics
        """
        performance_metrics = {
            "total_cycle_time": 0,
            "agent_times": {},
            "bottlenecks": [],
            "successful_agents": [],
            "failed_agents": []
        }
        
        # Calculate total cycle time and agent execution times
        agent_outputs = cycle_data.get("agent_outputs", {})
        if not isinstance(agent_outputs, dict):
            self.logger.warning(f"Expected dict for agent_outputs, got {type(agent_outputs)}")
            return performance_metrics
            
        for agent_name, agent_data in agent_outputs.items():
            if isinstance(agent_data, dict) and "execution_time" in agent_data:
                try:
                    exec_time = float(agent_data["execution_time"])
                    performance_metrics["agent_times"][agent_name] = exec_time
                    performance_metrics["total_cycle_time"] += exec_time
                    
                    if agent_data.get("status") == "success":
                        performance_metrics["successful_agents"].append(agent_name)
                    else:
                        performance_metrics["failed_agents"].append(agent_name)
                except (ValueError, TypeError) as e:
                    self.logger.error(f"Error processing execution time for {agent_name}: {e}")
        
        # Identify bottlenecks (agents taking more than 25% of total time)
        total_time = performance_metrics["total_cycle_time"]
        if total_time > 0:
            for agent_name, time_taken in performance_metrics["agent_times"].items():
                if time_taken > 0.25 * total_time:
                    performance_metrics["bottlenecks"].append({
                        "agent": agent_name,
                        "time": time_taken,
                        "percentage": (time_taken / total_time) * 100
                    })
        
        return performance_metrics
    
    def _evaluate_web_data_quality(self, cycle_data):
        """
        Evaluate the quality of web data used in the cycle.
        
        Args:
            cycle_data: Dictionary containing cycle information and web data
            
        Returns:
            Dictionary with web data quality metrics
        """
        web_data_quality = {
            "sources_count": 0,
            "data_freshness": 0,
            "data_relevance": 0,
            "data_diversity": 0,
            "successful_extractions": 0,
            "failed_extractions": 0
        }
        
        web_data = cycle_data.get("web_data", {})
        if not isinstance(web_data, dict):
            self.logger.warning(f"Expected dict for web_data, got {type(web_data)}")
            return web_data_quality
            
        sources = web_data.get("sources", [])
        if not isinstance(sources, list):
            self.logger.warning(f"Expected list for sources, got {type(sources)}")
            return web_data_quality
            
        web_data_quality["sources_count"] = len(sources)
        
        # Count successful and failed extractions
        for source in sources:
            if not isinstance(source, dict):
                continue
                
            if source.get("status") == "success":
                web_data_quality["successful_extractions"] += 1
            else:
                web_data_quality["failed_extractions"] += 1
        
        # Calculate data freshness (average age of sources in days)
        current_time = datetime.now()
        total_age = 0
        valid_timestamps = 0
        
        for source in sources:
            if not isinstance(source, dict):
                continue
                
            timestamp = source.get("timestamp")
            if timestamp:
                try:
                    source_time = datetime.fromisoformat(timestamp)
                    age_days = (current_time - source_time).days
                    total_age += age_days
                    valid_timestamps += 1
                except (ValueError, TypeError):
                    pass
        
        if valid_timestamps > 0:
            web_data_quality["data_freshness"] = total_age / valid_timestamps
        
        # Calculate data relevance (based on keyword matching)
        query = cycle_data.get("query", "")
        if query:
            try:
                query_keywords = set(query.lower().split())
                total_relevance = 0
                content_sources = 0
                
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                        
                    content = source.get("content", "")
                    if content:
                        content_keywords = set(content.lower().split())
                        overlap = len(query_keywords.intersection(content_keywords))
                        if len(query_keywords) > 0:
                            relevance = overlap / len(query_keywords)
                            total_relevance += relevance
                            content_sources += 1
                
                if content_sources > 0:
                    web_data_quality["data_relevance"] = total_relevance / content_sources
            except Exception as e:
                self.logger.error(f"Error calculating data relevance: {e}")
        
        # Calculate data diversity (based on source types)
        try:
            source_types = set()
            for source in sources:
                if isinstance(source, dict):
                    source_types.add(source.get("type", "unknown"))
            
            if web_data_quality["sources_count"] > 0:
                web_data_quality["data_diversity"] = len(source_types) / web_data_quality["sources_count"]
        except Exception as e:
            self.logger.error(f"Error calculating data diversity: {e}")
        
        return web_data_quality
    
    def _measure_hypothesis_improvement(self, cycle_data, previous_cycles):
        """
        Measure the improvement in hypothesis quality across cycles.
        
        Args:
            cycle_data: Dictionary containing cycle information and hypothesis
            previous_cycles: List of previous cycle data
            
        Returns:
            Dictionary with hypothesis improvement metrics
        """
        hypothesis_improvement = {
            "current_score": 0,
            "previous_score": 0,
            "score_delta": 0,
            "complexity_increase": 0,
            "refinement_count": 0,
            "improvement_percentage": 0
        }
        
        # Safely extract current hypothesis
        current_hypothesis = cycle_data.get("hypothesis", {})
        if not isinstance(current_hypothesis, dict):
            self.logger.warning(f"Expected dict for hypothesis, got {type(current_hypothesis)}")
            return hypothesis_improvement
            
        # Get current score safely
        try:
            current_score = float(current_hypothesis.get("score", 0))
            hypothesis_improvement["current_score"] = current_score
        except (ValueError, TypeError):
            self.logger.warning("Invalid hypothesis score format")
            current_score = 0
        
        # Get previous hypothesis score
        if previous_cycles and len(previous_cycles) > 0:
            try:
                previous_cycle = previous_cycles[-1]
                if isinstance(previous_cycle, dict):
                    previous_hypothesis = previous_cycle.get("hypothesis", {})
                    if isinstance(previous_hypothesis, dict):
                        previous_score = float(previous_hypothesis.get("score", 0))
                        hypothesis_improvement["previous_score"] = previous_score
                        hypothesis_improvement["score_delta"] = current_score - previous_score
                        
                        if previous_score > 0:
                            hypothesis_improvement["improvement_percentage"] = (
                                (current_score - previous_score) / previous_score
                            ) * 100
                        
                        # Calculate complexity increase based on text length
                        current_text = current_hypothesis.get("text", "")
                        previous_text = previous_hypothesis.get("text", "")
                        
                        if len(previous_text) > 0:
                            hypothesis_improvement["complexity_increase"] = (
                                (len(current_text) - len(previous_text)) / len(previous_text)
                            ) * 100
                        
                        # Count refinements
                        hypothesis_improvement["refinement_count"] = len(previous_cycles) + 1
            except (ValueError, TypeError, IndexError) as e:
                self.logger.error(f"Error measuring hypothesis improvement: {e}")
        
        return hypothesis_improvement
    
    def _update_metrics(self, performance_metrics, web_data_quality, hypothesis_improvement):
        """
        Update the agent's metrics history.
        
        Args:
            performance_metrics: Dictionary with performance metrics
            web_data_quality: Dictionary with web data quality metrics
            hypothesis_improvement: Dictionary with hypothesis improvement metrics
        """
        try:
            self.metrics["cycle_duration"].append(performance_metrics["total_cycle_time"])
            self.metrics["web_data_quality"].append(web_data_quality)
            self.metrics["hypothesis_improvement"].append(hypothesis_improvement)
            
            # Update agent performance metrics
            for agent_name, execution_time in performance_metrics["agent_times"].items():
                if agent_name not in self.metrics["agent_performance"]:
                    self.metrics["agent_performance"][agent_name] = []
                
                self.metrics["agent_performance"][agent_name].append(execution_time)
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
    
    def _generate_llm_insights(self, cycle_data, performance_metrics, previous_cycles):
        """
        Generate insights and recommendations using the Gemini LLM.
        
        Args:
            cycle_data: Dictionary containing cycle information
            performance_metrics: Dictionary with performance metrics
            previous_cycles: List of previous cycle data
            
        Returns:
            Dictionary with insights, recommendations, and bottlenecks
        """
        # Prepare input for LLM
        prompt = self._prepare_llm_prompt(cycle_data, performance_metrics, previous_cycles)
        
        # Generate insights using Gemini with error handling
        try:
            llm_response = generate_text(prompt, temperature=0.4)
            # Parse LLM response
            insights = self._parse_llm_response(llm_response)
            return insights
        except Exception as e:
            self.logger.error(f"Error generating LLM insights: {e}")
            return {
                "insights": [
                    "Failed to generate insights due to LLM error: " + str(e)
                ],
                "recommendations": [
                    "Check LLM service connectivity",
                    "Verify API key and credentials",
                    "Review prompt structure and formatting"
                ],
                "bottlenecks": [
                    "LLM processing service"
                ]
            }
    
    def _prepare_llm_prompt(self, cycle_data, performance_metrics, previous_cycles):
        """
        Prepare the prompt for the Gemini LLM.
        
        Args:
            cycle_data: Dictionary containing cycle information
            performance_metrics: Dictionary with performance metrics
            previous_cycles: List of previous cycle data
            
        Returns:
            String prompt for the LLM
        """
        # Safely extract data with defaults
        cycle_id = cycle_data.get("cycle_id", "unknown")
        query = cycle_data.get("query", "unknown")
        
        # Safely extract hypothesis data
        hypothesis = cycle_data.get("hypothesis", {})
        hypothesis_text = "No hypothesis available"
        hypothesis_score = 0
        
        if isinstance(hypothesis, dict):
            hypothesis_text = hypothesis.get("text", "No hypothesis available")
            hypothesis_score = hypothesis.get("score", 0)
        
        # Format performance metrics safely
        total_cycle_time = performance_metrics.get("total_cycle_time", 0)
        successful_agents = ", ".join(performance_metrics.get("successful_agents", ["none"]))
        failed_agents = ", ".join(performance_metrics.get("failed_agents", ["none"]))
        bottlenecks = ", ".join([b.get("agent", "unknown") for b in performance_metrics.get("bottlenecks", [])])
        
        # Safely get web data metrics
        web_data = cycle_data.get("web_data", {})
        sources_count = 0
        successful_extractions = 0
        failed_extractions = 0
        
        if isinstance(web_data, dict):
            sources_count = web_data.get("sources_count", 0)
            successful_extractions = web_data.get("successful_extractions", 0)
            failed_extractions = web_data.get("failed_extractions", 0)
        
        # Create prompt
        prompt = f"""
        You are a Meta Review Agent in "The Second Mind" system that evaluates research cycles and provides feedback for improvement.
        
        CURRENT CYCLE INFORMATION:
        - Cycle ID: {cycle_id}
        - Query: {query}
        - Hypothesis: {hypothesis_text}
        - Hypothesis Score: {hypothesis_score}/10
        
        PERFORMANCE METRICS:
        - Total Cycle Time: {total_cycle_time:.2f} seconds
        - Successful Agents: {successful_agents}
        - Failed Agents: {failed_agents}
        - Bottlenecks: {bottlenecks}
        
        WEB DATA METRICS:
        - Sources Count: {sources_count}
        - Successful Extractions: {successful_extractions}
        - Failed Extractions: {failed_extractions}
        
        PREVIOUS CYCLES: {len(previous_cycles)}
        
        Based on the information above, please provide the following:
        1. Insights: Identify 3-5 key insights about the current cycle.
        2. Recommendations: Suggest 3-5 specific improvements for the next cycle.
        3. Bottlenecks: Identify the top 2-3 bottlenecks in the process.
        
        IMPORTANT: Format your response as strict JSON with the following structure:
        {
            "insights": ["insight1", "insight2", ...],
            "recommendations": ["recommendation1", "recommendation2", ...],
            "bottlenecks": ["bottleneck1", "bottleneck2", ...]
        }
        
        Do not include any commentary or explanations outside of the JSON.
        """
        
        return prompt
    
    def _parse_llm_response(self, llm_response):
        """
        Parse the LLM response into a structured format.
        
        Args:
            llm_response: String response from the LLM
            
        Returns:
            Dictionary with insights, recommendations, and bottlenecks
        """
        default_result = {
            "insights": [
                "No insights available due to LLM processing error"
            ],
            "recommendations": [
                "Review system logs for errors",
                "Check LLM integration"
            ],
            "bottlenecks": [
                "LLM processing"
            ]
        }
        
        if not llm_response:
            self.logger.warning("Empty LLM response received")
            return default_result
        
        try:
            # Extract JSON from the response
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                # Strip any markdown code block indicators
                json_str = llm_response[json_start:json_end]
                json_str = json_str.strip('`')
                
                # Replace any invalid escape sequences
                json_str = json_str.replace('\\', '\\\\')
                
                try:
                    result = json.loads(json_str)
                    
                    # Ensure the result has the expected structure
                    if not all(key in result for key in ["insights", "recommendations", "bottlenecks"]):
                        self.logger.warning("LLM response missing required keys")
                        return default_result
                    
                    return result
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON decode error: {e}")
                    
                    # Try another approach - clean the JSON string
                    clean_json_str = json_str.replace('\n', ' ').replace('\t', ' ')
                    try:
                        result = json.loads(clean_json_str)
                        return result
                    except json.JSONDecodeError:
                        pass
            
            # If JSON parsing failed, try to parse manually
            insights = []
            recommendations = []
            bottlenecks = []
            
            lines = llm_response.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if "insights" in line.lower():
                    current_section = "insights"
                elif "recommendations" in line.lower():
                    current_section = "recommendations"
                elif "bottlenecks" in line.lower():
                    current_section = "bottlenecks"
                elif current_section and (line.startswith("-") or line.startswith("*")):
                    item = line[1:].strip()
                    if current_section == "insights":
                        insights.append(item)
                    elif current_section == "recommendations":
                        recommendations.append(item)
                    elif current_section == "bottlenecks":
                        bottlenecks.append(item)
            
            if insights or recommendations or bottlenecks:
                return {
                    "insights": insights or ["No insights available"],
                    "recommendations": recommendations or ["No recommendations available"],
                    "bottlenecks": bottlenecks or ["No bottlenecks identified"]
                }
            
            return default_result
        except Exception as e:
            self.logger.error(f"Error processing LLM response: {e}")
            return default_result
        
    def review(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conduct a final meta-review of the processed research data.
        
        Args:
            data: Dictionary containing research data
            
        Returns:
            Dictionary with meta-review results
        """
        self.logger.info("Starting meta-review of research data")
        
        # Check input data type
        if not isinstance(data, dict):
            self.logger.warning("[WARNING] MetaReviewAgent received unexpected data format. Using fallback.")
            return {"meta_review_results": []}
        
        # Handle different data formats
        if isinstance(data, tuple) and len(data) > 0 and isinstance(data[0], dict):
            # If data is a tuple containing dictionaries, extract the first element
            data = data[0]
        
        # Extract proximity results safely
        proximity_results = data.get("proximity_results", [])
        
        # Check if the proximity results are valid
        if not isinstance(proximity_results, list):
            self.logger.error(f"Unexpected proximity_results format: {type(proximity_results)}")
            proximity_results = []
        
        # Extract items from proximity results
        meta_review_results = []
        
        for item in proximity_results:
            if isinstance(item, dict):
                # Properly evaluate the item
                meta_review_results.append({
                    "item": item,
                    "review_score": self._evaluate_proximity_score(item)
                })
            else:
                self.logger.warning(f"Unexpected item format in proximity_results: {type(item)}")
                meta_review_results.append({
                    "item": {"item": [], "proximity_score": 0.0},
                    "review_score": 0.0
                })
        
        # If no items were found, add default empty results
        if not meta_review_results:
            meta_review_results = [
                {"item": {"item": [], "proximity_score": 0.0}, "review_score": 0.0},
                {"item": {"item": [], "proximity_score": 0.0}, "review_score": 0.0}
            ]
        
        # Create meta review results
        review_result = {"meta_review_results": meta_review_results}
        
        # Post the meta review results to MCPS
        try:
            # Create context data for MCPS
            session_id = str(uuid.uuid4())
            context_data = {
                "session_id": session_id,
                "type": "meta_review_final",
                "data": review_result,
                "relevance": 0.95,  # Very high relevance for final meta review
                "relationships": {
                    "data_source": "proximity_results",
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # First attempt to POST the data
            item_id = self._post_meta_insights_to_mcps(context_data)
            
            # If we get an item_id back, store it for future reference
            if item_id:
                self.logger.info(f"Meta review posted to MCPS with item_id: {item_id}")
                # You might want to store this item_id somewhere for future updates
                review_result["mcps_item_id"] = item_id
        except Exception as e:
            self.logger.error(f"Failed to post meta review to MCPS: {e}")
        
        self.logger.info(f"Meta-review completed with {len(meta_review_results)} results")
        return review_result

    def _evaluate_proximity_score(self, item: Dict[str, Any]) -> float:
        """
        Evaluate proximity score based on connections.
        
        Args:
            item: Dictionary containing proximity data
            
        Returns:
            Float score representing the proximity evaluation
        """
        # Safely extract proximity score
        if not item:
            return 0.0
        
        # Try different possible keys
        possible_keys = ["proximity_score", "score", "proximity", "connection_score"]
        
        for key in possible_keys:
            if key in item:
                try:
                    score = float(item[key])
                    return score
                except (ValueError, TypeError):
                    pass
        
        # If item contains a nested item with a score
        if "item" in item and isinstance(item["item"], dict):
            return self._evaluate_proximity_score(item["item"])
        
        return 0.0