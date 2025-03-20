"""
Main script to run the Second Mind system with ContextProtocolServer and GenerationAgent
"""
import time
from core.storage import MemoryStorage
from core.context_manager import ContextProtocolServer
from agents.generation_agent import GenerationAgent
from web.scraper import WebScraper
from web.google_search_wrapper import SearchAPI
from utils.logger import get_logger

logger = get_logger(__name__)

def main():
    # Initialize components
    logger.info("Initializing Second Mind system...")
    
    # Initialize storage
    memory_storage = MemoryStorage()
    
    # Initialize and start Context Protocol Server
    context_server = ContextProtocolServer(
        storage=memory_storage,
        host="localhost",
        port=8000
    )
    context_server.start()
    logger.info("Context Protocol Server started")
    
    # Give the server some time to start
    time.sleep(2)
    
    # Initialize web components
    web_scraper = WebScraper()
    search_api = SearchAPI()
    
    # Initialize Generation Agent with context server connection
    generation_agent = GenerationAgent(
        web_scraper=web_scraper,
        search_api=search_api,
        context_server_url="http://localhost:8000"
    )
    logger.info("Generation Agent initialized")
    
    # Example query
    query = "How are AI technologies being used in forensic investigations?"
    logger.info(f"Testing with query: {query}")
    
    # Generate hypotheses
    results = generation_agent.generate(query)
    
    # Display results
    logger.info(f"Session ID: {results['session_id']}")
    logger.info(f"Generated {len(results['results'])} hypotheses")
    
    for i, hypothesis in enumerate(results['results']):
        logger.info(f"Hypothesis {i+1}: {hypothesis['statement']} (Confidence: {hypothesis['confidence']})")
    
    # Keep the server running
    try:
        logger.info("Press CTRL+C to stop the server")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping the server...")
        context_server.stop()
        logger.info("Server stopped")

if __name__ == "__main__":
    main()