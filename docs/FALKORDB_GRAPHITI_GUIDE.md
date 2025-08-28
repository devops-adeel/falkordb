# FalkorDB for Graphiti/GraphRAG: The Complete Developer Guide

> **TL;DR**: This guide helps you set up FalkorDB optimized for Graphiti temporal knowledge graphs, avoiding a catastrophic 7,762x memory expansion we discovered (451KB → 3.5GB). If you're building AI agents that need to remember and reason over time, this is your starting point.

## Table of Contents
1. [Graph Databases 101: Why Graphs for AI?](#graph-databases-101)
2. [Understanding FalkorDB's Architecture](#understanding-falkordbs-architecture)
3. [Graphiti's Temporal Knowledge Model](#graphitis-temporal-knowledge-model)
4. [The Optimized Setup](#the-optimized-setup)
5. [Quick Start](#quick-start)
6. [Next Steps](#next-steps)

---

## Graph Databases 101: Why Graphs for AI?

### What's a Graph Database?

Unlike traditional databases that store data in tables (rows and columns), graph databases store data as:

- **Nodes** (vertices): Entities like people, places, concepts
- **Edges** (relationships): Connections between entities
- **Properties**: Key-value pairs on both nodes and edges

```
Traditional Database:
┌─────────┬──────────┬───────────┐
│ user_id │   name   │   email   │
├─────────┼──────────┼───────────┤
│    1    │  Alice   │ alice@... │
│    2    │   Bob    │  bob@...  │
└─────────┴──────────┴───────────┘

Graph Database:
    (Alice)─────[KNOWS]─────▶(Bob)
      │                        │
  [WORKS_AT]               [MANAGES]
      │                        │
      ▼                        ▼
  (TechCorp)◀──[SUBSIDIARY]─(StartupX)
```

### Why Graphs Excel at GraphRAG

GraphRAG (Graph-based Retrieval Augmented Generation) leverages graph structures for:

1. **Context Discovery**: Follow relationships to find relevant context
2. **Temporal Reasoning**: Track how knowledge evolves over time
3. **Multi-hop Queries**: Answer questions requiring multiple connections
4. **Incremental Updates**: Add new knowledge without rebuilding

💡 **Key Insight**: Traditional RAG searches for similar text chunks. GraphRAG traverses relationships to build contextual understanding.

### Your First Cypher Query

Cypher is the query language for graph databases (like SQL for relational DBs):

```cypher
// Find all concepts Alice learned about
MATCH (alice:Person {name: 'Alice'})-[:LEARNED]->(concept:Concept)
RETURN concept.name, concept.learned_date
ORDER BY concept.learned_date DESC

// Find knowledge paths between two concepts
MATCH path = (ai:Concept {name: 'AI'})-[*..3]-(ethics:Concept {name: 'Ethics'})
RETURN path
```

---

## Understanding FalkorDB's Architecture

### GraphBLAS: The Secret Sauce

FalkorDB uses **sparse matrices** to represent graphs, making it blazingly fast for graph operations:

```
Graph:               Adjacency Matrix:
  A──▶B                 A B C D
  │   │              A [0 1 0 0]
  ▼   ▼              B [0 0 1 1]
  C   D              C [0 0 0 0]
                     D [0 0 0 0]
```

### The CSC Format Advantage

FalkorDB stores matrices in Compressed Sparse Column (CSC) format:
- Only stores non-zero values (edges that exist)
- Extremely efficient for sparse graphs (most real-world graphs)
- Lightning-fast matrix operations for graph algorithms

⚠️ **CRITICAL WARNING**: This efficiency has a dark side - pre-allocating space for future nodes can cause massive memory expansion if not configured correctly.

### Memory Pre-allocation: The Double-Edged Sword

FalkorDB pre-allocates space for nodes to avoid constant resizing:

```yaml
# DEFAULT (DANGEROUS for small graphs with duplicates):
NODE_CREATION_BUFFER: 16384  # Pre-allocates 16K node slots

# OPTIMIZED for Graphiti workloads:
NODE_CREATION_BUFFER: 512    # 32x reduction in memory overhead
```

🔍 **FORENSIC NOTE**: We discovered that duplicate UUIDs + large pre-allocation = 7,762x memory explosion. See [MEMORY_FORENSICS.md](./MEMORY_FORENSICS.md) for the full investigation.

---

## Graphiti's Temporal Knowledge Model

### Entity vs Episodic Nodes

Graphiti uses a **bi-temporal** model to track knowledge over time:

```
Entity Nodes (Persistent Concepts):
(Python)──[IS_A]──▶(Programming Language)
   │
   └──[HAS_FEATURE]──▶(Type Hints)

Episodic Nodes (Time-bound Events):
(Episode_2024_08_15)──[LEARNED]──▶(Python)
   │
   └──[CONTEXT]──▶"During code review discussion"
```

### The UUID Deduplication Challenge

Graphiti assigns UUIDs to prevent duplicate knowledge:

```python
# Graphiti's deduplication logic
entity_uuid = generate_uuid_from_content(entity_name, entity_type)
if not graph.node_exists(uuid=entity_uuid):
    graph.create_node(uuid=entity_uuid, ...)
else:
    graph.update_node(uuid=entity_uuid, ...)
```

⚠️ **CRITICAL**: Failed deduplication creates nodes with same UUID but different internal IDs, triggering sparse matrix fragmentation.

### Incremental Knowledge Updates

GraphRAG systems continuously add knowledge:

```cypher
// Add new knowledge to existing entity
MERGE (e:Entity {uuid: $uuid})
ON CREATE SET e.created = timestamp()
ON MATCH SET e.updated = timestamp()
SET e.last_seen = timestamp()
```

---

## The Optimized Setup

### Docker Compose Configuration

Here's our battle-tested configuration that prevents memory explosions:

```yaml
version: '3.8'

services:
  falkordb:
    image: falkordb/falkordb:v4.2.2  # Version with memory fixes
    container_name: falkordb
    
    # The secret sauce - optimized parameters
    environment:
      - FALKORDB_ARGS=
          THREAD_COUNT 8              # M3 MacBook optimization
          NODE_CREATION_BUFFER 512    # ← CRITICAL: Prevents memory explosion
          QUERY_MEM_CAPACITY 268435456 # 256MB per query limit
          CACHE_SIZE 50               # Query result caching
          OMP_THREAD_COUNT 2          # Parallel execution threads
          EFFECTS_THRESHOLD 100       # Replication threshold (μs)
      
      - REDIS_ARGS=
          --maxmemory 2gb            # Total memory limit
          --maxmemory-policy volatile-lru  # Evict least-recently-used
          --save 3600 10             # Persistence: every hour if 10+ changes
          --save 300 100             # Or every 5 min if 100+ changes
    
    ports:
      - "6379:6379"  # Redis protocol port
    
    volumes:
      - falkordb_data:/data  # Persistent storage
    
    # Health checks prevent false failures during startup
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 30s

    # Resource limits (adjust for your system)
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
        reservations:
          cpus: '2'
          memory: 2G

volumes:
  falkordb_data:
    driver: local
```

### Parameter Breakdown

| Parameter | Default | Optimized | Impact |
|-----------|---------|-----------|--------|
| NODE_CREATION_BUFFER | 16,384 | **512** | 32x memory reduction, prevents fragmentation |
| QUERY_MEM_CAPACITY | Unlimited | **256MB** | Prevents runaway queries |
| maxmemory-policy | noeviction | **volatile-lru** | Better for temporal data |
| THREAD_COUNT | System | **8** | Matches M3 performance cores |
| CACHE_SIZE | 256 | **50** | Balanced for multiple agents |

### Memory Calculation Example

```
Without Optimization:
- 100 nodes with 3 duplicate UUIDs
- 6 matrices × 16,384 slots × 12 bytes = 1.2MB theoretical
- With fragmentation: 3.5GB actual (2,917x overhead!)

With Optimization:
- Same 100 nodes with 3 duplicate UUIDs  
- 6 matrices × 512 slots × 12 bytes = 37KB theoretical
- With fragmentation: 110MB actual (91x reduction!)
```

---

## Quick Start

### 1. Clone and Configure

```bash
# Create project directory
mkdir falkordb-graphiti && cd falkordb-graphiti

# Download optimized docker-compose.yml
curl -O https://raw.githubusercontent.com/your-repo/falkordb/main/docker-compose.yml

# Start FalkorDB
docker compose up -d

# Verify it's running
docker exec falkordb redis-cli ping
# Should return: PONG
```

### 2. Initialize the Graph

```bash
# Create the shared knowledge graph
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph \
  "CREATE (:System {initialized: timestamp(), version: '1.0'})"

# Verify configuration
docker exec falkordb redis-cli GRAPH.CONFIG GET NODE_CREATION_BUFFER
# Should return: "512"
```

### 3. Connect from Python

```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

# Initialize driver with optimized settings
driver = FalkorDriver(
    host="localhost",
    port=6379,
    database="shared_knowledge_graph"
)

# Create Graphiti instance
graphiti = Graphiti(graph_driver=driver)

# Add your first knowledge
await graphiti.add_episode(
    name="Learning FalkorDB",
    content="FalkorDB uses sparse matrices for efficient graph operations",
    timestamp=datetime.now()
)
```

### 4. Monitor Memory Usage

```bash
# Real-time memory monitoring
watch -n 1 'docker exec falkordb redis-cli INFO memory | grep used_memory_human'

# Check for duplicate UUIDs (root cause of explosions)
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph \
  "MATCH (n) WHERE EXISTS(n.uuid) 
   RETURN n.uuid, COUNT(*) as duplicates 
   ORDER BY duplicates DESC LIMIT 10"
```

---

## Next Steps

### Essential Reading

1. **[MEMORY_FORENSICS.md](./MEMORY_FORENSICS.md)** - Deep dive into the 7,762x memory explosion
2. **[GRAPHITI_INTEGRATION.md](./GRAPHITI_INTEGRATION.md)** - Advanced Graphiti patterns
3. **[CYPHER_PRIMER.md](./CYPHER_PRIMER.md)** - GraphRAG query patterns
4. **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - When things go wrong

### Performance Tuning Checklist

- [ ] Set NODE_CREATION_BUFFER to 512 (or lower for small graphs)
- [ ] Enable QUERY_MEM_CAPACITY limits
- [ ] Configure volatile-lru eviction for temporal data
- [ ] Monitor for duplicate UUIDs weekly
- [ ] Set up automated backups before major imports
- [ ] Review slow query log monthly

### Common Pitfalls to Avoid

1. **Never use default NODE_CREATION_BUFFER** with Graphiti
2. **Always check for duplicate UUIDs** after bulk imports
3. **Don't skip memory monitoring** during development
4. **Avoid loading suspicious RDB files** without inspection

### Getting Help

- FalkorDB Issues: [github.com/FalkorDB/FalkorDB](https://github.com/FalkorDB/FalkorDB)
- Graphiti Support: [github.com/getzep/graphiti](https://github.com/getzep/graphiti)
- This Setup: See issues in this repository

---

💡 **Pro Tip**: Start with NODE_CREATION_BUFFER=256 for graphs under 1000 nodes. You can always increase it later, but you can't undo memory fragmentation without a restart.

🚀 **Ready to Build?** You now have a battle-tested FalkorDB setup that won't explode in production. Happy GraphRAG building!