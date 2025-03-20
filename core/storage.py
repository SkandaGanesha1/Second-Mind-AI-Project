import json
import os
import time
import networkx as nx
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import logging
from utils.logger import get_logger

logger = get_logger(__name__)

class MemoryStorage:
    """
    A storage system for The Second Mind that maintains memory of past interactions,
    hypotheses, and their relationships.
    """
    
    def __init__(self, memory_file: str = "memory.json", decay_factor: float = 0.9, pruning_threshold: float = 0.3):
        """
        Initialize the memory storage system.
        
        Args:
            memory_file (str): File path to persist memory
            decay_factor (float): Factor to apply to old memories (0.9 means 10% decay)
            pruning_threshold (float): Threshold below which memories are pruned
        """
        self.memory_file = memory_file
        self.decay_factor = decay_factor
        self.pruning_threshold = pruning_threshold
        self.memory = {}
        self.knowledge_graph = nx.DiGraph()
        self._load_memory()
        self.data = []
        
    def _load_memory(self) -> None:
        """Load memory from file if it exists."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    loaded_data = json.load(f)
                    self.memory = loaded_data.get('memory', {})
                    # Reconstruct knowledge graph from loaded data
                    graph_data = loaded_data.get('graph', {'nodes': [], 'edges': []})
                    self.knowledge_graph = nx.node_link_graph(graph_data)
                logger.info(f"Loaded {len(self.memory)} memories from storage")
            except Exception as e:
                logger.error(f"Error loading memory: {e}")
                self.memory = {}
                self.knowledge_graph = nx.DiGraph()
    
    def _save_memory(self) -> None:
        """Save memory to file."""
        try:
            # Convert knowledge graph to serializable format
            graph_data = nx.node_link_data(self.knowledge_graph)
            with open(self.memory_file, 'w') as f:
                json.dump({
                    'memory': self.memory,
                    'graph': graph_data,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
            logger.info(f"Saved {len(self.memory)} memories to storage")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def apply_decay(self) -> None:
        """Apply decay to all memories based on their age."""
        current_time = time.time()
        keys_to_prune = []
        
        for key, data in self.memory.items():
            age_in_days = (current_time - data.get('timestamp', current_time)) / (24 * 3600)
            # Apply exponential decay
            relevance_factor = self.decay_factor ** age_in_days
            self.memory[key]['relevance'] = data.get('relevance', 1.0) * relevance_factor
            
            # Mark for pruning if below threshold
            if self.memory[key]['relevance'] < self.pruning_threshold:
                keys_to_prune.append(key)
        
        # Prune low-relevance memories
        for key in keys_to_prune:
            self.delete(key)
        
        logger.info(f"Applied decay to memories. Pruned {len(keys_to_prune)} items.")
    
    def store(self, key: str, data: Dict[str, Any], relevance: float = 1.0, 
              relationships: Optional[Dict[str, List[str]]] = None) -> None:
        """
        Store a piece of information in memory with metadata.
        
        Args:
            key (str): Unique identifier for the memory item
            data (Dict[str, Any]): Data to store
            relevance (float): Initial relevance score (1.0 is highest)
            relationships (Dict[str, List[str]], optional): Relationships to other memory items
                Format: {'similar_to': ['key1', 'key2'], 'derived_from': ['key3']}
        """
        timestamp = time.time()
        
        memory_item = {
            'data': data,
            'metadata': {
                'created': datetime.fromtimestamp(timestamp).isoformat(),
                'last_accessed': datetime.fromtimestamp(timestamp).isoformat(),
                'access_count': 0,
            },
            'relevance': relevance,
            'timestamp': timestamp
        }
        
        self.memory[key] = memory_item
        
        # Add to knowledge graph
        self.knowledge_graph.add_node(key, **memory_item)
        
        # Add relationships if provided
        if relationships:
            for rel_type, rel_targets in relationships.items():
                for target in rel_targets:
                    if target in self.memory:
                        self.knowledge_graph.add_edge(key, target, relationship=rel_type)
        
        self._save_memory()
        logger.debug(f"Stored memory item with key: {key}")
    
    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an item from memory by key.
        
        Args:
            key (str): The key to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: The retrieved data or None if not found
        """
        if key in self.memory:
            # Update access metadata
            self.memory[key]['metadata']['last_accessed'] = datetime.now().isoformat()
            self.memory[key]['metadata']['access_count'] += 1
            
            # Increase relevance slightly on access
            self.memory[key]['relevance'] = min(1.0, self.memory[key]['relevance'] * 1.05)
            
            logger.debug(f"Retrieved memory item with key: {key}")
            return self.memory[key]['data']
        else:
            logger.debug(f"Memory item with key '{key}' not found")
            return None
    
    def update(self, key: str, data: Dict[str, Any], 
               update_relevance: Optional[float] = None) -> bool:
        """
        Update an existing memory item.
        
        Args:
            key (str): The key to update
            data (Dict[str, Any]): New or updated data
            update_relevance (Optional[float]): New relevance score
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        if key in self.memory:
            # Update data
            self.memory[key]['data'].update(data)
            
            # Update relevance if provided
            if update_relevance is not None:
                self.memory[key]['relevance'] = update_relevance
            
            # Update metadata
            self.memory[key]['metadata']['last_modified'] = datetime.now().isoformat()
            
            # Update node in knowledge graph
            self.knowledge_graph.nodes[key].update(self.memory[key])
            
            self._save_memory()
            logger.debug(f"Updated memory item with key: {key}")
            return True
            
        logger.debug(f"Failed to update: Memory item with key '{key}' not found")
        return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a memory item.
        
        Args:
            key (str): The key to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if key in self.memory:
            del self.memory[key]
            
            # Remove from knowledge graph
            if self.knowledge_graph.has_node(key):
                self.knowledge_graph.remove_node(key)
            
            self._save_memory()
            logger.debug(f"Deleted memory item with key: {key}")
            return True
            
        logger.debug(f"Failed to delete: Memory item with key '{key}' not found")
        return False
    
    def find_similar(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Find memories similar to the given query.
        Uses simple keyword matching for now.
        
        Args:
            query (str): The query string
            k (int): Number of results to return
            
        Returns:
            List[Dict[str, Any]]: List of similar memories
        """
        # Simple keyword matching (this would be replaced with embedding-based search in a full implementation)
        results = []
        query_terms = set(query.lower().split())
        
        for key, item in self.memory.items():
            # Calculate a simple similarity score based on term overlap
            content = json.dumps(item['data']).lower()
            overlap = sum(1 for term in query_terms if term in content)
            if overlap > 0:
                score = overlap / len(query_terms) * item['relevance']
                results.append({
                    'key': key,
                    'data': item['data'],
                    'score': score,
                    'relevance': item['relevance']
                })
        
        # Sort by score and return top k
        results.sort(key=lambda x: x['score'], reverse=True)
        logger.debug(f"Found {len(results[:k])} similar items for query: {query}")
        return results[:k]
    
    def find_connected(self, key: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find memories connected to the given key in the knowledge graph.
        
        Args:
            key (str): The key to find connections for
            relationship_type (Optional[str]): Filter by relationship type
            
        Returns:
            List[Dict[str, Any]]: List of connected memories
        """
        if not self.knowledge_graph.has_node(key):
            return []
        
        connected = []
        
        # Get all outgoing edges from the key
        for _, target, data in self.knowledge_graph.out_edges(key, data=True):
            # Filter by relationship type if specified
            if relationship_type is None or data.get('relationship') == relationship_type:
                if target in self.memory:
                    connected.append({
                        'key': target,
                        'data': self.memory[target]['data'],
                        'relationship': data.get('relationship', 'unknown'),
                        'relevance': self.memory[target]['relevance']
                    })
        
        # Sort by relevance
        connected.sort(key=lambda x: x['relevance'], reverse=True)
        logger.debug(f"Found {len(connected)} connected items for key: {key}")
        return connected
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the memory storage.
        
        Returns:
            Dict[str, Any]: Statistics about the memory
        """
        total_items = len(self.memory)
        avg_relevance = sum(item['relevance'] for item in self.memory.values()) / total_items if total_items > 0 else 0
        
        return {
            'total_items': total_items,
            'avg_relevance': avg_relevance,
            'graph_nodes': self.knowledge_graph.number_of_nodes(),
            'graph_edges': self.knowledge_graph.number_of_edges(),
            'graph_density': nx.density(self.knowledge_graph) if total_items > 1 else 0,
        }
    
    def save_result(self, result):
        self.data.append(result)

    def store_result(self, result):
        """
        Store a research result.
        
        Args:
            result: The research result to store
        """
        # Convert tuple to dict if necessary
        if isinstance(result, tuple) and len(result) >= 2:
            # Assuming the result tuple contains (statement, confidence, rationale)
            result_dict = {
                "statement": result[0],
                "confidence": result[1],
                "rationale": result[2] if len(result) > 2 else "No rationale provided"
            }
            self.data.append(result_dict)
        elif isinstance(result, dict):
            self.data.append(result)
        else:
            # Handle other types of results
            self.data.append({"raw_result": str(result)})
        
        # Also store in memory for persistence
        key = f"result_{len(self.data)}"
        self.store(key, {"result": result}, relevance=1.0)
        
        logger.info(f"Stored research result: {result}")

    def get_latest_results(self):
        """
        Get the latest research results.
        
        Returns:
            List of research results
        """
        return self.data if self.data else []
    
class ContextManager:
    """Manager for maintaining context across agent interactions."""
    
    def __init__(self, storage: MemoryStorage):
        """
        Initialize the context manager.
        
        Args:
            storage (MemoryStorage): Reference to the memory storage system
        """
        self.storage = storage
        self.current_session = {}
        self.session_id = datetime.now().strftime('%Y%m%d%H%M%S')
        self.session_start = time.time()
        
    def start_session(self, query: str) -> str:
        """
        Start a new research session.
        
        Args:
            query (str): The initial query that starts the session
            
        Returns:
            str: Session ID
        """
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.session_start = time.time()
        self.current_session = {
            'query': query,
            'cycle_count': 0,
            'current_cycle': 1,
            'hypotheses': [],
            'web_data': [],
            'scores': {},
            'feedback': [],
            'state': 'initialized',
        }
        
        # Store initial session in memory
        self.storage.store(
            key=f"{self.session_id}_init",
            data={'query': query, 'session_id': self.session_id},
            relevance=1.0
        )
        
        logger.info(f"Started new session {self.session_id} with query: {query}")
        return self.session_id
    
    def add_hypothesis(self, hypothesis: Dict[str, Any], cycle: int) -> str:
        """
        Add a hypothesis to the current session.
        
        Args:
            hypothesis (Dict[str, Any]): The hypothesis data
            cycle (int): The cycle number
            
        Returns:
            str: Key of stored hypothesis
        """
        key = f"{self.session_id}_hyp_{cycle}_{len(self.current_session['hypotheses']) + 1}"
        
        # Add to session
        self.current_session['hypotheses'].append({
            'key': key,
            'cycle': cycle,
            'data': hypothesis,
            'timestamp': time.time()
        })
        
        # Store in memory
        self.storage.store(
            key=key,
            data=hypothesis,
            relevance=1.0,
            relationships={
                'part_of_session': [f"{self.session_id}_init"],
                'cycle': [f"{self.session_id}_cycle_{cycle}"]
            }
        )
        
        logger.debug(f"Added hypothesis {key} in cycle {cycle}")
        return key
    
    def add_web_data(self, data: Dict[str, Any], source: str, cycle: int) -> str:
        """
        Add web data to the current session.
        
        Args:
            data (Dict[str, Any]): The web data
            source (str): Source of the data
            cycle (int): The cycle number
            
        Returns:
            str: Key of stored web data
        """
        key = f"{self.session_id}_web_{cycle}_{len(self.current_session['web_data']) + 1}"
        
        # Add to session
        web_item = {
            'key': key,
            'cycle': cycle,
            'data': data,
            'source': source,
            'timestamp': time.time()
        }
        self.current_session['web_data'].append(web_item)
        
        # Store in memory
        self.storage.store(
            key=key,
            data={'web_data': data, 'source': source},
            relevance=0.9,  # Web data starts slightly less relevant than hypotheses
            relationships={
                'part_of_session': [f"{self.session_id}_init"],
                'cycle': [f"{self.session_id}_cycle_{cycle}"]
            }
        )
        
        logger.debug(f"Added web data {key} from {source} in cycle {cycle}")
        return key
    
    def update_hypothesis_score(self, hyp_key: str, score: float, feedback: str) -> None:
        """
        Update the score for a hypothesis.
        
        Args:
            hyp_key (str): Key of the hypothesis
            score (float): Score value
            feedback (str): Feedback about the score
        """
        self.current_session['scores'][hyp_key] = {
            'score': score,
            'feedback': feedback,
            'timestamp': time.time()
        }
        
        # Update in memory
        self.storage.update(
            key=hyp_key,
            data={'score': score, 'feedback': feedback},
            update_relevance=min(1.0, 0.5 + score/10)  # Higher scored hypotheses get higher relevance
        )
        
        logger.debug(f"Updated score for hypothesis {hyp_key}: {score}/10")
    
    def add_cycle_feedback(self, cycle: int, feedback: Dict[str, Any]) -> None:
        """
        Add feedback for a complete cycle.
        
        Args:
            cycle (int): The cycle number
            feedback (Dict[str, Any]): Feedback data
        """
        self.current_session['feedback'].append({
            'cycle': cycle,
            'data': feedback,
            'timestamp': time.time()
        })
        
        key = f"{self.session_id}_feedback_{cycle}"
        
        # Store in memory
        self.storage.store(
            key=key,
            data=feedback,
            relevance=0.8,  # Feedback is important but less than the actual hypotheses
            relationships={
                'part_of_session': [f"{self.session_id}_init"],
                'cycle': [f"{self.session_id}_cycle_{cycle}"]
            }
        )
        
        logger.debug(f"Added feedback for cycle {cycle}")
    
    def start_new_cycle(self) -> int:
        """
        Start a new cycle in the current session.
        
        Returns:
            int: The new cycle number
        """
        self.current_session['cycle_count'] += 1
        self.current_session['current_cycle'] = self.current_session['cycle_count']
        cycle_num = self.current_session['current_cycle']
        
        # Store cycle start in memory
        self.storage.store(
            key=f"{self.session_id}_cycle_{cycle_num}",
            data={'cycle_number': cycle_num, 'started': datetime.now().isoformat()},
            relevance=0.9,
            relationships={
                'part_of_session': [f"{self.session_id}_init"],
                'previous_cycle': [f"{self.session_id}_cycle_{cycle_num-1}"] if cycle_num > 1 else []
            }
        )
        
        logger.info(f"Started cycle {cycle_num} for session {self.session_id}")
        return cycle_num
    
    def get_best_hypothesis(self, cycle: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get the highest scored hypothesis for a cycle.
        
        Args:
            cycle (Optional[int]): The cycle number (None for current cycle)
            
        Returns:
            Optional[Dict[str, Any]]: The best hypothesis or None
        """
        if cycle is None:
            cycle = self.current_session['current_cycle']
        
        # Filter hypotheses for this cycle
        cycle_hyps = [h for h in self.current_session['hypotheses'] if h['cycle'] == cycle]
        
        if not cycle_hyps:
            return None
        
        # Find the one with highest score
        best_hyp = None
        best_score = -1
        
        for hyp in cycle_hyps:
            if hyp['key'] in self.current_session['scores']:
                score = self.current_session['scores'][hyp['key']]['score']
                if score > best_score:
                    best_score = score
                    best_hyp = hyp
        
        return best_hyp
    
    def get_cycle_web_data(self, cycle: int) -> List[Dict[str, Any]]:
        """
        Get all web data for a specific cycle.
        
        Args:
            cycle (int): The cycle number
            
        Returns:
            List[Dict[str, Any]]: List of web data items
        """
        return [w for w in self.current_session['web_data'] if w['cycle'] == cycle]
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current session.
        
        Returns:
            Dict[str, Any]: Session summary
        """
        # Get best hypothesis from each cycle
        cycle_results = []
        for cycle in range(1, self.current_session['cycle_count'] + 1):
            best_hyp = self.get_best_hypothesis(cycle)
            if best_hyp:
                score_info = self.current_session['scores'].get(best_hyp['key'], {'score': 'N/A', 'feedback': ''})
                cycle_results.append({
                    'cycle': cycle,
                    'hypothesis': best_hyp['data'],
                    'score': score_info['score'],
                    'feedback': score_info['feedback']
                })
        
        # Get overall statistics
        total_time = time.time() - self.session_start
        
        return {
            'session_id': self.session_id,
            'query': self.current_session['query'],
            'total_cycles': self.current_session['cycle_count'],
            'total_hypotheses': len(self.current_session['hypotheses']),
            'total_web_data': len(self.current_session['web_data']),
            'execution_time_sec': total_time,
            'cycle_results': cycle_results,
            'final_result': cycle_results[-1] if cycle_results else None
        }