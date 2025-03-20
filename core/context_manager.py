import json
import time
import threading
import uuid
from typing import Dict, List, Any, Optional, Union
from flask import Flask, request, jsonify
import logging
from datetime import datetime
from core.storage import MemoryStorage
from utils.logger import get_logger

logger = get_logger(__name__)

class ContextProtocolServer:
    """
    A server that manages context across agents using a protocol-driven approach.
    It acts as a centralized hub for storing, updating, and retrieving context.
    """
    
    def __init__(self, storage: MemoryStorage, host: str = "localhost", port: int = 8000):
        """
        Initialize the context protocol server.
        
        Args:
            storage (MemoryStorage): Reference to the memory storage system
            host (str): Hostname to run the server on
            port (int): Port number for the server
        """
        self.storage = storage
        self.host = host
        self.port = port
        self.app = Flask("ContextProtocolServer")
        self.active_sessions = {}
        self.setup_routes()
        self.server_thread = None
        
    def setup_routes(self):
        """Configure API routes for the server."""
        
        @self.app.route('/context', methods=['GET'])
        def get_context():
            """Get context for a given query or session."""
            query = request.args.get('query')
            session_id = request.args.get('session_id')
            
            if session_id and session_id in self.active_sessions:
                # Return active session context
                return jsonify({
                    'status': 'success',
                    'context': self.active_sessions[session_id],
                    'timestamp': datetime.now().isoformat()
                })
            elif query:
                # Search for similar contexts based on query
                similar = self.storage.find_similar(query)
                return jsonify({
                    'status': 'success',
                    'similar_contexts': similar,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing query or valid session_id parameter'
                }), 400
        
        @self.app.route('/context', methods=['POST'])
        def add_context():
            """Add new information to the context."""
            data = request.json
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400
            
            session_id = data.get('session_id')
            context_type = data.get('type')
            context_data = data.get('data')
            
            if not all([session_id, context_type, context_data]):
                return jsonify({
                    'status': 'error',
                    'message': 'Missing required fields (session_id, type, data)'
                }), 400
            
            # Create session if it doesn't exist
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = {
                    'created': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'items': {}
                }
            
            # Generate a unique key for this context item
            item_id = f"{session_id}_{context_type}_{uuid.uuid4().hex[:8]}"
            
            # Add to active session
            self.active_sessions[session_id]['items'][item_id] = {
                'type': context_type,
                'data': context_data,
                'added': datetime.now().isoformat()
            }
            self.active_sessions[session_id]['last_updated'] = datetime.now().isoformat()
            
            # Store in persistent storage
            relevance = data.get('relevance', 1.0)
            relationships = data.get('relationships', {})
            
            self.storage.store(
                key=item_id,
                data={
                    'type': context_type,
                    'data': context_data,
                    'session_id': session_id
                },
                relevance=relevance,
                relationships=relationships
            )
            
            return jsonify({
                'status': 'success',
                'item_id': item_id,
                'message': f'Context added to session {session_id}'
            })
        
        @self.app.route('/context/<item_id>', methods=['PUT'])
        def update_context(item_id):
            """Update an existing context item."""
            data = request.json
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400
            
            # Check if item exists in any active session
            session_id = None
            for sess_id, session in self.active_sessions.items():
                if item_id in session['items']:
                    session_id = sess_id
                    break
            
            if not session_id:
                return jsonify({
                    'status': 'error',
                    'message': f'Context item {item_id} not found in any active session'
                }), 404
            
            # Update the item
            update_data = data.get('data', {})
            self.active_sessions[session_id]['items'][item_id]['data'].update(update_data)
            self.active_sessions[session_id]['items'][item_id]['updated'] = datetime.now().isoformat()
            self.active_sessions[session_id]['last_updated'] = datetime.now().isoformat()
            
            # Update in persistent storage
            update_relevance = data.get('relevance')
            self.storage.update(
                key=item_id,
                data=update_data,
                update_relevance=update_relevance
            )
            
            return jsonify({
                'status': 'success',
                'message': f'Context item {item_id} updated'
            })
        
        @self.app.route('/context/<item_id>', methods=['DELETE'])
        def delete_context(item_id):
            """Delete a context item."""
            # Check if item exists in any active session
            session_id = None
            for sess_id, session in self.active_sessions.items():
                if item_id in session['items']:
                    session_id = sess_id
                    break
            
            if not session_id:
                return jsonify({
                    'status': 'error',
                    'message': f'Context item {item_id} not found in any active session'
                }), 404
            
            # Delete from active session
            del self.active_sessions[session_id]['items'][item_id]
            self.active_sessions[session_id]['last_updated'] = datetime.now().isoformat()
            
            # Delete from persistent storage
            self.storage.delete(item_id)
            
            return jsonify({
                'status': 'success',
                'message': f'Context item {item_id} deleted'
            })
        
        @self.app.route('/context/search', methods=['GET'])
        def search_context():
            """Search for context items."""
            query = request.args.get('query')
            
            if not query:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing query parameter'
                }), 400
            
            # Search in storage
            results = self.storage.find_similar(query)
            
            return jsonify({
                'status': 'success',
                'results': results,
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/context/session/<session_id>', methods=['GET'])
        def get_session(session_id):
            """Get all context items for a session."""
            if session_id not in self.active_sessions:
                return jsonify({
                    'status': 'error',
                    'message': f'Session {session_id} not found'
                }), 404
            
            return jsonify({
                'status': 'success',
                'session': self.active_sessions[session_id],
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/context/session/<session_id>', methods=['DELETE'])
        def end_session(session_id):
            """End a session (but keep items in storage)."""
            if session_id not in self.active_sessions:
                return jsonify({
                    'status': 'error',
                    'message': f'Session {session_id} not found'
                }), 404
            
            # Archive the session before removing
            self.storage.store(
                key=f"archived_session_{session_id}",
                data=self.active_sessions[session_id],
                relevance=0.7  # Archived sessions have lower initial relevance
            )
            
            # Remove from active sessions
            del self.active_sessions[session_id]
            
            return jsonify({
                'status': 'success',
                'message': f'Session {session_id} ended and archived'
            })
        
        @self.app.route('/context/stats', methods=['GET'])
        def get_stats():
            """Get statistics about the context server."""
            storage_stats = self.storage.get_stats()
            
            return jsonify({
                'status': 'success',
                'stats': {
                    'active_sessions': len(self.active_sessions),
                    'storage': storage_stats,
                    'server_uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0
                },
                'timestamp': datetime.now().isoformat()
            })
    
    def start(self):
        """Start the context protocol server in a separate thread."""
        self.start_time = time.time()
        
        def run_server():
            self.app.run(host=self.host, port=self.port)
        
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        logger.info(f"Context Protocol Server started on http://{self.host}:{self.port}")
    
    def stop(self):
        """Stop the context protocol server."""
        if self.server_thread and self.server_thread.is_alive():
            # In a production environment, you would use a proper shutdown mechanism
            # For this example, we'll just let the daemon thread be terminated
            logger.info("Context Protocol Server stopping")