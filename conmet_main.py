import argparse
import logging
import os
import time
import sys
import threading
from typing import Dict, Any

# Add parent directory to path to ensure imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import server and agent components
from core.storage import MemoryStorage
from core.context_manager import ContextProtocolServer
from agents.meta_review_agent import MetaReviewAgent
from utils.logger import get_logger

logger = get_logger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Start Context Protocol Server with Meta-Review Agent integration")
    parser.add_argument("--host", type=str, default="localhost", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--storage-path", type=str, default="./data/memory_storage", help="Path to memory storage")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    return parser.parse_args()

def setup_logging(log_level):
    """Setup logging configuration."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("mcps_integration.log")
        ]
    )

def create_test_task():
    """Create a test task for the Meta-Review Agent."""
    return {
        "cycle_id": "test-cycle-1",
        "query": "automated reasoning systems",
        "cycle_data": {
            "agent_outputs": {
                "generation_agent": {
                    "execution_time": 2.5,
                    "status": "success",
                    "output": "Initial hypothesis on automated reasoning"
                },
                "ranking_agent": {
                    "execution_time": 1.2,
                    "status": "success",
                    "output": "Ranked hypotheses"
                }
            },
            "web_data": {
                "sources": [
                    {
                        "type": "academic",
                        "status": "success",
                        "timestamp": "2025-03-20T10:15:30",
                        "content": "Recent advancements in automated reasoning systems show promise in multimodal contexts."
                    },
                    {
                        "type": "news",
                        "status": "success",
                        "timestamp": "2025-03-18T08:45:12",
                        "content": "Tech companies are investing heavily in automated reasoning for decision support systems."
                    }
                ]
            },
            "hypothesis": {
                "text": "Automated reasoning systems can improve decision-making by integrating multimodal inputs and applying heuristic evaluation techniques.",
                "score": 7.5
            }
        }
    }

def run_test_agent(agent, storage, context_manager):
    """Run a test of the Meta-Review Agent with sample data."""
    logger.info("Running test of Meta-Review Agent integration with MCPS...")
    
    # Wait for server to be ready
    time.sleep(2)
    
    # Create test task
    test_task = create_test_task()
    
    # Process the task with the Meta-Review Agent
    try:
        logger.info("Meta-Review Agent processing test task...")
        result = agent.process(test_task)
        logger.info(f"Meta-Review Agent result: {result}")
        
        # Run a review as well
        review_data = {
            "proximity_results": [
                {"item": ["concept_1", "concept_2"], "proximity_score": 0.85},
                {"item": ["concept_3", "concept_4"], "proximity_score": 0.72}
            ]
        }
        review_result = agent.review(review_data)
        logger.info(f"Meta-Review Agent review result: {review_result}")
        
        logger.info("Test completed successfully")
    except Exception as e:
        logger.error(f"Error during test: {e}")

def main():
    """Main function to run the integrated system."""
    args = parse_args()
    setup_logging(args.log_level)
    
    logger.info("Initializing system components...")
    
    # Create storage directory if it doesn't exist
    os.makedirs(os.path.dirname(args.storage_path), exist_ok=True)
    
    # Initialize storage
    storage = MemoryStorage(storage_path=args.storage_path)
    logger.info(f"Memory storage initialized at {args.storage_path}")
    
    # Initialize and start Context Protocol Server
    context_server = ContextProtocolServer(storage=storage, host=args.host, port=args.port)
    context_server.start()
    logger.info(f"Context Protocol Server started at http://{args.host}:{args.port}")
    
    # Create a simple wrapper for the context manager that the Meta-Review Agent expects
    class ContextManagerWrapper:
        def __init__(self, host, port):
            self.host = host
            self.port = port
            self.base_url = f"http://{host}:{port}"
        
        def update_context(self, data):
            """Compatibility method to update context."""
            import requests
            try:
                session_id = data.get("meta_review", {}).get("cycle_id", "default-session")
                if not session_id:
                    session_id = "default-session"
                
                payload = {
                    "session_id": session_id,
                    "type": "meta_review",
                    "data": data
                }
                
                response = requests.post(f"{self.base_url}/context", json=payload)
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Error updating context: {e}")
                return False
    
    # Create context manager wrapper
    context_manager = ContextManagerWrapper(args.host, args.port)
    
    # Initialize Meta-Review Agent
    meta_review_agent = MetaReviewAgent(context_manager=context_manager, storage=storage)
    logger.info("Meta-Review Agent initialized")
    
    # Run a test of the agent integration
    test_thread = threading.Thread(target=run_test_agent, args=(meta_review_agent, storage, context_manager))
    test_thread.daemon = True
    test_thread.start()
    
    try:
        logger.info("System is running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        context_server.stop()
        logger.info("System shutdown complete")

if __name__ == "__main__":
    main()