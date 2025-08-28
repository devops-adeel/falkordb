# FalkorDB for Graphiti on OrbStack

A production-ready FalkorDB setup optimized for running multiple Graphiti instances on M3 MacBook Pro using OrbStack.

## Overview

This repository provides a Docker Compose setup for FalkorDB, a high-performance graph database optimized for GraphRAG applications. It's configured specifically for:

- **Apple Silicon M3** performance optimization
- **Multiple concurrent Graphiti instances** sharing a single knowledge graph
- **Persistent storage** with automatic backups
- **Low-latency queries** for real-time AI agent interactions
- **OrbStack** integration for optimal Docker performance on macOS

## 📚 Documentation

### For Developers New to FalkorDB/GraphRAG

- **[FalkorDB + Graphiti Guide](./docs/FALKORDB_GRAPHITI_GUIDE.md)** - Start here! Complete guide with graph database primer
- **[Memory Forensics](./docs/MEMORY_FORENSICS.md)** - Deep dive into the 7,762x memory expansion issue and solution
- **[Graphiti Integration](./docs/GRAPHITI_INTEGRATION.md)** - Practical patterns for bi-temporal knowledge graphs
- **[Cypher Query Primer](./docs/CYPHER_PRIMER.md)** - Learn Cypher with GraphRAG-specific examples
- **[Troubleshooting Guide](./docs/TROUBLESHOOTING.md)** - Systematic diagnostic workflows for common issues

### Quick Links

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [Quick Start Guide](./docs/FALKORDB_GRAPHITI_GUIDE.md#quick-start) | Get running in 5 minutes | 5 min |
| [Memory Explosion Case](./docs/MEMORY_FORENSICS.md#the-discovery) | Learn from our 451KB → 3.5GB disaster | 15 min |
| [Connection Patterns](./docs/GRAPHITI_INTEGRATION.md#connection-patterns) | Multi-agent setup examples | 10 min |
| [Emergency Procedures](./docs/TROUBLESHOOTING.md#emergency-procedures) | When things go wrong | 5 min |

### ⚠️ Critical Configuration

If you remember nothing else, remember this:
```yaml
NODE_CREATION_BUFFER: 512  # NEVER use default 16384!
```
This single setting prevents the catastrophic memory explosion detailed in our [forensics analysis](./docs/MEMORY_FORENSICS.md).

## Features

- 🚀 **Optimized for M3**: ARM64 native images, no emulation overhead
- 📊 **Shared Knowledge Graph**: Single database serving multiple Graphiti clients
- 💾 **Persistent Storage**: Data survives container restarts
- 🔍 **Monitoring Tools**: Built-in scripts for health checks and performance monitoring
- 🔒 **Automatic Backups**: Scheduled backups with retention management
- ⚡ **Low Latency**: Sub-10ms query response times for GraphRAG operations
- 🌐 **OrbStack Integration**: Access browser UI via custom domain with automatic HTTPS
- 🔐 **Secure by Default**: HTTPS with auto-generated trusted certificates

## Prerequisites

- macOS with Apple Silicon (M1/M2/M3)
- [OrbStack](https://orbstack.dev/) installed and running
- Docker Compose (included with OrbStack)
- At least 8GB free RAM
- 10GB free disk space

## Quick Start

### 1. Clone and Setup

```bash
# Clone this repository (or download the files)
git clone <repository-url> falkordb
cd falkordb

# Start FalkorDB
docker compose up -d

# Verify it's running
docker compose ps

# Check logs
docker compose logs -f falkordb
```

### 2. Initialize the Database

```bash
# Test connection (note: using port 6380 to avoid conflicts)
docker exec falkordb redis-cli ping
# Should return: PONG

# Create the shared knowledge graph
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph \
  "CREATE (n:Init {created: timestamp()})"

# Verify database exists
docker exec falkordb redis-cli GRAPH.LIST
# Should show: 1) "shared_knowledge_graph"
```

**Note**: FalkorDB is configured with OrbStack networking:
- **Browser UI**: Access via `https://falkordb.local` (no port needed)
- **Redis/FalkorDB protocol**: Port **6380** (instead of default 6379)
- **Automatic HTTPS**: OrbStack provides SSL certificates automatically

This provides a clean, professional setup without port conflicts.

### 3. Access the Browser Interface

```bash
# Open the FalkorDB browser (opens https://falkordb.local)
./scripts/open-browser.sh

# Or navigate directly to:
# https://falkordb.local (HTTPS with auto certificates)
# http://falkordb.local (HTTP alternative)
```

### 4. Monitor Performance

```bash
# Run the monitoring dashboard
./scripts/monitor.sh

# Watch real-time queries (useful for debugging)
docker exec -it falkordb redis-cli MONITOR
```

## Configuration

### Docker Compose Settings

The `docker-compose.yml` is pre-configured with optimal settings for M3 MacBook Pro:

```yaml
environment:
  - FALKORDB_ARGS=THREAD_COUNT 8 NODE_CREATION_BUFFER 8192 CACHE_SIZE 50 OMP_THREAD_COUNT 2
  - REDIS_ARGS=--maxmemory 4gb --maxmemory-policy allkeys-lru --save 60 1000
```

#### Key Parameters:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `THREAD_COUNT` | 8 | Matches M3's performance cores for concurrent queries |
| `NODE_CREATION_BUFFER` | 8192 | Balanced for moderate write loads |
| `CACHE_SIZE` | 50 | Query cache for multiple Graphiti instances |
| `OMP_THREAD_COUNT` | 2 | Parallelization per query |
| `maxmemory` | 4gb | Memory limit for Redis/FalkorDB |
| `save` | 60 1000 | Auto-save every 60s if 1000+ keys changed |

### Environment Variables

The `.env` file contains connection details for Graphiti clients:

```bash
FALKORDB_HOST=localhost
FALKORDB_PORT=6380  # Using 6380 to avoid conflicts
FALKORDB_DATABASE=shared_knowledge_graph
# Browser UI accessed via https://falkordb.local (OrbStack domain)
```

## Connecting from Graphiti

### Python Example

```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

# Create FalkorDB driver (note: using port 6380)
driver = FalkorDriver(
    host="localhost",
    port=6380,  # Using 6380 to avoid conflicts
    database="shared_knowledge_graph"  # All instances use same DB
)

# Initialize Graphiti with the driver
graphiti = Graphiti(graph_driver=driver)
```

### Connection Pooling for Multiple Instances

```python
import asyncio
from falkordb.asyncio import FalkorDB
from redis.asyncio import BlockingConnectionPool

async def create_graphiti_client():
    # Connection pool for concurrent access
    pool = BlockingConnectionPool(
        host="localhost",
        port=6380,  # Using 6380 to avoid conflicts
        max_connections=16,
        timeout=None,
        decode_responses=True
    )
    
    db = FalkorDB(connection_pool=pool)
    return db
```

## Backup and Restore

### Automatic Backups

```bash
# Create a backup
./scripts/backup.sh

# Backups are stored in ./backups/ with timestamps
# Old backups are automatically cleaned up after 7 days
```

### Manual Restore

```bash
# Stop FalkorDB
docker compose down

# Copy backup to volume
cp backups/falkordb_backup_20250114_120000.rdb \
   ~/OrbStack/docker/volumes/falkordb_falkordb_data/_data/dump.rdb

# Start FalkorDB
docker compose up -d
```

## Performance Monitoring

### Real-time Monitoring

```bash
# Full monitoring dashboard
./scripts/monitor.sh

# Memory usage only
docker exec falkordb redis-cli INFO memory

# Graph-specific memory
docker exec falkordb redis-cli GRAPH.MEMORY USAGE shared_knowledge_graph

# Check slow queries
docker exec falkordb redis-cli SLOWLOG GET 10
```

### Performance Metrics

Expected performance on M3 MacBook Pro:
- Query latency: < 10ms for most GraphRAG operations
- Throughput: 1000+ queries/second
- Memory usage: ~500MB base + graph data
- CPU usage: < 1% idle, 10-20% under load

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs falkordb

# Verify OrbStack is running
docker ps

# Check port availability
lsof -i :6380  # Redis protocol port

# Check if OrbStack network bridge is enabled
orb config get network_bridge  # Should return 'true'
```

### High Memory Usage

```bash
# Check current memory
docker exec falkordb redis-cli INFO memory

# Flush cache if needed
docker exec falkordb redis-cli FLUSHDB

# Adjust maxmemory in docker-compose.yml
```

### Slow Queries

```bash
# Identify slow queries
docker exec falkordb redis-cli SLOWLOG GET 10

# Increase cache size in docker-compose.yml
# CACHE_SIZE 100

# Optimize OMP_THREAD_COUNT for your workload
```

### Data Persistence Issues

```bash
# Verify volume exists
docker volume ls | grep falkordb

# Check volume location in OrbStack
ls ~/OrbStack/docker/volumes/falkordb_falkordb_data/

# Force save
docker exec falkordb redis-cli BGSAVE
```

## Maintenance

### Daily Tasks

```bash
# Monitor health
./scripts/monitor.sh

# Check logs for errors
docker compose logs --tail=100 falkordb | grep -i error
```

### Weekly Tasks

```bash
# Create backup
./scripts/backup.sh

# Check disk usage
du -sh ~/OrbStack/docker/volumes/falkordb_falkordb_data/
```

### Updates

```bash
# Pull latest FalkorDB image
docker compose pull

# Recreate container with new image
docker compose up -d --force-recreate
```

## Architecture Notes

### Why FalkorDB?

- **Sparse Matrix Representation**: Uses GraphBLAS for efficient graph operations
- **Sub-millisecond Queries**: Optimized for GraphRAG workloads
- **Multi-tenant Support**: Perfect for multiple Graphiti instances
- **Memory Efficient**: v4.8 uses 42% less memory than previous versions

### OrbStack Advantages

- **Native Performance**: No virtualization overhead on Apple Silicon
- **Fast Volumes**: Named volumes are faster than bind mounts
- **Low Resource Usage**: 0.1% CPU when idle
- **Easy Debugging**: Direct access to volumes via Finder
- **Automatic Domains**: Access services via `.local` domains without port numbers
- **Built-in HTTPS**: Automatic SSL certificates for secure local development

### Graphiti Integration

FalkorDB serves as the persistent knowledge graph for Graphiti's:
- Entity storage and relationships
- Temporal fact tracking
- Vector embeddings (when configured)
- Fast graph traversal for context retrieval

## Advanced Configuration

### Custom Memory Tuning

For different workloads, adjust in `docker-compose.yml`:

```yaml
# For write-heavy workloads
FALKORDB_ARGS=NODE_CREATION_BUFFER 16384

# For read-heavy workloads
FALKORDB_ARGS=CACHE_SIZE 100

# For larger graphs
REDIS_ARGS=--maxmemory 8gb
```

### Multi-Database Setup

To run separate databases for different projects:

```bash
# Create additional databases
docker exec falkordb redis-cli GRAPH.QUERY project1_graph "CREATE ()"
docker exec falkordb redis-cli GRAPH.QUERY project2_graph "CREATE ()"

# Connect Graphiti to specific database
driver = FalkorDriver(database="project1_graph")
```

## Resources

- [FalkorDB Documentation](https://docs.falkordb.com/)
- [Graphiti Documentation](https://github.com/getzep/graphiti)
- [OrbStack Documentation](https://docs.orbstack.dev/)
- [GraphRAG Best Practices](https://www.falkordb.com/blog/)

## License

This configuration is provided as-is for personal and commercial use.

## Support

For issues specific to:
- This setup: Create an issue in this repository
- FalkorDB: [FalkorDB GitHub](https://github.com/FalkorDB/FalkorDB)
- Graphiti: [Graphiti GitHub](https://github.com/getzep/graphiti)
- OrbStack: [OrbStack Support](https://orbstack.dev/support)