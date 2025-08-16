"""
Shared fixtures and configuration for FalkorDB-Graphiti integration tests.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import pytest
import pytest_asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langfuse import Langfuse
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_EPISODE_MENTIONS
from graphiti_core.utils.maintenance.graph_data_operations import clear_data
from openai import RateLimitError, APITimeoutError
import docker
import time


# Retry decorator for LLM calls
llm_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, ConnectionError))
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def langfuse_data() -> List[Dict[str, Any]]:
    """Fetch real conversation data from Langfuse server."""
    try:
        # Load Langfuse configuration from environment
        langfuse = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "http://langfuse-prod-langfuse-web-1.orb.local")
        )
        
        # Fetch last 7 days of traces
        traces = langfuse.fetch_traces(
            from_timestamp=datetime.now(timezone.utc) - timedelta(days=7),
            to_timestamp=datetime.now(timezone.utc),
            limit=50
        )
        
        # Extract conversation patterns
        conversations = []
        for trace in traces:
            # Extract input/output from trace
            if hasattr(trace, 'input') and hasattr(trace, 'output'):
                conversations.append({
                    "input": str(trace.input) if trace.input else "",
                    "output": str(trace.output) if trace.output else "",
                    "metadata": trace.metadata if hasattr(trace, 'metadata') else {}
                })
        
        # If no Langfuse data available, use fallback test data
        if not conversations:
            conversations = _get_fallback_conversations()
            
        return conversations
        
    except Exception as e:
        print(f"Warning: Could not fetch Langfuse data: {e}")
        # Return fallback test conversations
        return _get_fallback_conversations()


def _get_fallback_conversations() -> List[Dict[str, Any]]:
    """Provide fallback conversation data for testing."""
    return [
        {
            "input": "I need help with my FalkorDB setup on M3 MacBook",
            "output": "I can help you optimize FalkorDB for M3. The key settings are THREAD_COUNT=8 for performance cores and port 6380 to avoid conflicts.",
            "metadata": {"source": "support_chat"}
        },
        {
            "input": "How do I connect multiple Graphiti instances?",
            "output": "Use connection pooling with max_connections=16. Each instance should connect to port 6380 with the shared_knowledge_graph database.",
            "metadata": {"source": "technical_support"}
        },
        {
            "input": "What's the best way to handle concurrent writes?",
            "output": "FalkorDB handles concurrent writes well with NODE_CREATION_BUFFER=8192. Use async operations and connection pooling for best performance.",
            "metadata": {"source": "architecture_discussion"}
        },
        {
            "input": "How do I monitor FalkorDB performance?",
            "output": "Use the monitor.sh script for real-time monitoring. Check memory with redis-cli INFO memory and slow queries with SLOWLOG GET 10.",
            "metadata": {"source": "operations_guide"}
        },
        {
            "input": "Can you explain the backup strategy?",
            "output": "Run backup.sh to create timestamped backups in ./backups/. Backups are retained for 7 days. Use docker exec for manual saves with BGSAVE.",
            "metadata": {"source": "backup_documentation"}
        }
    ]


@pytest_asyncio.fixture(scope="function")
async def graphiti_clients() -> List[Graphiti]:
    """Create 5 Graphiti clients with connection pooling for testing concurrent access."""
    clients = []
    
    for i in range(5):
        try:
            driver = FalkorDriver(
                host="localhost",
                port=6380,  # Custom port to avoid conflicts
                database="shared_knowledge_graph"
                # Note: decode_responses is not a parameter for FalkorDriver
            )
            
            # Initialize Graphiti with retry logic
            client = Graphiti(graph_driver=driver)
            
            # Apply retry decorator to key methods
            client.add_episode = llm_retry(client.add_episode)
            client.search = llm_retry(client.search)
            
            clients.append(client)
            
        except Exception as e:
            pytest.skip(f"Could not connect to FalkorDB: {e}")
    
    yield clients
    
    # Cleanup after each test
    for client in clients:
        try:
            # Close connections properly
            if hasattr(client, 'close'):
                await client.close()
        except:
            pass  # Ignore cleanup errors


@pytest_asyncio.fixture(scope="function")
async def single_client() -> Graphiti:
    """Create a single Graphiti client for simpler tests."""
    try:
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database="shared_knowledge_graph"
            # Note: decode_responses is not a parameter for FalkorDriver
        )
        
        client = Graphiti(graph_driver=driver)
        
        # Apply retry logic
        client.add_episode = llm_retry(client.add_episode)
        client.search = llm_retry(client.search)
        
        yield client
        
        # Cleanup
        if hasattr(client, 'close'):
            await client.close()
            
    except Exception as e:
        pytest.skip(f"Could not connect to FalkorDB: {e}")


@pytest.fixture(scope="function")
def measure_time():
    """Decorator factory to measure and assert operation time."""
    def decorator(max_seconds: float = 2.0):
        def wrapper(func):
            async def inner(*args, **kwargs):
                start = time.perf_counter()
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start
                
                # Assert timing constraint
                assert duration < max_seconds, \
                    f"Operation took {duration:.2f}s, max allowed: {max_seconds}s"
                
                return result, duration
            return inner
        return wrapper
    return decorator


@pytest.fixture(scope="session")
def docker_client():
    """Get Docker client for container management tests."""
    try:
        client = docker.from_env()
        # Verify FalkorDB container exists
        client.containers.get("falkordb")
        return client
    except docker.errors.NotFound:
        pytest.skip("FalkorDB container not found")
    except docker.errors.DockerException as e:
        pytest.skip(f"Docker not available: {e}")


@pytest_asyncio.fixture(scope="function")
async def clean_graph(single_client):
    """Clean the graph before and after each test."""
    # Clean before test
    try:
        await clear_data(single_client.driver)
        await single_client.build_indices_and_constraints()
    except:
        pass  # Ignore if graph doesn't exist yet
    
    yield
    
    # Clean after test
    try:
        await clear_data(single_client.driver)
    except:
        pass


@pytest.fixture(scope="function")
def performance_metrics():
    """Track performance metrics across tests."""
    metrics = {
        "query_times": [],
        "write_times": [],
        "concurrent_operations": []
    }
    
    yield metrics
    
    # Print summary after test
    if metrics["query_times"]:
        avg_query = sum(metrics["query_times"]) / len(metrics["query_times"])
        print(f"\n  Average query time: {avg_query:.3f}s")
    
    if metrics["write_times"]:
        avg_write = sum(metrics["write_times"]) / len(metrics["write_times"])
        print(f"  Average write time: {avg_write:.3f}s")
    
    if metrics["concurrent_operations"]:
        avg_concurrent = sum(metrics["concurrent_operations"]) / len(metrics["concurrent_operations"])
        print(f"  Average concurrent operation time: {avg_concurrent:.3f}s")


# Test markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring FalkorDB"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (>5 seconds)"
    )
    config.addinivalue_line(
        "markers", "concurrent: mark test as testing concurrent access"
    )
    config.addinivalue_line(
        "markers", "persistence: mark test as testing data persistence"
    )