"""
Utility module for fetching and processing real conversation data from Langfuse.
This provides realistic test data for integration tests.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from langfuse import Langfuse


class LangfuseFetcher:
    """Helper class to fetch and process Langfuse data for testing."""
    
    def __init__(self, public_key: Optional[str] = None, 
                 secret_key: Optional[str] = None,
                 host: Optional[str] = None):
        """
        Initialize Langfuse fetcher with credentials.
        
        Args:
            public_key: Langfuse public key (defaults to env var)
            secret_key: Langfuse secret key (defaults to env var)
            host: Langfuse host URL (defaults to env var)
        """
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        self.host = host or os.getenv("LANGFUSE_HOST", "http://langfuse-prod-langfuse-web-1.orb.local")
        
        self.client = None
        if self.public_key and self.secret_key:
            try:
                self.client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host
                )
            except Exception as e:
                print(f"Warning: Could not initialize Langfuse client: {e}")
    
    def fetch_recent_traces(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent traces from Langfuse.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of traces to fetch
            
        Returns:
            List of trace dictionaries
        """
        if not self.client:
            return []
        
        try:
            # Try the simpler API without timestamp parameters
            # as they might not be supported in all versions
            traces = self.client.fetch_traces(limit=limit)
            
            return self._process_traces(traces)
        except Exception as e:
            print(f"Error fetching traces: {e}")
            return []
    
    def fetch_sessions(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch recent sessions from Langfuse.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of sessions to fetch
            
        Returns:
            List of session dictionaries with traces
        """
        if not self.client:
            return []
        
        try:
            # Try the simpler API without timestamp parameters
            sessions = self.client.fetch_sessions(limit=limit)
            
            return self._process_sessions(sessions)
        except Exception as e:
            print(f"Error fetching sessions: {e}")
            return []
    
    def fetch_conversations(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch conversations (input/output pairs) from traces.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of conversations to fetch
            
        Returns:
            List of conversation dictionaries
        """
        traces = self.fetch_recent_traces(days, limit)
        conversations = []
        
        for trace in traces:
            if trace.get("input") and trace.get("output"):
                conversations.append({
                    "input": trace["input"],
                    "output": trace["output"],
                    "metadata": trace.get("metadata", {}),
                    "timestamp": trace.get("timestamp"),
                    "duration": trace.get("duration"),
                    "tags": trace.get("tags", [])
                })
        
        return conversations
    
    def fetch_by_tags(self, tags: List[str], days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch traces filtered by specific tags.
        
        Args:
            tags: List of tags to filter by
            days: Number of days to look back
            limit: Maximum number of traces to fetch
            
        Returns:
            List of trace dictionaries matching the tags
        """
        if not self.client:
            return []
        
        try:
            # Try the simpler API
            traces = self.client.fetch_traces(limit=limit)
            
            return self._process_traces(traces)
        except Exception as e:
            print(f"Error fetching traces by tags: {e}")
            return []
    
    def _process_traces(self, traces) -> List[Dict[str, Any]]:
        """Process raw traces into standardized dictionaries."""
        processed = []
        
        for trace in traces:
            try:
                processed_trace = {
                    "id": getattr(trace, "id", None),
                    "input": self._safe_extract(trace, "input"),
                    "output": self._safe_extract(trace, "output"),
                    "metadata": self._safe_extract(trace, "metadata", {}),
                    "timestamp": self._safe_extract(trace, "timestamp"),
                    "duration": self._safe_extract(trace, "calculatedTotalCost"),
                    "tags": self._safe_extract(trace, "tags", []),
                    "scores": self._safe_extract(trace, "scores", {}),
                    "session_id": self._safe_extract(trace, "sessionId")
                }
                
                # Only include if we have meaningful content
                if processed_trace["input"] or processed_trace["output"]:
                    processed.append(processed_trace)
                    
            except Exception as e:
                print(f"Error processing trace: {e}")
                continue
        
        return processed
    
    def _process_sessions(self, sessions) -> List[Dict[str, Any]]:
        """Process raw sessions into standardized dictionaries."""
        processed = []
        
        for session in sessions:
            try:
                processed_session = {
                    "id": getattr(session, "id", None),
                    "traces": [],
                    "metadata": self._safe_extract(session, "metadata", {}),
                    "timestamp": self._safe_extract(session, "createdAt")
                }
                
                # Process traces within session if available
                if hasattr(session, "traces"):
                    processed_session["traces"] = self._process_traces(session.traces)
                
                processed.append(processed_session)
                
            except Exception as e:
                print(f"Error processing session: {e}")
                continue
        
        return processed
    
    def _safe_extract(self, obj, attr: str, default=None):
        """Safely extract attribute from object."""
        try:
            value = getattr(obj, attr, default)
            # Convert to string if it's a complex object
            if value and not isinstance(value, (str, int, float, bool, list, dict)):
                value = str(value)
            return value
        except:
            return default
    
    def get_test_scenarios(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get categorized test scenarios from Langfuse data.
        
        Returns:
            Dictionary of test scenarios categorized by type
        """
        conversations = self.fetch_conversations(days=30, limit=100)
        
        scenarios = {
            "support": [],
            "technical": [],
            "general": [],
            "error": []
        }
        
        for conv in conversations:
            input_lower = str(conv.get("input", "")).lower()
            output_lower = str(conv.get("output", "")).lower()
            
            # Categorize based on content
            if any(word in input_lower for word in ["help", "support", "issue", "problem"]):
                scenarios["support"].append(conv)
            elif any(word in input_lower for word in ["config", "setup", "install", "performance"]):
                scenarios["technical"].append(conv)
            elif "error" in input_lower or "error" in output_lower:
                scenarios["error"].append(conv)
            else:
                scenarios["general"].append(conv)
        
        return scenarios


def get_sample_conversations() -> List[Dict[str, Any]]:
    """
    Get sample conversations for testing.
    Tries to fetch from Langfuse first, falls back to synthetic data.
    
    Returns:
        List of conversation dictionaries
    """
    fetcher = LangfuseFetcher()
    
    # Try to fetch real data
    conversations = fetcher.fetch_conversations(days=7, limit=20)
    
    # If no real data, provide synthetic fallback
    if not conversations:
        conversations = [
            {
                "input": "How do I configure FalkorDB for multiple Graphiti instances?",
                "output": "Configure FalkorDB with connection pooling using max_connections=16. Use port 6380 to avoid conflicts. Set THREAD_COUNT=8 for M3 optimization.",
                "metadata": {"source": "synthetic", "category": "technical"}
            },
            {
                "input": "What's the best way to monitor FalkorDB performance?",
                "output": "Use the monitor.sh script for real-time monitoring. Check memory with 'docker exec falkordb redis-cli INFO memory'. View slow queries with 'SLOWLOG GET 10'.",
                "metadata": {"source": "synthetic", "category": "monitoring"}
            },
            {
                "input": "How do I handle concurrent writes from multiple agents?",
                "output": "FalkorDB handles concurrent writes well. Use NODE_CREATION_BUFFER=8192 for balanced write loads. Implement connection pooling and use async operations.",
                "metadata": {"source": "synthetic", "category": "concurrency"}
            },
            {
                "input": "My FalkorDB container keeps restarting. What should I check?",
                "output": "Check container logs with 'docker compose logs falkordb'. Verify memory limits aren't exceeded. Ensure port 6380 is available. Check disk space for volumes.",
                "metadata": {"source": "synthetic", "category": "troubleshooting"}
            },
            {
                "input": "How do I backup FalkorDB data?",
                "output": "Run './scripts/backup.sh' to create timestamped backups. Backups are stored in ./backups/ directory. Old backups are automatically cleaned after 7 days.",
                "metadata": {"source": "synthetic", "category": "operations"}
            }
        ]
    
    return conversations


def get_stress_test_data(count: int = 100) -> List[Dict[str, Any]]:
    """
    Generate stress test data for performance testing.
    
    Args:
        count: Number of test data items to generate
        
    Returns:
        List of test data dictionaries
    """
    import random
    
    templates = [
        "Configuration question about {topic}: {detail}",
        "Performance issue with {topic} showing {detail}",
        "How to optimize {topic} for {detail}",
        "Best practices for {topic} when {detail}",
        "Troubleshooting {topic} error: {detail}"
    ]
    
    topics = ["FalkorDB", "Graphiti", "connection pooling", "memory management", 
              "query performance", "concurrent access", "backup strategy", "monitoring"]
    
    details = ["high load", "multiple instances", "M3 optimization", "Docker setup",
               "port conflicts", "slow queries", "data persistence", "error handling"]
    
    stress_data = []
    for i in range(count):
        template = random.choice(templates)
        topic = random.choice(topics)
        detail = random.choice(details)
        
        stress_data.append({
            "input": template.format(topic=topic, detail=detail),
            "output": f"Response for {topic} regarding {detail}. Item {i} of stress test.",
            "metadata": {
                "source": "stress_test",
                "index": i,
                "topic": topic,
                "detail": detail
            }
        })
    
    return stress_data