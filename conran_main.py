#!/usr/bin/env python3
"""
Integration script for Context Protocol Server and Ranking Agent.
This script runs the Context Protocol Server and demonstrates how to use it with the Ranking Agent.
"""

import os
import sys
import time
import json
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.storage import MemoryStorage
from core.context_manager import ContextProtocolServer
from agents.ranking_agent import RankingAgent
from utils.logger import get_logger

logger = get_logger(__name__)

def main():
    # 1. Initialize the Memory Storage
    logger.info("Initializing Memory Storage...")
    storage = MemoryStorage()
    
    # 2. Start the Context Protocol Server
    logger.info("Starting Context Protocol Server...")
    server = ContextProtocolServer(storage=storage, host="localhost", port=8000)
    server.start()
    
    # Wait for server to start
    logger.info("Waiting for server to initialize...")
    time.sleep(2)
    
    # 3. Initialize the Ranking Agent with server URL
    logger.info("Initializing Ranking Agent...")
    ranking_agent = RankingAgent(context_server_url="http://localhost:8000")
    
    # 4. Test the integration with sample data
    logger.info("Testing integration with sample data...")
    
    # Create test context
    test_context = {
        "query": "What are the latest advancements in quantum computing?",
        "hypotheses": [
            {
                "id": "hyp_001",
                "statement": "Quantum computers have achieved quantum supremacy by solving problems no classical computer can solve."
            },
            {
                "id": "hyp_002",
                "statement": "Error correction remains the biggest challenge in quantum computing."
            },
            {
                "id": "hyp_003",
                "statement": "Quantum machine learning is showing promise for certain optimization problems."
            }
        ],
        "reflection_results": [
            {
                "hypothesis_id": "hyp_001",
                "coherence_score": 0.8,
                "supporting_facts": ["Google's Sycamore processor completed a task in 200 seconds that would take a classical computer 10,000 years"],
                "contradictions": ["Classical algorithms have been improved to reduce the gap in some cases"]
            },
            {
                "hypothesis_id": "hyp_002",
                "coherence_score": 0.9,
                "supporting_facts": ["Quantum error correction requires many physical qubits for one logical qubit", 
                                     "Noise limits current quantum computers to short coherence times"],
                "contradictions": []
            },
            {
                "hypothesis_id": "hyp_003",
                "coherence_score": 0.7,
                "supporting_facts": ["Quantum neural networks show faster training for certain problems"],
                "contradictions": ["Classical ML still outperforms in most practical applications"]
            }
        ],
        "web_data": [
            {
                "title": "Quantum Supremacy Using a Programmable Superconducting Processor",
                "content": "Google AI Quantum and collaborators have achieved quantum supremacy with Sycamore processor, completing a task in 200 seconds that would take classical supercomputers 10,000 years.",
                "url": "https://example.com/quantum-supremacy"
            },
            {
                "title": "Quantum Error Correction Challenges",
                "content": "Quantum error correction remains a significant challenge, with current approaches requiring many physical qubits for each logical qubit protected from noise.",
                "url": "https://example.com/quantum-error-correction"
            }
        ]
    }
    
    # Process the test context with the Ranking Agent
    logger.info("Processing test context with Ranking Agent...")
    result_context = ranking_agent.process(test_context)
    
    # Print the results
    logger.info("Ranking completed. Results:")
    if "ranked_hypotheses" in result_context:
        for hyp in result_context["ranked_hypotheses"]:
            logger.info(f"Rank {hyp['rank']}: {hyp['statement']} (Score: {hyp['overall_score']})")
    else:
        logger.error("No ranked hypotheses found in result context")
    
    # 5. Verify the results were stored in the Context Protocol Server
    logger.info("Verifying results in Context Protocol Server...")
    session_id = result_context.get("session_id")
    if session_id:
        # Here you would typically make a request to the server to verify
        # For this example, we'll just log the session ID
        logger.info(f"Check session {session_id} in Context Protocol Server")
    
    # Keep the server running for a while
    logger.info("Integration test complete. Press Ctrl+C to exit...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop()

if __name__ == "__main__":
    main()