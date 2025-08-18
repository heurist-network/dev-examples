#!/usr/bin/env python3

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum





@dataclass
class SessionConfig:
    """Configuration for custom session behavior"""
    # Memory windowing
    max_items: int = 50  # Maximum items to store
    window_size: int = 20  # Items to return by default
    
    # Compression
    enable_compression: bool = True
    compression_threshold: int = 100  # Compress items older than N
    
    # Retention
    ttl_hours: int = 168  # 7 days default
    
    # Performance
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300


@dataclass
class SessionItem:
    """Enhanced session item with metadata"""
    role: str
    content: Any  # Can be string, dict, or list for multimodal
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    hash: Optional[str] = None
    compressed: bool = False
    
    def __post_init__(self):
        """Generate unique hash for each message including timestamp"""
        if self.hash is None:
            content_str = json.dumps(self.content, sort_keys=True, default=str)
            # Include timestamp to ensure uniqueness even for identical messages
            self.hash = hashlib.sha256(
                f"{self.role}:{content_str}:{self.timestamp.isoformat()}".encode()
            ).hexdigest()[:16]