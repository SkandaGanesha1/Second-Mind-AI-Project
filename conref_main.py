"""
Main script to run the Model Context Protocol Server (MCPS) with the Reflection Agent.
This creates an example of their integration.
"""
import time
import sys
import uuid
from core.storage import MemoryStorage
from core.context_manager import ContextProtocolServer
from agents.reflection_agent import ReflectionAgent
from utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Main function to run the system."""
    try:
        # Initialize memory storage
        logger.info("Initializing memory storage...")
        storage = MemoryStorage()
        
        # Initialize and start the Context Protocol Server
        logger.info("Starting Context Protocol Server...")
        mcps = ContextProtocolServer(storage=storage, host="localhost", port=8000)
        mcps.start()
        logger.info("Context Protocol Server started. Waiting for initialization...")
        time.sleep(2)  # Give server time to initialize
        
        # Initialize the Reflection Agent with MCPS connection
        logger.info("Initializing Reflection Agent...")
        reflection_agent = ReflectionAgent(mcps_url="http://localhost:8000")
        
        # Create a test context
        session_id = str(uuid.uuid4())
        test_context = {
            "session_id": session_id,
            "query": "How do quantum computers affect cryptography?",
            "hypotheses": [
                {
                    "id": "hyp_001",
                    "statement": "Quantum computers can break current RSA encryption methods through Shor's algorithm."
                },
                {
                    "id": "hyp_002",
                    "statement": "Post-quantum cryptography algorithms can resist quantum computer attacks."
                }
            ],
            "web_data": [
                {
                    "source": "https://example.com/quantum-crypto",
                    "title": "Quantum Computing and Cryptography",
                    "content": "Quantum computers leverage quantum mechanics principles to perform calculations impossible for classical computers. Shor's algorithm, executable on quantum computers, can factor large numbers exponentially faster than classical algorithms, threatening RSA encryption."
                },
                {
                    "source": "https://example.com/post-quantum",
                    "title": "Post-Quantum Cryptography",
                    "content": "Post-quantum cryptography refers to cryptographic algorithms that are thought to be secure against an attack by quantum computers. These algorithms are designed to resist quantum computing techniques like Shor's algorithm."
                }
            ]
        }
        
        logger.info("Processing test context with Reflection Agent...")
        result_context = reflection_agent.process(test_context)
        
        # Display results
        logger.info("Reflection Results:")
        for reflection in result_context.get("reflection_results", []):
            logger.info(f"Hypothesis {reflection.get('hypothesis_id')}: " +
                       f"Coherent: {reflection.get('is_coherent')}, " +
                       f"Evidence: {reflection.get('has_supporting_evidence')}")
            for comment in reflection.get("comments", []):
                logger.info(f"- {comment}")
        
        # Retrieve data from MCPS to verify storage
        logger.info("\nVerifying data storage in MCPS...")
        import requests
        response = requests.get(f"http://localhost:8000/context/session/{session_id}")
        if response.status_code == 200:
            session_data = response.json()
            logger.info(f"Found {len(session_data.get('session', {}).get('items', {}))} items in MCPS for session")
        else:
            logger.warning(f"Could not retrieve session data from MCPS: {response.status_code}")
        
        # Keep the server running for a while
        logger.info("\nServer running. Press Ctrl+C to stop...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping server...")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())