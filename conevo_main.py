import os
import time
import argparse
import json
from typing import Dict, Any, Optional

from core.storage import MemoryStorage
from core.context_manager import ContextProtocolServer
from agents.evolution_agent import EvolutionAgent
from web.scraper import WebScraper
from web.google_search_wrapper import SearchAPI
from utils.logger import get_logger

logger = get_logger(__name__)

def init_storage() -> MemoryStorage:
    """Initialize the memory storage system."""
    # You might want to add parameters like storage_path, vector_dimensions, etc.
    storage = MemoryStorage()
    logger.info("Memory storage initialized")
    return storage

def init_context_server(storage: MemoryStorage, host: str = "localhost", port: int = 8000) -> ContextProtocolServer:
    """Initialize and start the context protocol server."""
    server = ContextProtocolServer(storage, host=host, port=port)
    server.start()
    logger.info(f"Context Protocol Server started at http://{host}:{port}")
    return server

def init_agents(mcps_url: str) -> Dict[str, Any]:
    """Initialize all required agents."""
    # Initialize web components
    web_scraper = WebScraper()
    
    # SearchAPI now reads the key from environment variables directly
    search_api = SearchAPI()  # Remove the api_key parameter
    
    # Initialize the Evolution Agent
    evolution_agent = EvolutionAgent(web_scraper, search_api, mcps_url=mcps_url)
    
    # You would initialize other agents here as well
    
    logger.info("Agents initialized")
    return {
        "evolution": evolution_agent,
        # Add other agents here
    }

def run_test_cycle(evolution_agent: EvolutionAgent) -> None:
    """Run a test cycle with the Evolution Agent."""
    # Create a sample context
    session_id = f"test_session_{int(time.time())}"
    
    # Sample hypotheses
    sample_hypotheses = [
        {
            "id": "hyp_001",
            "statement": "Quantum computers will outperform classical computers for specific optimization problems.",
            "confidence": 0.7,
            "scores": {"evidence": 0.65, "coherence": 0.8, "originality": 0.75},
            "overall_score": 7.5
        },
        {
            "id": "hyp_002",
            "statement": "Neural interfaces will become mainstream for human-computer interaction.",
            "confidence": 0.6,
            "scores": {"evidence": 0.7, "coherence": 0.6, "originality": 0.8},
            "overall_score": 7.0
        }
    ]
    
    # Sample reflection results
    reflection_results = [
        {
            "hypothesis_id": "hyp_001",
            "is_coherent": True,
            "has_supporting_evidence": False,
            "contradictions": False
        },
        {
            "hypothesis_id": "hyp_002",
            "is_coherent": False,
            "has_supporting_evidence": True,
            "contradictions": True
        }
    ]
    
    test_context = {
        "query": "future of computing",
        "ranked_hypotheses": sample_hypotheses,
        "reflection_results": reflection_results,
        "cycle": 1,
        "session_id": session_id
    }
    
    # Process the context with the Evolution Agent
    logger.info("Running test cycle with Evolution Agent")
    try:
        result = evolution_agent.process(test_context)
        logger.info(f"Evolution Agent processed {len(result.get('evolved_hypotheses', []))} hypotheses")
        logger.info(f"Evolution details: {json.dumps(result.get('evolution_details', []), indent=2)}")
    except Exception as e:
        logger.error(f"Error in test cycle: {str(e)}")

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Second Mind - Context Protocol Server with Evolution Agent")
    parser.add_argument("--host", default="localhost", help="Host address for the Context Protocol Server")
    parser.add_argument("--port", type=int, default=8000, help="Port for the Context Protocol Server")
    parser.add_argument("--test", action="store_true", help="Run a test cycle")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        # Initialize the system
        storage = init_storage()
        context_server = init_context_server(storage, host=args.host, port=args.port)
        
        # Define MCPS URL
        mcps_url = f"http://{args.host}:{args.port}"
        
        # Initialize agents
        agents = init_agents(mcps_url)
        evolution_agent = agents["evolution"]
        
        # Allow server to start properly
        logger.info("Waiting for Context Protocol Server to initialize...")
        time.sleep(2)
        
        # Run a test cycle if requested
        if args.test:
            run_test_cycle(evolution_agent)
        
        # Keep the main thread running
        logger.info("System running. Press Ctrl+C to exit...")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if 'context_server' in locals():
            context_server.stop()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        if 'context_server' in locals():
            context_server.stop()

if __name__ == "__main__":
    main()