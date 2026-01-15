import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    MCP_CONFIG_FILE = os.getenv('MCP_CONFIG_FILE', 'broswer_mcp.json')
    
    # Agent settings
    AGENT_MODEL = "llama-3.3-70b-versatile"
    AVAILABLE_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "meta-llama/llama-guard-4-12b",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "groq/compound",
        "groq/compound-mini"
    ]
    AGENT_TEMPERATURE = 0.4
    AGENT_MAX_STEPS = 10
    AGENT_SYSTEM_PROMPT = """You are a highly efficient MCP Research Assistant. 
Your goal is to provide concise, direct, and token-efficient answers.

STRICT PROTOCOL:
1. BREVITY: No boilerplate or small talk. Answer immediately after retrieving data.
2. SPEED: Use specialized tools (ArXiv/Semantic Scholar) directly. Do NOT waste time/tokens on general web searches if technical data exists.
3. TOKEN BUDGET: Only request the specific data needed. Do not summarize if a simple list suffices.
4. CITATIONS: Provide short ArXiv IDs or DOIs only.
5. FAILOVER: If a tool fails once, switch immediately to another or answer with what you have. Do not retry."""
    
    # Session settings
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    
    # Streaming
    STREAMING_ENABLED = True
    SSE_RETRY_TIMEOUT = 30000  # ms
    
    # UI settings
    THEME_DEFAULT = 'dark'
    ENABLE_DARK_MODE = True
    
config = Config()