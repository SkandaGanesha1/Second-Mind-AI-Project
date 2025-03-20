import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SERP_API_KEY = os.getenv("SERP_API_KEY")

# Search Engine Settings
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
SEARCH_RESULT_LIMIT = 5

# Web Scraping Settings
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# Request throttling
REQUEST_DELAY = 1  # seconds between requests
MAX_RETRIES = 3

# Agent Settings
AGENT_CYCLE_LIMIT = 3  # Maximum number of refinement cycles
CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence score for hypothesis acceptance

# Storage Settings
MEMORY_DECAY_FACTOR = 0.9  # Factor to apply to old memory items to decrease relevance over time
MEMORY_PRUNING_THRESHOLD = 0.3  # Threshold below which memories are pruned

# Context Server Settings
CONTEXT_SERVER_HOST = "localhost"
CONTEXT_SERVER_PORT = 8000

# Logging Settings
LOG_LEVEL = "INFO"
LOG_FILE = "second_mind.log"

# Targeted sites for academic research
ACADEMIC_SITES = [
    "arxiv.org",
    "scholar.google.com",
    "researchgate.net",
    "sciencedirect.com",
    "ieee.org",
    "springer.com",
    "nature.com",
    "ncbi.nlm.nih.gov/pubmed",
]

# Patent databases
PATENT_SITES = [
    "patents.google.com",
    "patentscope.wipo.int",
    "uspto.gov",
    "epo.org",
]

# Tech news sites
TECH_NEWS_SITES = [
    "techcrunch.com",
    "wired.com",
    "theverge.com",
    "technologyreview.com",
    "arstechnica.com",
]

# Server configuration
SERVER_CONFIG = {
    "host": "localhost",
    "port": 8000,
    "debug": False,
    "timeout": 30
}

# Storage configuration
STORAGE_CONFIG = {
    "vector_dimension": 1536,  # Default dimension for embedding vectors
    "similarity_threshold": 0.75,  # Threshold for similarity matching
    "max_memory_items": 10000,  # Maximum number of items to keep in memory
    "decay_rate": 0.05,  # Memory decay rate per day
    "persistence_path": "./data/memory_storage.pkl"  # Path to save persistent storage
}

# Agent configuration
AGENT_CONFIG = {
    "reflection": {
        "coherence_threshold": 0.7,  # Minimum coherence score to accept a hypothesis
        "evidence_count_threshold": 2,  # Minimum number of supporting facts required
        "mcps_url": "http://localhost:8000",
        "timeout": 10  # Request timeout in seconds
    },
    "generation": {
        "temperature": 0.7,
        "max_hypotheses": 5,
        "mcps_url": "http://localhost:8000"
    },
    "ranking": {
        "relevance_weight": 0.6,
        "novelty_weight": 0.2,
        "coherence_weight": 0.2,
        "mcps_url": "http://localhost:8000"
    }
}

# Web scraping configuration
WEB_CONFIG = {
    "max_search_results": 10,
    "max_retries": 3,
    "request_delay": 1.0,  # Delay between requests in seconds
    "timeout": 15,
    "user_agent": "The Second Mind Research Agent/1.0"
}

# LLM configuration
LLM_CONFIG = {
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-pro",
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 8192
    }
}

# config.py
"""
Configuration settings for The Second Mind system.
"""

# Server settings
SERVER_HOST = "localhost"
SERVER_PORT = 8000

# System settings
DEBUG = False

# Agent settings
MAX_HYPOTHESES = 10
MEMORY_DECAY_RATE = 0.05
CONFIDENCE_THRESHOLD = 0.6

# Web search settings
SEARCH_API_KEY = ""  # Add your API key here if needed
SEARCH_ENGINE_ID = ""  # Add your search engine ID if needed
MAX_SEARCH_RESULTS = 10

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "second_mind.log"

import os
from typing import Dict, Any

# Server configuration
SERVER_CONFIG = {
    "host": os.environ.get("MCPS_HOST", "localhost"),
    "port": int(os.environ.get("MCPS_PORT", "8000")),
    "debug": os.environ.get("DEBUG", "False").lower() == "true"
}

# Storage configuration
STORAGE_CONFIG = {
    "vector_dimensions": 768,  # Default dimension for embeddings
    "storage_path": os.environ.get("STORAGE_PATH", "./data/storage"),
    "relevance_threshold": 0.7,  # Minimum relevance score for retrieval
    "max_items": 10000  # Maximum items to store
}

# Agent configuration
AGENT_CONFIG = {
    "evolution": {
        "max_cycles": 5,
        "confidence_threshold": 0.8,
        "min_hypotheses_to_evolve": 1,
        "max_hypotheses_to_evolve": 3
    },
    "reflection": {
        "coherence_threshold": 0.7,
        "evidence_threshold": 0.6
    },
    "ranking": {
        "weights": {
            "evidence": 0.4,
            "coherence": 0.3,
            "originality": 0.3
        }
    }
}

# Web API configuration
WEB_CONFIG = {
    "search_api_key": os.environ.get("SEARCH_API_KEY", ""),
    "max_results": 5,
    "request_timeout": 10,  # seconds
    "scraper_user_agent": "Second Mind Research Assistant/1.0"
}

# Logging configuration
LOGGING_CONFIG = {
    "level": os.environ.get("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": os.environ.get("LOG_FILE", "./logs/second_mind.log")
}

def get_config() -> Dict[str, Any]:
    """Return the complete configuration dictionary."""
    return {
        "server": SERVER_CONFIG,
        "storage": STORAGE_CONFIG,
        "agents": AGENT_CONFIG,
        "web": WEB_CONFIG,
        "logging": LOGGING_CONFIG
    }