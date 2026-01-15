from flask import Blueprint, request, Response, jsonify, stream_with_context
import asyncio
import json
import datetime

from agent.mcp_agent import get_agent
from agent.streaming import EventStream

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat', methods=['POST'])
def chat():
    """Handle chat requests with streaming"""
    agent = get_agent()
    
    # Check if agent is initialized
    state = agent.get_state()
    if not state.get('initialized'):
        return jsonify({
            'error': 'Agent not initialized',
            'details': state.get('initialization_error', 'Unknown error')
        }), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    user_input = data.get('message', '').strip()
    
    if not user_input:
        return jsonify({'error': 'Message is required'}), 400
    
    # Create async generator function
    async def generate():
        async for chunk in agent.stream_response(user_input):
            yield chunk
    
    # Create Flask response with proper streaming
    async def stream():
        async for chunk in EventStream.create_response_stream(generate()):
            yield chunk.encode('utf-8')
    
    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@chat_bp.route('/chat/history', methods=['GET'])
def get_history():
    """Get chat history"""
    return jsonify({
        'messages': [],
        'session_id': 'current',
        'timestamp': datetime.now().isoformat()
    })

@chat_bp.route('/chat/regenerate', methods=['POST'])
def regenerate():
    """Regenerate last response"""
    return jsonify({
        'status': 'success',
        'message': 'Regeneration not implemented yet'
    })

@chat_bp.route('/chat/interrupt', methods=['POST'])
def interrupt():
    """Interrupt current agent execution"""
    agent = get_agent()
    agent.reset()
    return jsonify({'status': 'interrupted'})