import asyncio
import json
import os
import time
import traceback
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from config import config
from dotenv import load_dotenv

load_dotenv()

class EnhancedMCPAgent:
    def __init__(self):
        self.state = {
            'status': 'idle',
            'initialized': False,
            'current_tool': None,
            'tokens_used': 0
        }
        self.mcp_servers = {}
        self._available_tools_info = []
        self.model_name = config.AGENT_MODEL
        self.temperature = config.AGENT_TEMPERATURE
        self.model = None

    def update_config(self, model=None, temperature=None):
        """Update agent settings dynamically"""
        if model:
            self.model_name = model
        if temperature is not None:
            self.temperature = temperature
        
        # Re-initialize model with new settings
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            self.model = ChatGroq(
                api_key=api_key,
                model_name=self.model_name,
                temperature=self.temperature,
                max_retries=0  # Faster failure, prevents loop hang
            )

    def initialize_sync(self):
        """Initialize the agent synchronously"""
        try:
            # Create a new event loop for this thread if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self.initialize_async())
        except Exception as e:
            print(f"Agent initialization sync error: {e}")
            traceback.print_exc()
            return False

    async def initialize_async(self):
        """Initialize the agent and connect to MCP servers"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Agent: Loading configuration...")
            
            # Load config
            config_path = os.path.join(os.getcwd(), config.MCP_CONFIG_FILE)
            if not os.path.exists(config_path):
                print(f"Config file not found: {config_path}")
                return False
                
            with open(config_path, 'r') as f:
                mcp_config = json.load(f)
            
            servers = mcp_config.get('mcpServers', {})
            
            for name, cfg in servers.items():
                try:
                    # Filter out non-string args and handle environment variables
                    args = [str(arg) for arg in cfg.get('args', [])]
                    env = {**os.environ, **cfg.get('env', {})}
                    
                    self.mcp_servers[name] = {
                        'command': cfg['command'],
                        'args': args,
                        'env': env
                    }
                    print(f"Registered MCP server: {name}")
                except Exception as e:
                    print(f"Failed to register server {name}: {e}")

            # Initialize model
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                print("GROQ_API_KEY not found in environment")
                return False
                
            self.model = ChatGroq(
                api_key=api_key,
                model_name=self.model_name,
                temperature=self.temperature,
                max_retries=0
            )

            # Collect all available tools
            await self._refresh_tools()
            
            self.state['initialized'] = True
            self.state['status'] = 'idle'
            print(f"Agent initialized successfully with {len(self._available_tools_info)} tools")
            return True
            
        except Exception as e:
            print(f"Agent initialization failed: {e}")
            traceback.print_exc()
            return False

    async def _refresh_tools(self):
        """Fetch tools from all registered MCP servers in parallel"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching tools from {len(self.mcp_servers)} MCP servers...")
        
        async def fetch_from_server(name, cfg):
            server_tools = []
            try:
                print(f"Connecting to {name}...")
                params = StdioServerParameters(
                    command=cfg['command'],
                    args=cfg['args'],
                    env=cfg['env']
                )
                
                # Use a longer timeout for server connection/initialization
                async with asyncio.timeout(60):
                    async with stdio_client(params) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_result = await session.list_tools()
                            for tool in tools_result.tools:
                                server_tools.append({
                                    'name': tool.name,
                                    'description': tool.description,
                                    'input_schema': tool.inputSchema,
                                    'server': name
                                })
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(tools_result.tools)} tools in {name}")
            except Exception as e:
                # Capture specific error info for Semantic Scholar or others
                error_detail = str(e)
                if "TaskGroup" in error_detail:
                    error_detail = "Server subprocess failed to start or exited early (check UV/NPX installation)"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Could not fetch tools from {name}: {error_detail}")
            return server_tools

        # Run all fetches in parallel
        tasks = [fetch_from_server(name, cfg) for name, cfg in self.mcp_servers.items()]
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_tools = [tool for server_result in results for tool in server_result]
        self._available_tools_info = all_tools

    def get_langchain_tools(self):
        """Convert MCP tools to an ultra-minimized format to fit within 2500 tokens"""
        tools = []
        for tool in self._available_tools_info:
            desc = tool['description']
            if len(desc) > 150:
                desc = desc[:147] + "..."
                
            schema = json.loads(json.dumps(tool['input_schema'])) # Deep copy
            if 'properties' in schema:
                for prop in schema['properties']:
                    if isinstance(schema['properties'][prop], dict):
                        p_desc = schema['properties'][prop].get('description', '')
                        if len(p_desc) > 50:
                            schema['properties'][prop]['description'] = p_desc[:47] + "..."
                        
                        schema['properties'][prop].pop('example', None)
                        schema['properties'][prop].pop('examples', None)
                
            tools.append({
                "type": "function",
                "function": {
                    "name": tool['name'],
                    "description": desc,
                    "parameters": schema
                }
            })
        return tools

    async def stream_response(self, user_input: str) -> AsyncGenerator[str, None]:
        if not self.state['initialized']:
            yield json.dumps({'type': 'error', 'message': 'Agent not initialized'})
            return

        self.state['status'] = 'thinking'
        system_msg = SystemMessage(content=config.AGENT_SYSTEM_PROMPT)
        messages = [system_msg, HumanMessage(content=user_input)]
        
        tools = self.get_langchain_tools()
        model_with_tools = self.model.bind_tools(tools) if tools else self.model
        
        max_steps = config.AGENT_MAX_STEPS
        step = 0
        
        while step < max_steps:
            step += 1
            response_text = ""
            current_tool_calls = []
            
            self.state['status'] = 'streaming'
            try:
                async for chunk in model_with_tools.astream(messages):
                    if chunk.content:
                        response_text += chunk.content
                        yield json.dumps({'type': 'content', 'content': chunk.content})
                    if chunk.tool_calls:
                        for tc in chunk.tool_calls:
                            current_tool_calls.append(tc)
            except Exception as e:
                yield json.dumps({'type': 'error', 'message': f"Model error: {str(e)}"})
                break

            if current_tool_calls:
                ai_msg = AIMessage(content=response_text, tool_calls=current_tool_calls)
                messages.append(ai_msg)
                
                for tc in current_tool_calls:
                    tool_name = tc['name']
                    args = tc['args']
                    tc_id = tc['id']
                    
                    tool_info = next((t for t in self._available_tools_info if t['name'] == tool_name), None)
                    if not tool_info:
                        error_msg = f"Tool {tool_name} not found"
                        yield json.dumps({'type': 'error', 'message': error_msg})
                        messages.append(ToolMessage(content=error_msg, tool_call_id=tc_id))
                        continue
                    
                    server_name = tool_info['server']
                    yield json.dumps({'type': 'tool_start', 'tool': tool_name, 'args': args})
                    
                    # Prevent rapid-fire search calls that trigger bot detection
                    if 'search' in tool_name.lower():
                        await asyncio.sleep(0.5)
                    
                    self.state['status'] = 'executing'
                    
                    # Store results locally to yield OUTSIDE context manager
                    tool_res = ""
                    is_ok = False
                    try:
                        cfg = self.mcp_servers[server_name]
                        params = StdioServerParameters(command=cfg['command'], args=cfg['args'], env=cfg['env'])
                        
                        async with stdio_client(params) as (read, write):
                            async with ClientSession(read, write) as session:
                                await asyncio.wait_for(session.initialize(), timeout=20.0)
                                call_res = await asyncio.wait_for(session.call_tool(tool_name, args), timeout=60.0)
                                tool_res = "\n".join([i.text if hasattr(i, "text") else str(i) for i in call_res.content])
                                is_ok = not call_res.isError
                    except Exception as e:
                        tool_res = f"Execution error: {str(e)}"
                        is_ok = False

                    # Tight truncation for speed and token savings
                    if len(tool_res) > 1000:
                        tool_res = tool_res[:1000] + "\n... (result truncated) ..."
                    
                    yield json.dumps({
                        'type': 'tool_result',
                        'tool': tool_name,
                        'result': tool_res,
                        'success': is_ok
                    })
                    messages.append(ToolMessage(content=tool_res, tool_call_id=tc_id))
                
                continue
            else:
                break
        
        self.state['status'] = 'idle'

    def get_state(self) -> Dict[str, Any]:
        return self.state.copy()
    
    def get_context_info(self) -> Dict[str, Any]:
        return {
            'available_tools': self._available_tools_info,
            'system_prompt': config.AGENT_SYSTEM_PROMPT,
            'model': self.model_name,
            'temperature': self.temperature,
            'max_steps': config.AGENT_MAX_STEPS
        }

# Global agent instance
agent_instance = EnhancedMCPAgent()

def get_agent():
    return agent_instance

def init_agent():
    return agent_instance.initialize_sync()