import time
import threading
from core.supervisor import SupervisorAgent
from core.storage import MemoryStorage, ContextManager
from agents.generation_agent import GenerationAgent
from agents.reflection_agent import ReflectionAgent
from agents.ranking_agent import RankingAgent
from agents.evolution_agent import EvolutionAgent
from agents.proximity_agent import ProximityAgent
from agents.meta_review_agent import MetaReviewAgent
from utils.logger import get_logger
from web.scraper import WebScraper
from web.google_search_wrapper import SearchAPI

web_scraper = WebScraper()  
search_api = SearchAPI()  

logger = get_logger(__name__)

def main():
    logger.info("Initializing The Second Mind system...")
    
    # Initialize core components
    storage = MemoryStorage()
    context_manager = ContextManager(storage)  # Pass the storage argument
    supervisor = SupervisorAgent(storage, context_manager)
    
    # Register agents
    supervisor.register_agent("generation", GenerationAgent(web_scraper, search_api)) 
    supervisor.register_agent("reflection", ReflectionAgent())
    supervisor.register_agent("ranking", RankingAgent())
    supervisor.register_agent("evolution", EvolutionAgent(web_scraper, search_api))
    supervisor.register_agent("proximity", ProximityAgent(storage))
    supervisor.register_agent("meta_review", MetaReviewAgent(context_manager, storage))
    
    # Start the Supervisor Agent
    supervisor.start()
    
    # Define research topic
    research_topic = "Impact of AI on Forensic Investigations"
    session_id = supervisor.start_research(research_topic)
    
    logger.info(f"Research session {session_id} started for topic: {research_topic}")
    
    try:
        while True:
            time.sleep(5)  # Keep the system running
    except KeyboardInterrupt:
        logger.info("Shutting down The Second Mind system...")
        supervisor.stop()

if __name__ == "__main__":
    main()
