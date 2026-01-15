import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class SessionManager:
    def __init__(self, storage_path: str = "sessions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
    
    def create_session(self, title: str = None) -> str:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        session_data = {
            'id': session_id,
            'title': title or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'messages': [],
            'metadata': {}
        }
        
        self._save_session(session_id, session_data)
        return session_id
    
    def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        """Add message to session"""
        session = self._load_session(session_id)
        if not session:
            return False
        
        message = {
            'id': str(uuid.uuid4()),
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        session['messages'].append(message)
        session['updated_at'] = datetime.now().isoformat()
        self._save_session(session_id, session)
        return True
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID"""
        return self._load_session(session_id)
    
    def list_sessions(self, limit: int = 50) -> List[dict]:
        """List all sessions"""
        sessions = []
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    session = json.load(f)
                    sessions.append({
                        'id': session['id'],
                        'title': session['title'],
                        'created_at': session['created_at'],
                        'updated_at': session['updated_at'],
                        'message_count': len(session['messages'])
                    })
            except:
                continue
        
        # Sort by updated_at descending
        sessions.sort(key=lambda x: x['updated_at'], reverse=True)
        return sessions[:limit]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def _save_session(self, session_id: str, data: dict):
        """Save session to disk"""
        file_path = self.storage_path / f"{session_id}.json"
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_session(self, session_id: str) -> Optional[dict]:
        """Load session from disk"""
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return None