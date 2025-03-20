import time
import queue
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime
import logging
from utils.logger import get_logger
from core.storage import MemoryStorage, ContextManager
from config import AGENT_CYCLE_LIMIT, CONFIDENCE_THRESHOLD
from agents.generation_agent import GenerationAgent
from agents.reflection_agent import ReflectionAgent
from agents.ranking_agent import RankingAgent
from agents.evolution_agent import EvolutionAgent
from agents.proximity_agent import ProximityAgent
from agents.meta_review_agent import MetaReviewAgent
from web.scraper import WebScraper
from web.google_search_wrapper import SearchAPI

logger = get_logger(__name__)

class SupervisorAgent:
    """
    The Supervisor Agent that manages and coordinates the six specialized agents.
    It assigns tasks to agents, allocates resources, and enables feedback loops.
    """
    
    def __init__(self, storage: MemoryStorage, context_manager: ContextManager):
        """
        Initialize the supervisor agent.
        
        Args:
            storage (MemoryStorage): Reference to the memory storage system
            context_manager (ContextManager): Reference to the context manager
        """
        self.storage = storage
        self.context = context_manager
        self.agents = {}  # Will store agent instances
        self.task_queue = queue.Queue()
        self.running = False
        self.current_session = None
        self.worker_thread = None
        self.cycle_results = {}
        self.cycle_feedback = {}
        self.scraper = WebScraper()
        self.google_search_wrapper = SearchAPI()
        self.generation_agent = GenerationAgent(self.scraper, self.google_search_wrapper)
        self.reflection_agent = ReflectionAgent()
        self.ranking_agent = RankingAgent()
        self.evolution_agent = EvolutionAgent(self.scraper, self.google_search_wrapper)
        self.proximity_agent = ProximityAgent(self.storage)
        self.meta_review_agent = MetaReviewAgent(self.context, self.storage)
        self.session_data = {}
    
    def register_agent(self, agent_type: str, agent_instance: Any) -> None:
        """
        Register an agent with the supervisor.
        
        Args:
            agent_type (str): Type of agent (e.g., 'generation', 'reflection')
            agent_instance (Any): The agent instance
        """
        self.agents[agent_type] = agent_instance
        logger.info(f"Registered {agent_type} agent")
    
    def start(self) -> None:
        """Start the supervisor agent."""
        if self.running:
            return
        
        self.running = True
        
        def process_tasks():
            while self.running:
                try:
                    task = self.task_queue.get(timeout=1)
                    self._execute_task(task)
                    self.task_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error processing task: {e}")
        
        self.worker_thread = threading.Thread(target=process_tasks)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        logger.info("Supervisor agent started")
    
    def stop(self) -> None:
        """Stop the supervisor agent."""
        self.running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
        logger.info("Supervisor agent stopped")
    
    def _execute_task(self, task: Dict[str, Any]) -> None:
        """
        Execute a task by delegating to the appropriate agent.
        
        Args:
            task (Dict[str, Any]): Task definition
        """
        task_type = task.get('type')
        agent_type = task.get('agent')
        cycle = task.get('cycle', 0)
        
        if agent_type not in self.agents:
            logger.error(f"Unknown agent type: {agent_type}")
            return
        
        agent = self.agents[agent_type]
        
        try:
            logger.info(f"Executing task: {task_type} with {agent_type} agent (Cycle {cycle})")
            
            # Execute the task
            if task_type == 'generate':
                result = agent.generate(task.get('query'), task.get('web_data', []))
                self._handle_generation_result(result, cycle)
            elif task_type == 'reflect':
                result = agent.reflect(task.get('hypothesis'), task.get('web_data', []))
                self._handle_reflection_result(result, cycle)
            elif task_type == 'rank':
                result = agent.rank(task.get('hypotheses', []), task.get('web_data', []))
                self._handle_ranking_result(result, cycle)
            elif task_type == 'evolve':
                result = agent.evolve(task.get('hypothesis'), task.get('web_data', []), task.get('feedback', []))
                self._handle_evolution_result(result, cycle)
            elif task_type == 'proximity':
                result = agent.find_proximity(task.get('query'), task.get('hypothesis'))
                self._handle_proximity_result(result, cycle)
            elif task_type == 'meta_review':
                result = agent.review(task.get('cycle_results'), task.get('performance_data', {}))
                self._handle_meta_review_result(result, cycle)
            elif task_type == 'web_search':
                result = agent.search(task.get('query'), task.get('sources', []))
                self._handle_web_search_result(result, cycle)
            else:
                logger.warning(f"Unknown task type: {task_type}")
        
        except Exception as e:
            logger.error(f"Error executing task {task_type} with {agent_type} agent: {e}")
            
            # Add task to next cycle if it failed
            if cycle < AGENT_CYCLE_LIMIT:
                self.task_queue.put({**task, 'cycle': cycle + 1})
    
    def _handle_generation_result(self, result: Dict[str, Any], cycle: int) -> None:
        """
        Handle the result from the Generation agent.
        
        Args:
            result (Dict[str, Any]): The generation result
            cycle (int): The current cycle number
        """
        if not result or 'hypothesis' not in result:
            logger.warning(f"Invalid generation result in cycle {cycle}")
            return
        
        # Store the hypothesis
        hyp_key = self.context.add_hypothesis(result['hypothesis'], cycle)
        
        # Update cycle results
        if cycle not in self.cycle_results:
            self.cycle_results[cycle] = {}
        self.cycle_results[cycle]['generation'] = {
            'hypothesis_key': hyp_key,
            'hypothesis': result['hypothesis'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Queue next task (reflection)
        self.task_queue.put({
            'type': 'reflect',
            'agent': 'reflection',
            'cycle': cycle,
            'hypothesis': result['hypothesis'],
            'web_data': result.get('web_data', [])
        })
    
    def _handle_reflection_result(self, result: Dict[str, Any], cycle: int) -> None:
        """
        Handle the result from the Reflection agent.
        
        Args:
            result (Dict[str, Any]): The reflection result
            cycle (int): The current cycle number
        """
        if not result:
            logger.warning(f"Invalid reflection result in cycle {cycle}")
            return
        
        # Update cycle results
        if cycle not in self.cycle_results:
            self.cycle_results[cycle] = {}
        self.cycle_results[cycle]['reflection'] = {
            'coherence': result.get('coherence', 0),
            'issues': result.get('issues', []),
            'suggestions': result.get('suggestions', []),
            'timestamp': datetime.now().isoformat()
        }
        
        # Get hypothesis from previous step
        hypothesis = None
        if 'generation' in self.cycle_results.get(cycle, {}):
            hypothesis = self.cycle_results[cycle]['generation'].get('hypothesis')
        
        if not hypothesis:
            logger.warning(f"No hypothesis found for reflection in cycle {cycle}")
            return
        
        # Queue next task (ranking)
        self.task_queue.put({
            'type': 'rank',
            'agent': 'ranking',
            'cycle': cycle,
            'hypotheses': [hypothesis],
            'reflection': result,
            'web_data': result.get('web_data', [])
        })
        
        # Optionally, queue a proximity task in parallel
        self.task_queue.put({
            'type': 'proximity',
            'agent': 'proximity',
            'cycle': cycle,
            'query': self.context.current_session.get('query', ''),
            'hypothesis': hypothesis
        })
    
    def _handle_ranking_result(self, result: Dict[str, Any], cycle: int) -> None:
        """
        Handle the result from the Ranking agent.
        
        Args:
            result (Dict[str, Any]): The ranking result
            cycle (int): The current cycle number
        """
        if not result or 'rankings' not in result:
            logger.warning(f"Invalid ranking result in cycle {cycle}")
            return
        
        # Update cycle results
        if cycle not in self.cycle_results:
            self.cycle_results[cycle] = {}
        self.cycle_results[cycle]['ranking'] = {
            'rankings': result['rankings'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Update hypothesis scores
        for item in result['rankings']:
            hyp = item.get('hypothesis')
            score = item.get('score')
            feedback = item.get('feedback', '')
            
            if hyp and score is not None:
                # Find the hypothesis key
                hyp_key = None
                if 'generation' in self.cycle_results.get(cycle, {}):
                    if self.cycle_results[cycle]['generation'].get('hypothesis') == hyp:
                        hyp_key = self.cycle_results[cycle]['generation'].get('hypothesis_key')
                
                if hyp_key:
                    self.context.update_hypothesis_score(hyp_key, score, feedback)
        
        # Get the top hypothesis
        top_hypothesis = None
        if result['rankings']:
            top_hypothesis = max(result['rankings'], key=lambda x: x.get('score', 0)).get('hypothesis')
        
        if not top_hypothesis:
            logger.warning(f"No top hypothesis found for evolution in cycle {cycle}")
            return
        
        # Queue next task (evolution)
        reflection_result = self.cycle_results.get(cycle, {}).get('reflection', {})
        self.task_queue.put({
            'type': 'evolve',
            'agent': 'evolution',
            'cycle': cycle,
            'hypothesis': top_hypothesis,
            'rankings': result['rankings'],
            'reflection': reflection_result,
            'web_data': result.get('web_data', [])
        })
    
    def _handle_evolution_result(self, result: Dict[str, Any], cycle: int) -> None:
        """
        Handle the result from the Evolution agent.
        
        Args:
            result (Dict[str, Any]): The evolution result
            cycle (int): The current cycle number
        """
        if not result or 'evolved_hypothesis' not in result:
            logger.warning(f"Invalid evolution result in cycle {cycle}")
            return
        
        # Update cycle results
        if cycle not in self.cycle_results:
            self.cycle_results[cycle] = {}
        self.cycle_results[cycle]['evolution'] = {
            'evolved_hypothesis': result['evolved_hypothesis'],
            'improvements': result.get('improvements', []),
            'timestamp': datetime.now().isoformat()
        }
        
        # Store the evolved hypothesis
        hyp_key = self.context.add_hypothesis(result['evolved_hypothesis'], cycle)
        
        # Queue the meta-review task
        self.task_queue.put({
            'type': 'meta_review',
            'agent': 'meta_review',
            'cycle': cycle,
            'cycle_results': self.cycle_results.get(cycle, {}),
            'performance_data': {
                'execution_times': result.get('execution_times', {}),
                'resource_usage': result.get('resource_usage', {}),
                'errors': result.get('errors', [])
            }
        })
        
        # If not at the cycle limit, prepare for the next cycle
        if cycle < AGENT_CYCLE_LIMIT:
            # Check if evolved hypothesis meets confidence threshold
            confidence = result.get('confidence', 0)
            if confidence >= CONFIDENCE_THRESHOLD:
                logger.info(f"Evolved hypothesis meets confidence threshold ({confidence}). Ending cycles.")
                # Finish the current session
                self._finalize_session()
            else:
                # Start a new cycle
                next_cycle = cycle + 1
                logger.info(f"Starting cycle {next_cycle}")
                self.context.start_new_cycle()
                
                # Queue the initial task for the next cycle
                self.task_queue.put({
                    'type': 'web_search',
                    'agent': 'web_search',
                    'cycle': next_cycle,
                    'query': self.context.current_session.get('query', ''),
                    'sources': []
                })
        else:
            # Reached cycle limit, finalize the session
            logger.info(f"Reached cycle limit ({AGENT_CYCLE_LIMIT}). Ending session.")
            self._finalize_session()
    
    def _handle_proximity_result(self, result: Dict[str, Any], cycle: int) -> None:
        """
        Handle the result from the Proximity agent.
        
        Args:
            result (Dict[str, Any]): The proximity result
            cycle (int): The current cycle number
        """
        if not result:
            logger.warning(f"Invalid proximity result in cycle {cycle}")
            return
        
        # Update cycle results
        if cycle not in self.cycle_results:
            self.cycle_results[cycle] = {}
        self.cycle_results[cycle]['proximity'] = {
            'related_memories': result.get('related_memories', []),
            'similarity_score': result.get('similarity_score', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        # No need to queue a next task as this is a parallel task
    
    def _handle_meta_review_result(self, result: Dict[str, Any], cycle: int) -> None:
        """
        Handle the result from the Meta-review agent.
        
        Args:
            result (Dict[str, Any]): The meta-review result
            cycle (int): The current cycle number
        """
        if not result:
            logger.warning(f"Invalid meta-review result in cycle {cycle}")
            return
        
        # Update cycle results
        if cycle not in self.cycle_results:
            self.cycle_results[cycle] = {}
        self.cycle_results[cycle]['meta_review'] = {
            'feedback': result.get('feedback', {}),
            'recommendations': result.get('recommendations', []),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add feedback to context
        self.context.add_cycle_feedback(cycle, result)
        
        # Store the feedback for use in future cycles
        self.cycle_feedback[cycle] = result
    
    def _handle_web_search_result(self, result: Dict[str, Any], cycle: int) -> None:
        """
        Handle the result from the Web Search agent.
        
        Args:
            result (Dict[str, Any]): The web search result
            cycle (int): The current cycle number
        """
        if not result or 'web_data' not in result:
            logger.warning(f"Invalid web search result in cycle {cycle}")
            return
        
        # Store the web data
        for item in result['web_data']:
            self.context.add_web_data(item, item.get('source', 'unknown'), cycle)
        
        # Queue the generation task
        self.task_queue.put({
            'type': 'generate',
            'agent': 'generation',
            'cycle': cycle,
            'query': self.context.current_session.get('query', ''),
            'web_data': result['web_data']
        })
    
    def _finalize_session(self) -> Dict[str, Any]:
        """
        Finalize the current research session.
        
        Returns:
            Dict[str, Any]: Session summary
        """
        # Get the session summary
        summary = self.context.get_session_summary()
        
        # Apply memory decay to reduce the relevance of older items
        self.storage.apply_decay()
        
        logger.info(f"Session finalized: {summary.get('session_id')}")
        return summary
    
    def start_research(self, query, max_iterations=5):
        """
        Initiates the research process with a given query and iterates through multiple refinement cycles.
        """
        self.session_data['query'] = query
        self.session_data['history'] = []

        for cycle in range(1, max_iterations + 1):  # Track iteration count correctly
            print(f"Iteration {cycle} / {max_iterations}")

            # Generate initial responses
            generated_data = self.generation_agent.generate(query)

            # Debugging: Check generated output type
            print("Generated Output Type:", type(generated_data))
            print("Generated Output Content:", generated_data)

            # Ensure generated_data is a dictionary with "results" key
            if not isinstance(generated_data, dict) or "results" not in generated_data:
                print("Warning: GenerationAgent returned unexpected data format. Using fallback.")
                generated_data = {"results": []}

            generated_outputs = generated_data["results"]
            self.session_data['history'].append({'stage': 'generation', 'outputs': generated_outputs})

            # Reflect on generated responses
            reflection_data = self.reflection_agent.process({
                "query": query,
                "web_data": generated_outputs,
                "hypotheses": []  # If hypotheses are generated later, keep it an empty list for now
            })

            # Debugging: Check reflection output type
            print("Reflection Output Type:", type(reflection_data))
            print("Reflection Output Content:", reflection_data)

            # Ensure reflection_data is a dictionary and extract key data
            if isinstance(reflection_data, dict):
                reflection_results = reflection_data.get("reflection_results", [])
                hypotheses = reflection_data.get("hypotheses", [])  # Extract hypotheses correctly
            else:
                print("Warning: Unexpected reflection data format. Using fallback.")
                reflection_results = []
                hypotheses = []

            # Ensure reflection_results is a list of dictionaries
            if not isinstance(reflection_results, list) or not all(isinstance(r, dict) for r in reflection_results):
                print("Warning: ReflectionAgent returned unexpected data format. Using fallback.")
                reflection_results = []

            # Create reflection mapping safely
            reflection_map = {r.get("hypothesis_id", f"default_{i}"): r for i, r in enumerate(reflection_results)}
            self.session_data['history'].append({'stage': 'reflection', 'outputs': reflection_results})

            # ✅ FIX: Pass extracted hypotheses to ranking agent correctly
            ranked_outputs = self.ranking_agent.rank({
                "query": query,
                "hypotheses": hypotheses,
                "reflection_results": reflection_results,
                "web_data": generated_outputs  # ✅ Include missing key
            })

            self.session_data['history'].append({'stage': 'ranking', 'outputs': ranked_outputs})

            # Prepare for evolution
            hypotheses_to_evolve = self.evolution_agent._select_hypotheses_to_evolve(ranked_outputs)

            # Create reflection mapping safely (ensure it only includes valid hypothesis_ids)
            reflection_map = {r.get("hypothesis_id", f"default_{i}"): r for i, r in enumerate(reflection_results)}

            # Apply evolution to refine top-ranked outputs
            evolved_outputs = self.evolution_agent.evolve(
                ranked_hypotheses=ranked_outputs,
                hypotheses_to_evolve=hypotheses_to_evolve,
                reflection_map=reflection_map,
                query=query,
                cycle=cycle  # Pass cycle number
            )

            self.session_data['history'].append({'stage': 'evolution', 'outputs': evolved_outputs})

            # Check proximity to determine similarity and novelty
            proximity_analysis = self.proximity_agent.analyze(evolved_outputs)
            self.session_data['history'].append({'stage': 'proximity', 'outputs': proximity_analysis})

            # Conduct meta-review for final evaluation
            meta_review_results = self.meta_review_agent.review(proximity_analysis)
            self.session_data['history'].append({'stage': 'meta_review', 'outputs': meta_review_results})

            # Determine if further iterations are needed based on meta-review feedback
            if self._check_completion_criteria(meta_review_results):
                print("Research process has converged to a satisfactory result.")
                return meta_review_results

        print("Max iterations reached. Returning the best available results.")
        return meta_review_results



    def get_research_status(self) -> Dict[str, Any]:
        """
        Get the status of the current research session.
        
        Returns:
            Dict[str, Any]: Status information
        """
        if not self.current_session:
            return {
                'status': 'inactive',
                'message': 'No active research session'
            }
        
        # Get the current cycle
        current_cycle = self.context.current_session.get('current_cycle', 0)
        
        # Get the best hypothesis for the current cycle
        best_hyp = self.context.get_best_hypothesis(current_cycle)
        
        return {
            'status': 'active',
            'session_id': self.current_session,
            'query': self.context.current_session.get('query', ''),
            'current_cycle': current_cycle,
            'total_cycles': self.context.current_session.get('cycle_count', 0),
            'best_hypothesis': best_hyp.get('data') if best_hyp else None,
            'pending_tasks': self.task_queue.qsize(),
            'cycle_results': self.cycle_results
        }
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Wait for the current research session to complete.
        
        Args:
            timeout (Optional[float]): Maximum time to wait in seconds
            
        Returns:
            Dict[str, Any]: Session summary
        """
        if not self.current_session:
            return {
                'status': 'inactive',
                'message': 'No active research session'
            }
        
        start_time = time.time()
        while not timeout or time.time() - start_time < timeout:
            if self.task_queue.empty():
                # All tasks are done
                return self.context.get_session_summary()
            
            time.sleep(0.1)
        
        # Timeout reached
        return {
            'status': 'timeout',
            'message': f'Research session timed out after {timeout} seconds',
            'partial_results': self.context.get_session_summary()
        }
    
    def _check_completion_criteria(self, meta_review_results):
        """
        Determines if research should be marked as complete.
        """
        if not isinstance(meta_review_results, dict):
            print("[WARNING] Unexpected data format in meta-review results. Defaulting to incomplete.")
            return False

        # Define some criteria for completion (e.g., sufficient findings)
        return len(meta_review_results.get("meta_review_results", [])) > 0