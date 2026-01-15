from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for
from flask_cors import CORS
import asyncio
import json
import os
import time
from datetime import datetime
import threading
from pathlib import Path

# Import your agent and session manager
from agent.mcp_agent import get_agent, init_agent
from utils.session_manager import SessionManager
from config import config
import warnings

# Suppress Pydantic compatibility warnings for Python 3.12+
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.*")
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core.*")

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = config.SECRET_KEY

# Store agent instance and session manager
agent = None
agent_initialized = False
session_manager = SessionManager(storage_path="sessions")

def initialize_agent_background():
    """Initialize agent in background thread"""
    global agent, agent_initialized
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing MCP Agent...")
        success = init_agent()
        if success:
            agent = get_agent()
            agent_initialized = True
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Agent initialized successfully")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Agent initialization failed")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Agent initialization error: {e}")

# Start agent initialization in background
init_thread = threading.Thread(target=initialize_agent_background, daemon=True)
init_thread.start()

@app.route('/')
def index():
    return render_template('index.html', theme=config.THEME_DEFAULT)

@app.route('/sessions')
def sessions_page():
    sessions = session_manager.list_sessions()
    return render_template('sessions.html', sessions=sessions, theme=config.THEME_DEFAULT)

@app.route('/settings')
def settings_page():
    return render_template('settings.html', theme=config.THEME_DEFAULT)

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'POST':
        data = request.get_json()
        if 'model' in data:
            config.AGENT_MODEL = data['model']
            if agent:
                agent.update_config(model=data['model'])
        if 'temperature' in data:
            config.AGENT_TEMPERATURE = float(data['temperature'])
            if agent:
                agent.update_config(temperature=float(data['temperature']))
        return jsonify({'status': 'updated'})
    
    return jsonify({
        'models': config.AVAILABLE_MODELS,
        'current_model': config.AGENT_MODEL,
        'temperature': config.AGENT_TEMPERATURE
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat with streaming response"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    user_input = data.get('message', '').strip()
    session_id = data.get('session_id')
    
    if not user_input:
        return jsonify({'error': 'Message is required'}), 400
    
    # Check if agent is ready
    if not agent_initialized or agent is None:
        return jsonify({
            'error': 'Agent not initialized yet',
            'message': 'Please wait a moment and try again'
        }), 503
    
    # Create session if it doesn't exist
    if not session_id:
        session_id = session_manager.create_session(title=user_input[:50] + "...")
    
    # Add user message to session
    session_manager.add_message(session_id, 'user', user_input)
    
    def generate():
        """Generate streaming response"""
        full_response = ""
        
        # Bridge async to sync for Flask streaming
        async def async_generator():
            try:
                state = agent.get_state()
                if not state.get('initialized'):
                    yield json.dumps({'type': 'error', 'message': 'Agent not properly initialized'})
                    return
                
                async for chunk in agent.stream_response(user_input):
                    yield chunk
            except Exception as e:
                yield json.dumps({'type': 'error', 'message': f'Streaming Error: {str(e)}'})

        # Run async loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async_gen = async_generator()
            while True:
                try:
                    chunk = loop.run_until_complete(async_gen.__anext__())
                    if not chunk:
                        break
                    
                    # Accumulate for session storage
                    data = json.loads(chunk)
                    if data.get('type') == 'content':
                        full_response += data.get('content', '')
                    
                    yield f"data: {chunk}\n\n"
                except StopAsyncIteration:
                    # Save assistant response to session
                    session_manager.add_message(session_id, 'assistant', full_response)
                    yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id})}\n\n"
                    break
        finally:
            # Crucial: Allow async tasks (like httpx aclose) to finish before closing loop
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
            except Exception:
                pass
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/tools', methods=['GET'])
def list_tools():
    """List available tools"""
    if not agent_initialized or agent is None:
        return jsonify({'tools': [], 'status': 'not_ready'})
    
    context = agent.get_context_info()
    return jsonify({
        'tools': context.get('available_tools', []),
        'status': 'ready'
    })

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    return jsonify({'sessions': session_manager.list_sessions()})

@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify(session)

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    success = session_manager.delete_session(session_id)
    return jsonify({'status': 'success' if success else 'failed'})

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'agent': {
            'initialized': agent_initialized,
            'status': agent.get_state().get('status', 'unknown') if agent else 'initializing',
            'system_prompt': config.AGENT_SYSTEM_PROMPT,
            'current_model': agent.model_name if agent else config.AGENT_MODEL,
            'temperature': agent.temperature if agent else config.AGENT_TEMPERATURE,
            'available_models': config.AVAILABLE_MODELS
        },
        'system': {'timestamp': datetime.now().isoformat(), 'status': 'running'}
    })

@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == '__main__':
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting MCP Agent UI...")
    # Give agent time to start connecting to servers
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)