import logging
import os
import sys
import time
from datetime import datetime
import colorlog
import json
from typing import Dict, Any, Optional, Union

# Configure logging directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

class SecondMindLogger:
    """
    Comprehensive logging system for The Second Mind.
    Provides colored console output and structured JSON log files.
    """
    
    AGENT_COLORS = {
        "supervisor": "cyan",
        "generation": "green",
        "reflection": "blue",
        "ranking": "yellow",
        "evolution": "magenta",
        "proximity": "white",
        "meta_review": "red",
        "web": "bright_black",
        "storage": "bright_cyan",
        "system": "bright_white"
    }
    
    def __init__(self, name: str = "second_mind", log_level: int = logging.INFO):
        """
        Initialize the logger with the given name and log level.
        
        Args:
            name: The name of the logger
            log_level: The logging level (default: INFO)
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.logger.propagate = False
        
        # Clear existing handlers if any
        if self.logger.handlers:
            self.logger.handlers.clear()
            
        # Create timestamped log file name
        timestamp = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(LOG_DIR, f"{name}_{timestamp}.log")
        json_log_file = os.path.join(LOG_DIR, f"{name}_{timestamp}.json")
        
        # Console handler with colors
        console_handler = colorlog.StreamHandler(stream=sys.stdout)
        console_format = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                'DEBUG': 'white',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            }
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler for text logs
        file_handler = logging.FileHandler(log_file)
        file_format = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
        
        # JSON file handler for structured logs
        self.json_handler = logging.FileHandler(json_log_file)
        self.json_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(self.json_handler)
        
        # Session ID for grouping related logs
        self.session_id = f"session_{int(time.time())}"
        
        # Performance metrics
        self.metrics = {}
        
    def _get_agent_color(self, agent_name: str) -> str:
        """Get the color for a specific agent."""
        return self.AGENT_COLORS.get(agent_name.lower(), "white")
    
    def _log_json(self, level: str, agent: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Log structured JSON data to the JSON log file."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "session_id": self.session_id,
            "agent": agent,
            "message": message,
            "data": data or {}
        }
        self.json_handler.handle(
            logging.LogRecord(
                self.name, 
                logging.INFO, 
                "", 0, 
                json.dumps(log_entry), 
                None, None
            )
        )
    
    def agent_log(self, agent_name: str, level: str, message: str, data: Optional[Dict[str, Any]] = None):
        """
        Log a message from a specific agent with color coding.
        
        Args:
            agent_name: Name of the agent (supervisor, generation, etc.)
            level: Log level (debug, info, warning, error, critical)
            message: The log message
            data: Optional additional structured data for JSON logging
        """
        agent_color = self._get_agent_color(agent_name)
        colored_agent = f"[{agent_name.upper()}]"
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"{colored_agent} {message}")
        
        # Add to JSON log
        self._log_json(level.upper(), agent_name, message, data)
        
    def start_timer(self, name: str):
        """Start a timer for performance measurement."""
        self.metrics[name] = {"start": time.time()}
    
    def end_timer(self, name: str) -> float:
        """End a timer and return the elapsed time."""
        if name in self.metrics and "start" in self.metrics[name]:
            elapsed = time.time() - self.metrics[name]["start"]
            self.metrics[name]["elapsed"] = elapsed
            return elapsed
        return 0.0
    
    def log_cycle(self, cycle_num: int, query: str, results: Dict[str, Any]):
        """Log results of a complete processing cycle."""
        self.agent_log(
            "system", "info", 
            f"Completed Cycle {cycle_num} for query: {query}", 
            {"cycle": cycle_num, "query": query, "results": results}
        )
    
    def log_web_extraction(self, source: str, data_type: str, success: bool, details: Optional[Dict[str, Any]] = None):
        """Log web extraction activities."""
        status = "successful" if success else "failed"
        self.agent_log(
            "web", "info", 
            f"Web extraction from {source} for {data_type} {status}", 
            {"source": source, "data_type": data_type, "success": success, "details": details or {}}
        )
    
    def debug(self, message: str, agent: str = "system", data: Optional[Dict[str, Any]] = None):
        """Debug level log."""
        self.agent_log(agent, "debug", message, data)
    
    def info(self, message: str, agent: str = "system", data: Optional[Dict[str, Any]] = None):
        """Info level log."""
        self.agent_log(agent, "info", message, data)
    
    def warning(self, message: str, agent: str = "system", data: Optional[Dict[str, Any]] = None):
        """Warning level log."""
        self.agent_log(agent, "warning", message, data)
    
    def error(self, message: str, agent: str = "system", data: Optional[Dict[str, Any]] = None):
        """Error level log."""
        self.agent_log(agent, "error", message, data)
    
    def critical(self, message: str, agent: str = "system", data: Optional[Dict[str, Any]] = None):
        """Critical level log."""
        self.agent_log(agent, "critical", message, data)

# Create a default logger instance
logger = SecondMindLogger()

# Convenience functions for importing
def get_logger(name: str = "second_mind", log_level: int = logging.INFO) -> SecondMindLogger:
    """Get a configured logger instance."""
    return SecondMindLogger(name, log_level)

def set_log_level(level: Union[str, int]):
    """Set the log level for the default logger."""
    if isinstance(level, str):
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL
        }
        level = level_map.get(level.lower(), logging.INFO)
    
    logger.logger.setLevel(level)
    for handler in logger.logger.handlers:
        handler.setLevel(level)