#!/usr/bin/env python3
"""
Task models for scheduled tasks.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Task:
    """Represents a scheduled task."""
    
    id: str
    name: str
    prompt: str
    cron: str
    timezone: str
    conversation_id: str
    created_by: Optional[str] = None
    enabled: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create task from dictionary representation."""
        # Ensure meta is a dict even if None was stored
        if data.get("meta") is None:
            data["meta"] = {}
        return cls(**data)
