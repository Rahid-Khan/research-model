from flask import Blueprint, jsonify, request
from datetime import datetime

from agent.mcp_agent import get_agent
from config import config

system_bp = Blueprint('system', __name__)

@system_bp.route('/status', methods=['GET'])
def status():
    """Get system and agent status"""
    agent = get_agent()
    
    return jsonify({
        'agent': agent.get_state(),
        'system': {
            'model': config.AGENT_MODEL,
            'temperature': config.AGENT_TEMPERATURE,
            'max_steps': config.AGENT_MAX_STEPS,
            'streaming_enabled': config.STREAMING_ENABLED,
            'timestamp': datetime.now().isoformat()
        },
        'health': {
            'initialized': agent.get_state().get('initialized', False),
            'status': 'healthy' if agent.get_state().get('initialized') else 'unhealthy'
        }
    })

@system_bp.route('/context', methods=['GET'])
def get_context():
    """Get agent context information"""
    agent = get_agent()
    context = agent.get_context_info()
    return jsonify(context)

@system_bp.route('/tools', methods=['GET'])
def list_tools():
    """List available MCP tools"""
    agent = get_agent()
    context = agent.get_context_info()
    return jsonify({
        'tools': context.get('available_tools', []),
        'count': len(context.get('available_tools', []))
    })

@system_bp.route('/settings', methods=['POST'])
def update_settings():
    """Update agent settings"""
    data = request.get_json()
    
    # Note: In production, you'd want to persist these settings
    return jsonify({
        'status': 'settings_updated',
        'settings': data,
        'note': 'Settings are not persisted in this version'
    })

@system_bp.route('/reset', methods=['POST'])
def reset():
    """Reset agent state"""
    agent = get_agent()
    success = agent.reset()
    return jsonify({
        'status': 'reset' if success else 'failed',
        'timestamp': datetime.now().isoformat()
    })

@system_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    agent = get_agent()
    state = agent.get_state()
    
    if state.get('initialized'):
        return jsonify({
            'status': 'healthy',
            'agent': 'initialized',
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({
            'status': 'unhealthy',
            'agent': 'not_initialized',
            'error': state.get('initialization_error'),
            'timestamp': datetime.now().isoformat()
        }), 503