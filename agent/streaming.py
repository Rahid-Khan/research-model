import json
import asyncio
from typing import AsyncGenerator
from datetime import datetime

class EventStream:
    @staticmethod
    def format_sse(data: dict, event: str = None) -> str:
        """Format data for Server-Sent Events"""
        if event:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"
        return f"data: {json.dumps(data)}\n\n"
    
    @staticmethod
    async def heartbeat() -> AsyncGenerator[str, None]:
        """Generate heartbeat events"""
        while True:
            yield EventStream.format_sse({'timestamp': datetime.now().isoformat()}, 'heartbeat')
            await asyncio.sleep(15)  # Send every 15 seconds
    
    @staticmethod
    async def create_response_stream(generator: AsyncGenerator[str, None]):
        """Create Flask response from async generator"""
        try:
            async for chunk in generator:
                yield EventStream.format_sse(json.loads(chunk))
        except Exception as e:
            yield EventStream.format_sse({
                'type': 'error',
                'message': str(e)
            }, 'error')
        finally:
            yield EventStream.format_sse({'type': 'complete'}, 'complete')