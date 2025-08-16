# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Docker Container Management
```bash
# Start FalkorDB
docker compose up -d

# Stop FalkorDB
docker compose down

# View logs
docker compose logs -f falkordb

# Check container status
docker compose ps
```

### FalkorDB Operations
```bash
# Test connection (using port 6380 to avoid conflicts)
docker exec falkordb redis-cli ping

# Create/verify shared knowledge graph
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "CREATE (n:Init {created: timestamp()})"

# List all graphs
docker exec falkordb redis-cli GRAPH.LIST

# Get graph memory usage
docker exec falkordb redis-cli GRAPH.MEMORY USAGE shared_knowledge_graph

# Check slow queries
docker exec falkordb redis-cli SLOWLOG GET 10
```

### Monitoring & Maintenance
```bash
# Run comprehensive monitoring dashboard
./scripts/monitor.sh

# Create backup (stored in ./backups/)
./scripts/backup.sh

# Open browser interface (https://falkordb.local)
./scripts/open-browser.sh
```

### Test Suite Commands
```bash
# Run basic connectivity test
./run_tests.sh

# Run all tests with detailed output
./run_all_tests.sh

# Run success validation tests
./run_tests_success.sh

# Run custom entity tests
cd tests && ./run_custom_entity_tests.sh

# Run specific test categories
pytest tests/test_*_int.py -v  # Integration tests
pytest tests/test_v*.py -v      # Version/regression tests
```

## Architecture Overview

This is a FalkorDB setup optimized for running multiple Graphiti instances on Apple Silicon M3 MacBooks using OrbStack. Key architectural decisions:

### Port Configuration
- **Redis/FalkorDB protocol**: Port **6380** (not default 6379 to avoid conflicts)
- **Browser UI**: Accessible via `https://falkordb.local` (OrbStack domain with auto HTTPS)
- **Why 6380**: Prevents conflicts with local Redis installations or other services

### Performance Tuning (M3 Optimized)
- `THREAD_COUNT=8`: Matches M3 performance cores for concurrent query processing
- `NODE_CREATION_BUFFER=8192`: Balanced for moderate write loads from Graphiti
- `CACHE_SIZE=50`: Query cache sized for multiple Graphiti instances
- `OMP_THREAD_COUNT=2`: OpenMP parallelization per query
- `maxmemory=4gb`: Memory limit with LRU eviction policy

### OrbStack Integration
- Named volumes for persistence: `falkordb_data`
- Custom domain: `falkordb.local` with automatic SSL certificates
- Volume location: `~/OrbStack/docker/volumes/falkordb_falkordb_data/`
- Zero virtualization overhead on Apple Silicon

## Graphiti Connection Examples

### Basic FalkorDB Connection
```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

# Note: Using port 6380, not default 6379
driver = FalkorDriver(
    host="localhost",
    port=6380,  # Custom port to avoid conflicts
    username="falkor_user",  # Optional
    password="falkor_password",  # Optional
    database="shared_knowledge_graph"  # Shared database for all instances
)

graphiti = Graphiti(graph_driver=driver)
```

### Connection Pooling for Multiple Instances
```python
import asyncio
from falkordb.asyncio import FalkorDB
from redis.asyncio import BlockingConnectionPool

async def create_graphiti_client():
    pool = BlockingConnectionPool(
        host="localhost",
        port=6380,  # Using custom port
        max_connections=16,  # Support multiple concurrent Graphiti instances
        timeout=None,
        decode_responses=True
    )
    
    db = FalkorDB(connection_pool=pool)
    return db
```

## Common Development Tasks

### Performance Tuning
```bash
# Adjust thread count at runtime
docker exec falkordb redis-cli GRAPH.CONFIG SET THREAD_COUNT 16

# Increase cache size for heavy read workloads
docker exec falkordb redis-cli GRAPH.CONFIG SET CACHE_SIZE 100

# Check current configuration
docker exec falkordb redis-cli GRAPH.CONFIG GET "*"
```

### Memory Management
```bash
# Check memory usage
docker exec falkordb redis-cli INFO memory | grep used_memory_human

# Force background save
docker exec falkordb redis-cli BGSAVE

# Clear cache if needed
docker exec falkordb redis-cli FLUSHDB
```

### Database Operations
```bash
# Create additional databases for different projects
docker exec falkordb redis-cli GRAPH.QUERY project1_graph "CREATE ()"
docker exec falkordb redis-cli GRAPH.QUERY project2_graph "CREATE ()"

# Delete a graph
docker exec falkordb redis-cli GRAPH.DELETE unwanted_graph
```

## Troubleshooting Guide

### Port Conflicts
If port 6380 is already in use:
```bash
# Check what's using the port
lsof -i :6380

# Modify docker-compose.yml to use a different port
# Change "6380:6379" to "6381:6379" or another available port
```

### Memory Issues
If experiencing high memory usage:
```bash
# Check current memory consumption
docker exec falkordb redis-cli INFO memory

# Adjust maxmemory in docker-compose.yml
# Modify: --maxmemory 4gb to --maxmemory 8gb

# Restart container
docker compose down && docker compose up -d
```

### OrbStack Specific
```bash
# Verify OrbStack networking
orb config get network_bridge  # Should return 'true'

# Access volume directly
ls ~/OrbStack/docker/volumes/falkordb_falkordb_data/_data/

# Force volume sync
docker compose down
docker volume inspect falkordb_falkordb_data
```

### Slow Query Diagnosis
```bash
# Identify problematic queries
docker exec falkordb redis-cli SLOWLOG GET 10

# For write-heavy workloads, increase buffer
docker exec falkordb redis-cli GRAPH.CONFIG SET NODE_CREATION_BUFFER 16384

# For read-heavy workloads, increase OMP threads
docker exec falkordb redis-cli GRAPH.CONFIG SET OMP_THREAD_COUNT 4
```

## Test Suite Organization

The test suite is organized in the `/tests` directory with the following structure:

## Test Categories
- **Regression Tests** (`test_v*.py`, `test_*regression*.py`): Tests for version-specific issues and regressions
- **Integration Tests** (`test_*_int.py`): Tests for concurrent access, persistence, complex queries
- **Unit Tests** (`test_custom_entities*.py`, `test_falkordb_gaps.py`): Focused tests for specific features
- **Workaround Tests** (`test_workaround*.py`): Demonstrations of potential workarounds

## Test Support Files
- `entities/`: Custom entity definitions for different domains (Arabic, GTD, Islamic Finance)
- `fixtures/`: Test data and scenarios
- `utils/`: Helper utilities and workarounds
- `conftest.py`: Pytest configuration and shared fixtures
- `requirements.txt`: Test dependencies

## Key Test Files
- `test_v0177.py`: Validates that v0.17.7 works with FalkorDB (PR #733 fix)
- `test_minimal_group_id_repro.py`: Minimal reproduction of the group_id issue
- `test_concurrent_access_int.py`: Multi-agent concurrent write tests
- `test_custom_entities_basic.py`: Custom entity definition tests

# Important Notes

1. **Always use port 6380** when connecting from Graphiti or other clients
2. **Browser access** is via `https://falkordb.local` (not localhost:3000)
3. **Backups** are automatically retained for 7 days in `./backups/`
4. **Named volumes** persist data even after `docker compose down`
5. **M3 optimization** assumes 8 performance cores - adjust THREAD_COUNT if needed
6. **Graph name** `shared_knowledge_graph` is used by all Graphiti instances by default