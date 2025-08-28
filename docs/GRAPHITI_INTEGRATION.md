# Graphiti + FalkorDB Integration Guide

> **Purpose**: Practical patterns for integrating Graphiti's temporal knowledge graphs with our optimized FalkorDB setup

## Table of Contents
1. [Understanding Graphiti's Architecture](#understanding-graphitis-architecture)
2. [Connection Patterns](#connection-patterns)
3. [Data Modeling Best Practices](#data-modeling-best-practices)
4. [Preventing UUID Duplicates](#preventing-uuid-duplicates)
5. [Performance Optimization](#performance-optimization)
6. [Production Patterns](#production-patterns)
7. [Debugging Integration Issues](#debugging-integration-issues)

---

## Understanding Graphiti's Architecture

### The Bi-Temporal Model

Graphiti tracks knowledge across two time dimensions:

```
Valid Time: When the fact was true in the real world
Transaction Time: When the fact was recorded in the system

Example:
"Alice learned Python in January" (valid_time: 2025-01)
Recorded in system on March 1st (transaction_time: 2025-03-01)
```

### Node Types in Graphiti

```python
# Entity Nodes - Persistent concepts
{
    "type": "Entity",
    "uuid": "entity_python_prog_lang",
    "name": "Python",
    "category": "Programming Language",
    "attributes": {
        "paradigm": "multi-paradigm",
        "typing": "dynamic"
    },
    "created": "2025-01-15T10:00:00Z",
    "group_id": "tech_knowledge"
}

# Episodic Nodes - Temporal events
{
    "type": "Episodic", 
    "uuid": "episode_2025_01_15_learning",
    "content": "Learned about Python decorators",
    "valid_from": "2025-01-15T14:00:00Z",
    "valid_to": "2025-01-15T16:00:00Z",
    "participants": ["Alice", "Bob"],
    "group_id": "tech_knowledge"
}
```

---

## Connection Patterns

### Basic Connection

```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
import os

# Basic connection
driver = FalkorDriver(
    host=os.getenv("FALKORDB_HOST", "localhost"),
    port=int(os.getenv("FALKORDB_PORT", 6379)),
    username=os.getenv("FALKORDB_USER"),  # Optional
    password=os.getenv("FALKORDB_PASS"),  # Optional
    database="shared_knowledge_graph"
)

graphiti = Graphiti(
    llm_client=your_llm_client,
    graph_driver=driver
)
```

### Connection Pool for Concurrent Agents

```python
import asyncio
from redis.asyncio import BlockingConnectionPool
from falkordb.asyncio import FalkorDB

class GraphitiConnectionManager:
    """Manages connections for multiple Graphiti agents"""
    
    def __init__(self, host="localhost", port=6379, max_connections=16):
        self.pool = BlockingConnectionPool(
            host=host,
            port=port,
            max_connections=max_connections,
            timeout=30,  # Connection timeout
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 3,  # TCP_KEEPINTVL  
                3: 5,  # TCP_KEEPCNT
            },
            decode_responses=True
        )
        self.db = FalkorDB(connection_pool=self.pool)
        
    async def get_connection(self):
        """Get a connection from the pool"""
        return await self.db.graph("shared_knowledge_graph")
    
    async def execute_query(self, query, params=None):
        """Execute a query with automatic retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                graph = await self.get_connection()
                return await graph.query(query, params)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def close(self):
        """Clean up connections"""
        await self.pool.disconnect()
```

### Multi-Agent Setup

```python
# Multiple agents sharing the same knowledge graph
class MultiAgentGraphiti:
    def __init__(self, num_agents=4):
        self.conn_manager = GraphitiConnectionManager(max_connections=num_agents * 2)
        self.agents = []
        
        for i in range(num_agents):
            driver = FalkorDriver(
                connection_pool=self.conn_manager.pool,
                database=f"shared_knowledge_graph"  # All use same graph
            )
            
            agent = Graphiti(
                llm_client=your_llm_client,
                graph_driver=driver,
                agent_id=f"agent_{i}"
            )
            self.agents.append(agent)
    
    async def parallel_learning(self, episodes):
        """Multiple agents learn in parallel"""
        tasks = []
        for i, episode in enumerate(episodes):
            agent = self.agents[i % len(self.agents)]
            task = agent.add_episode(
                content=episode['content'],
                name=episode['name'],
                timestamp=episode.get('timestamp')
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

---

## Data Modeling Best Practices

### 1. Consistent UUID Generation

```python
import hashlib
import json
from typing import Dict, Any

def generate_stable_uuid(entity_type: str, attributes: Dict[str, Any]) -> str:
    """Generate deterministic UUID to prevent duplicates"""
    
    # Sort attributes for consistency
    canonical = json.dumps({
        'type': entity_type,
        'attributes': dict(sorted(attributes.items()))
    }, sort_keys=True)
    
    # Generate UUID from canonical representation
    hash_obj = hashlib.sha256(canonical.encode())
    uuid = f"{entity_type}_{hash_obj.hexdigest()[:16]}"
    
    return uuid

# Usage
entity_uuid = generate_stable_uuid("Person", {
    "name": "Alice",
    "role": "Developer"
})
# Always produces: "Person_a3f5b8c9d2e1f0a7"
```

### 2. Temporal Validity Tracking

```python
from datetime import datetime, timedelta
from typing import Optional

class TemporalFact:
    """Represents a fact with temporal validity"""
    
    def __init__(self, 
                 content: str,
                 valid_from: datetime,
                 valid_to: Optional[datetime] = None,
                 confidence: float = 1.0):
        self.content = content
        self.valid_from = valid_from
        self.valid_to = valid_to or datetime.max
        self.confidence = confidence
        self.transaction_time = datetime.now()
    
    def to_cypher(self) -> str:
        """Convert to Cypher CREATE statement"""
        return f"""
        CREATE (f:Fact {{
            content: '{self.content}',
            valid_from: datetime('{self.valid_from.isoformat()}'),
            valid_to: datetime('{self.valid_to.isoformat()}'),
            confidence: {self.confidence},
            transaction_time: datetime('{self.transaction_time.isoformat()}')
        }})
        """
    
    def is_valid_at(self, timestamp: datetime) -> bool:
        """Check if fact is valid at given time"""
        return self.valid_from <= timestamp <= self.valid_to
```

### 3. Incremental Knowledge Updates

```python
class IncrementalKnowledgeGraph:
    """Handles incremental updates to prevent duplicates"""
    
    def __init__(self, driver):
        self.driver = driver
        self.update_cache = {}  # Track recent updates
    
    async def add_or_update_entity(self, entity_data):
        """Add new entity or update existing"""
        
        uuid = entity_data['uuid']
        
        # Check cache first (prevents duplicate DB calls)
        if uuid in self.update_cache:
            cache_time = self.update_cache[uuid]
            if datetime.now() - cache_time < timedelta(minutes=5):
                return "cached"
        
        # Use MERGE to prevent duplicates
        query = """
        MERGE (e:Entity {uuid: $uuid})
        ON CREATE SET 
            e.name = $name,
            e.created = timestamp(),
            e.group_id = $group_id
        ON MATCH SET
            e.updated = timestamp(),
            e.access_count = COALESCE(e.access_count, 0) + 1
        RETURN e
        """
        
        result = await self.driver.execute(query, {
            'uuid': uuid,
            'name': entity_data['name'],
            'group_id': entity_data.get('group_id', 'default')
        })
        
        self.update_cache[uuid] = datetime.now()
        return result
```

---

## Preventing UUID Duplicates

### Root Cause of Duplicates

```python
# PROBLEM: Concurrent agents creating same entity
async def problematic_pattern():
    # Agent 1 and Agent 2 both discover "Python"
    agent1_task = agent1.add_entity("Python", "Programming Language")
    agent2_task = agent2.add_entity("Python", "Programming Language")
    
    # Without proper locking, both might CREATE instead of MERGE
    await asyncio.gather(agent1_task, agent2_task)
    # Result: Duplicate nodes with same UUID!
```

### Solution 1: Application-Level Locking

```python
import asyncio
from typing import Dict

class UUIDLockManager:
    """Prevents concurrent creation of same UUID"""
    
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
    
    async def acquire_lock(self, uuid: str):
        if uuid not in self.locks:
            self.locks[uuid] = asyncio.Lock()
        return self.locks[uuid]
    
    async def with_lock(self, uuid: str, operation):
        lock = await self.acquire_lock(uuid)
        async with lock:
            return await operation()

# Usage
lock_manager = UUIDLockManager()

async def safe_add_entity(graphiti, entity_data):
    uuid = generate_stable_uuid(entity_data['type'], entity_data)
    
    async def operation():
        # Check if exists
        existing = await graphiti.get_entity(uuid)
        if existing:
            return await graphiti.update_entity(uuid, entity_data)
        else:
            return await graphiti.create_entity(entity_data)
    
    return await lock_manager.with_lock(uuid, operation)
```

### Solution 2: Database-Level Constraints

```cypher
// Create unique constraint on UUID (run once)
CREATE CONSTRAINT unique_uuid IF NOT EXISTS
FOR (n:Entity) 
REQUIRE n.uuid IS UNIQUE

CREATE CONSTRAINT unique_episode IF NOT EXISTS  
FOR (e:Episodic)
REQUIRE e.uuid IS UNIQUE
```

### Solution 3: Batch Deduplication

```python
async def batch_deduplicate(driver, batch_size=100):
    """Periodic deduplication of existing duplicates"""
    
    # Find duplicates
    find_query = """
    MATCH (n)
    WHERE EXISTS(n.uuid)
    WITH n.uuid as uuid, COLLECT(n) as nodes, COUNT(*) as cnt
    WHERE cnt > 1
    RETURN uuid, nodes, cnt
    LIMIT $batch_size
    """
    
    duplicates = await driver.execute(find_query, {'batch_size': batch_size})
    
    for row in duplicates:
        uuid, nodes, count = row
        
        # Keep newest node, delete others
        merge_query = """
        MATCH (n {uuid: $uuid})
        WITH n ORDER BY n.created DESC
        WITH COLLECT(n) as all_nodes
        WITH HEAD(all_nodes) as keeper, TAIL(all_nodes) as duplicates
        FOREACH (dup IN duplicates | DETACH DELETE dup)
        RETURN keeper.uuid as kept_uuid
        """
        
        await driver.execute(merge_query, {'uuid': uuid})
        print(f"Deduplicated {count-1} nodes for UUID: {uuid}")
```

---

## Performance Optimization

### Write Optimization for Bulk Imports

```python
class BulkImporter:
    """Optimized bulk import for Graphiti data"""
    
    def __init__(self, driver, batch_size=500):
        self.driver = driver
        self.batch_size = batch_size
        self.entity_buffer = []
        self.relation_buffer = []
    
    async def add_entity(self, entity):
        self.entity_buffer.append(entity)
        if len(self.entity_buffer) >= self.batch_size:
            await self.flush_entities()
    
    async def flush_entities(self):
        if not self.entity_buffer:
            return
        
        # Build single query for all entities
        query = """
        UNWIND $entities as entity
        MERGE (e:Entity {uuid: entity.uuid})
        SET e += entity.properties
        """
        
        await self.driver.execute(query, {'entities': self.entity_buffer})
        print(f"Imported {len(self.entity_buffer)} entities")
        self.entity_buffer = []
    
    async def create_indices_before_import(self):
        """Create indices for better MERGE performance"""
        indices = [
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.uuid)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.group_id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Episodic) ON (e.uuid)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Episodic) ON (e.valid_from)",
        ]
        
        for index_query in indices:
            await self.driver.execute(index_query)
```

### Read Optimization for RAG Queries

```python
class OptimizedRAGRetriever:
    """Optimized retrieval for GraphRAG workloads"""
    
    def __init__(self, driver):
        self.driver = driver
        self.query_cache = {}  # Simple query cache
    
    async def get_temporal_context(self, 
                                   entity_uuid: str,
                                   timestamp: datetime,
                                   max_hops: int = 2):
        """Get temporal context around an entity"""
        
        cache_key = f"{entity_uuid}:{timestamp.isoformat()}:{max_hops}"
        
        # Check cache
        if cache_key in self.query_cache:
            age = datetime.now() - self.query_cache[cache_key]['time']
            if age < timedelta(minutes=5):
                return self.query_cache[cache_key]['data']
        
        # Optimized query with early filtering
        query = """
        MATCH (e:Entity {uuid: $uuid})
        CALL {
            WITH e
            MATCH path = (e)-[*1..$max_hops]-(related)
            WHERE ALL(n IN nodes(path) WHERE 
                NOT EXISTS(n.valid_to) OR 
                datetime(n.valid_to) > datetime($timestamp)
            )
            RETURN path
            LIMIT 100
        }
        WITH e, COLLECT(path) as paths
        RETURN e, paths
        """
        
        result = await self.driver.execute(query, {
            'uuid': entity_uuid,
            'timestamp': timestamp.isoformat(),
            'max_hops': max_hops
        })
        
        # Cache result
        self.query_cache[cache_key] = {
            'time': datetime.now(),
            'data': result
        }
        
        return result
```

### Memory-Aware Configuration

```python
def get_optimized_config(graph_size_estimate: int) -> dict:
    """Get optimized FalkorDB config based on graph size"""
    
    if graph_size_estimate < 1000:
        return {
            'NODE_CREATION_BUFFER': 256,
            'CACHE_SIZE': 25,
            'OMP_THREAD_COUNT': 2,
            'maxmemory': '1gb'
        }
    elif graph_size_estimate < 10000:
        return {
            'NODE_CREATION_BUFFER': 512,
            'CACHE_SIZE': 50,
            'OMP_THREAD_COUNT': 2,
            'maxmemory': '2gb'
        }
    elif graph_size_estimate < 100000:
        return {
            'NODE_CREATION_BUFFER': 2048,
            'CACHE_SIZE': 100,
            'OMP_THREAD_COUNT': 4,
            'maxmemory': '4gb'
        }
    else:
        return {
            'NODE_CREATION_BUFFER': 8192,
            'CACHE_SIZE': 200,
            'OMP_THREAD_COUNT': 8,
            'maxmemory': '8gb'
        }
```

---

## Production Patterns

### Health Check Integration

```python
class GraphitiHealthCheck:
    """Production health monitoring"""
    
    def __init__(self, driver, alert_threshold_mb=1000):
        self.driver = driver
        self.alert_threshold_mb = alert_threshold_mb
    
    async def check_health(self) -> dict:
        health = {
            'status': 'healthy',
            'checks': {},
            'warnings': []
        }
        
        # Check connectivity
        try:
            await self.driver.execute("RETURN 1")
            health['checks']['connectivity'] = 'ok'
        except Exception as e:
            health['status'] = 'unhealthy'
            health['checks']['connectivity'] = f'failed: {e}'
            return health
        
        # Check memory usage
        memory_query = """
        CALL db.memory() YIELD usedMemory
        RETURN usedMemory
        """
        memory_mb = (await self.driver.execute(memory_query))[0][0] / 1024 / 1024
        health['checks']['memory_mb'] = memory_mb
        
        if memory_mb > self.alert_threshold_mb:
            health['warnings'].append(f"High memory usage: {memory_mb:.1f}MB")
        
        # Check for duplicates
        duplicate_query = """
        MATCH (n)
        WHERE EXISTS(n.uuid)
        WITH n.uuid as uuid, COUNT(*) as cnt
        WHERE cnt > 1
        RETURN COUNT(*) as duplicate_count
        """
        duplicates = (await self.driver.execute(duplicate_query))[0][0]
        health['checks']['duplicates'] = duplicates
        
        if duplicates > 0:
            health['warnings'].append(f"Found {duplicates} duplicate UUIDs")
            health['status'] = 'degraded'
        
        return health
```

### Graceful Degradation

```python
class ResilientGraphiti:
    """Handles failures gracefully"""
    
    def __init__(self, primary_driver, fallback_driver=None):
        self.primary = primary_driver
        self.fallback = fallback_driver
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60
        )
    
    async def execute_with_fallback(self, operation, *args, **kwargs):
        """Execute with automatic fallback"""
        
        # Try primary
        if not self.circuit_breaker.is_open():
            try:
                result = await operation(self.primary, *args, **kwargs)
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                self.circuit_breaker.record_failure()
                if not self.fallback:
                    raise
        
        # Use fallback
        if self.fallback:
            return await operation(self.fallback, *args, **kwargs)
        
        raise Exception("Primary failed and no fallback available")
```

---

## Debugging Integration Issues

### Common Problems and Solutions

#### Problem 1: Slow Queries

```python
# Diagnose slow queries
async def diagnose_slow_queries(driver):
    # Get query execution plan
    explain_query = """
    EXPLAIN
    MATCH (n:Entity)-[:RELATES_TO*1..3]-(m:Entity)
    WHERE n.uuid = 'test_uuid'
    RETURN n, m
    """
    
    plan = await driver.execute(explain_query)
    print("Execution plan:", plan)
    
    # Check if indices are being used
    index_query = "CALL db.indexes()"
    indices = await driver.execute(index_query)
    print("Available indices:", indices)
```

#### Problem 2: Memory Leaks

```bash
# Monitor memory over time
cat > monitor_memory.py << 'EOF'
import time
import redis

r = redis.Redis(host='localhost', port=6379)

while True:
    info = r.info('memory')
    print(f"{time.strftime('%H:%M:%S')} - "
          f"Used: {info['used_memory_human']}, "
          f"RSS: {info['used_memory_rss_human']}, "
          f"Fragmentation: {info['mem_fragmentation_ratio']}")
    time.sleep(10)
EOF

python monitor_memory.py
```

#### Problem 3: Duplicate UUIDs

```python
# Find and fix duplicates
async def find_duplicate_patterns(driver):
    """Identify patterns in duplicate creation"""
    
    query = """
    MATCH (n)
    WHERE EXISTS(n.uuid)
    WITH n.uuid as uuid, COLLECT(n) as nodes, COUNT(*) as cnt
    WHERE cnt > 1
    UNWIND nodes as node
    RETURN uuid, 
           node.created as created_time,
           node.group_id as group_id,
           ID(node) as internal_id
    ORDER BY uuid, created_time
    """
    
    duplicates = await driver.execute(query)
    
    # Analyze patterns
    patterns = {}
    for row in duplicates:
        uuid, created, group, internal_id = row
        if uuid not in patterns:
            patterns[uuid] = []
        patterns[uuid].append({
            'created': created,
            'group': group,
            'id': internal_id
        })
    
    # Find time clusters (concurrent creation)
    for uuid, instances in patterns.items():
        times = [i['created'] for i in instances]
        if len(set(times)) == 1:
            print(f"UUID {uuid}: All {len(instances)} created simultaneously")
        else:
            print(f"UUID {uuid}: Created over time span")
```

### Debug Logging

```python
import logging
from functools import wraps

# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('graphiti.integration')

def log_query(func):
    """Decorator to log all queries"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        query = args[1] if len(args) > 1 else kwargs.get('query', 'unknown')
        logger.debug(f"Executing query: {query[:100]}...")
        
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start
            logger.debug(f"Query completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
    
    return wrapper

# Apply to driver
driver.execute = log_query(driver.execute)
```

---

## Summary

### Key Integration Points

✅ **Use connection pooling** for multi-agent setups

✅ **Generate stable UUIDs** to prevent duplicates

✅ **Implement application-level locking** for concurrent writes

✅ **Create database constraints** as safety net

✅ **Monitor memory continuously** in production

✅ **Use batch operations** for bulk imports

✅ **Cache frequently accessed paths** for RAG queries

✅ **Implement health checks** with duplicate detection

✅ **Plan for graceful degradation** with fallbacks

✅ **Enable debug logging** during development

### Critical Settings

```yaml
# Always use these for Graphiti + FalkorDB
NODE_CREATION_BUFFER: 512      # Never use default 16384
QUERY_MEM_CAPACITY: 268435456  # Prevent runaway queries  
maxmemory-policy: volatile-lru # Better for temporal data
```

🎯 **Remember**: The key to successful Graphiti + FalkorDB integration is preventing duplicate UUIDs and managing memory carefully. Start with conservative settings and scale up as needed.