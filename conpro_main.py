# main.py
import time
import argparse
import os
import sys
from typing import Dict, Any

# Add project root to path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import core components
from core.storage import MemoryStorage
from core.context_manager import ContextProtocolServer
from agents.proximity_agent import ProximityAgent
from utils.logger import get_logger

# Import config
import config

# Set up logger
logger = get_logger("main")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='The Second Mind system')
    
    parser.add_argument('--host', type=str, default=config.SERVER_HOST,
                        help='Host for the Model Context Protocol Server')
    parser.add_argument('--port', type=int, default=config.SERVER_PORT,
                        help='Port for the Model Context Protocol Server')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    
    return parser.parse_args()

def initialize_system(args):
    """Initialize core system components."""
    logger.info("Initializing The Second Mind system...")
    
    # Initialize storage
    logger.info("Initializing Memory Storage...")
    storage = MemoryStorage()
    
    # Initialize Context Protocol Server
    logger.info(f"Starting Model Context Protocol Server on {args.host}:{args.port}...")
    mcps = ContextProtocolServer(storage=storage, host=args.host, port=args.port)
    mcps.start()
    
    # Wait a moment for the server to start
    time.sleep(2)
    
    # Initialize Proximity Agent
    logger.info("Initializing Proximity Agent...")
    mcps_url = f"http://{args.host}:{args.port}"
    proximity_agent = ProximityAgent(storage_manager=storage, mcps_url=mcps_url)
    
    return {
        "storage": storage,
        "mcps": mcps,
        "proximity_agent": proximity_agent
    }

def run_example_query(components):
    """Run a simple example query to demonstrate the system in action."""
    proximity_agent = components["proximity_agent"]
    
    logger.info("Running example query through Proximity Agent...")
    
    # Example query and hypotheses
    example_context = {
        "session_id": f"example_session_{int(time.time())}",
        "query": "How might we use biomimicry to improve urban water management systems?",
        "cycle": 1,
        "evolved_hypotheses": [
            {
                "id": "hyp_001",
                "statement": "Leaf-inspired surfaces could help capture and channel rainwater more efficiently in urban environments.",
                "confidence": 0.85
            },
            {
                "id": "hyp_002",
                "statement": "Mimicking how trees filter water through root systems could inspire new urban filtration infrastructure.",
                "confidence": 0.78
            }
        ]
    }
    
    # Process through proximity agent
    logger.info("Processing context through Proximity Agent...")
    processed_context = proximity_agent.process(example_context)
    
    # Display results
    logger.info("Example processing complete.")
    logger.info(f"Found {len(processed_context.get('proximity_results', []))} proximity connections.")
    
    for i, result in enumerate(processed_context.get('proximity_results', [])):
        if result.get("has_connections", False):
            logger.info(f"Hypothesis {i+1} has {len(result.get('connections', []))} connections.")
    
    return processed_context

def main():
    """Main entry point for The Second Mind system."""
    args = parse_arguments()
    
    # Set debug level
    if args.debug:
        logger.setLevel("DEBUG")
        logger.debug("Debug mode enabled")
    
    try:
        # Initialize system components
        components = initialize_system(args)
        
        logger.info("The Second Mind system initialized successfully.")
        logger.info(f"Model Context Protocol Server running at http://{args.host}:{args.port}")
        
        # Run example query to demonstrate functionality
        processed_context = run_example_query(components)
        
        # Keep the system running
        logger.info("System is running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        # Clean shutdown
        if 'components' in locals() and 'mcps' in components:
            logger.info("Stopping Model Context Protocol Server...")
            components["mcps"].stop()
        
        logger.info("The Second Mind system has been shut down.")

if __name__ == "__main__":
    main()