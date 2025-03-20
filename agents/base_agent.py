"""
Base Agent Class for The Second Mind
Defines the interface and common functionality for all specialized agents.
"""
from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional, List, Tuple

class BaseAgent(ABC):
    """
    Abstract base class for all agents in The Second Mind system.
    Provides common interface and shared functionality.
    """
    
    def __init__(self, agent_id: str, name: str):
        """
        Initialize the base agent.
        
        Args:
            agent_id: Unique identifier for the agent
            name: Human-readable name for the agent
        """
        self.agent_id = agent_id
        self.name = name
        self.logger = logging.getLogger(f"agent.{agent_id}")
        self.metrics = {
            "tasks_processed": 0,
            "avg_processing_time": 0,
            "success_rate": 1.0
        }
    
    @abstractmethod
    def process(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process the given context and return updated context.
        To be implemented by each specialized agent.
        
        Args:
            context: Current context containing all relevant information
            **kwargs: Additional arguments specific to the agent
            
        Returns:
            Updated context after agent processing
        """
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status and metrics of the agent."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "metrics": self.metrics
        }
    
    def update_metrics(self, processing_time: float, success: bool):
        """Update agent performance metrics."""
        self.metrics["tasks_processed"] += 1
        
        # Update average processing time
        current_avg = self.metrics["avg_processing_time"]
        current_count = self.metrics["tasks_processed"]
        self.metrics["avg_processing_time"] = (current_avg * (current_count - 1) + processing_time) / current_count
        
        # Update success rate
        if not success:
            current_successes = self.metrics["success_rate"] * (current_count - 1)
            self.metrics["success_rate"] = (current_successes) / current_count
    
    def extract_relevant_context(self, context: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        """
        Extract only the relevant parts of the context needed by this agent.
        
        Args:
            context: Full context dictionary
            keys: List of keys to extract
            
        Returns:
            Dict containing only the requested keys
        """
        return {k: context.get(k) for k in keys if k in context}
    
    def validate_context(self, context: Dict[str, Any], required_keys: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate that the context contains all required keys.
        
        Args:
            context: Context dictionary to validate
            required_keys: List of required keys
            
        Returns:
            (is_valid, error_message) tuple
        """
        missing_keys = [key for key in required_keys if key not in context]
        if missing_keys:
            return False, f"Missing required context keys: {', '.join(missing_keys)}"
        return True, None
