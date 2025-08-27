# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Security & Secrets Management (1Password Integration)

FalkorDB supports two deployment modes:
1. **Standard Mode** (`make up`): Uses default/insecure values suitable for development
2. **Secure Mode** (`make up-secure`): Injects secrets from 1Password HomeLab vault

### Initial Setup (One-time)
```bash
# Setup 1Password vault and create default secrets
make setup-vault

# Verify secrets are configured
make verify-secrets
```

### Secure Deployment
```bash
# Deploy with 1Password secrets injection
make up-secure

# Standard deployment (development, no secrets)
make up
```

### Managing Secrets
```bash
# View secrets in 1Password
op item get "FalkorDB/Core" --vault=HomeLab
op item get "FalkorDB/Integration" --vault=HomeLab
op item get "FalkorDB/OAuth" --vault=HomeLab

# Update API keys (e.g., for Graphiti or OpenAI)
op item edit "37e5lxhox53xsvzp3ozau32nha" --vault=HomeLab \
  "graphiti-api-key=YOUR-ACTUAL-KEY" \
  "openai-api-key=sk-YOUR-ACTUAL-KEY"
```

### Secret References
The `secrets/.env.1password` file contains references (not actual secrets):
- Uses item IDs instead of names due to slashes in titles
- Safe to commit to version control
- Actual secrets stored securely in 1Password
- Ephemeral injection during deployment with immediate cleanup

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

# Restart container (after config changes)
docker compose restart
```

### FalkorDB Operations
```bash
# Test connection
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

#### Sophisticated Backup System (offen/docker-volume-backup) - RECOMMENDED
```bash
# Start automated backup service (runs every 6 hours)
make backup-up

# Check backup service status and recent backups
make backup-status

# Trigger manual backup
make backup-manual

# View backup service logs
make backup-logs

# Stop backup service
make backup-down

# Restore from backup archive
docker run --rm -v falkordb_data:/data -v ~/FalkorDBBackups:/backup alpine \
  tar -xzf /backup/falkordb-latest.tar.gz -C /data --strip-components=2

# Configure external drive sync (edit docker-compose.backup.yml)
# Uncomment the line: - /Volumes/SanDisk/FalkorDBBackups:/external:rw
```

#### Legacy Backup Scripts (still available)
```bash
# Run comprehensive monitoring dashboard
./scripts/monitor.sh

# Create backup (stored in ./backups/)
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh                  # Interactive mode
./scripts/restore.sh -f backup.rdb    # Restore specific file

# Setup automated backups via cron
./scripts/automated-backup.sh setup-cron "0 */6 * * *"

# Open browser interface
./scripts/open-browser.sh
```

### Test Suite Commands

#### Using the unified test runner (./test.sh)
```bash
# Run all tests
./test.sh

# Run quick smoke tests
./test.sh --quick

# Run integration tests with verbose output
./test.sh --integration --verbose

# Run regression tests
./test.sh --regression

# Run tests with coverage
./test.sh --coverage

# Get help
./test.sh --help
```

#### Using Make (alternative)
```bash
# Run all tests
make test

# Run quick smoke tests
make test-quick

# Run specific test suites
make test-integration    # Integration tests
make test-regression     # Regression tests
make test-custom        # Custom entity tests

# Run with coverage
make coverage
make coverage-open      # Open HTML report

# Docker management
make docker-up          # Start FalkorDB
make docker-down        # Stop FalkorDB
make docker-status      # Check status

# Development helpers
make clean             # Clean test artifacts
make lint              # Run linting
make format            # Format code

# Combined workflows
make ci                # Run full CI pipeline
make all               # Start docker, test, coverage
```

#### Direct pytest commands
```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_*_int.py -v     # Integration tests
pytest tests/test_v*.py -v         # Version/regression tests
pytest tests/test_custom*.py -v    # Custom entity tests

# Run with markers
pytest -m "integration" tests/
pytest -m "slow" tests/
```

## Architecture Overview

This is a FalkorDB setup optimized for running multiple Graphiti instances on Apple Silicon M3 MacBooks using OrbStack. Key architectural decisions:

### Port Configuration
- **Redis/FalkorDB protocol**: Port **6379** via `falkordb.local:6379` (OrbStack domain)
- **Browser UI**: Accessible at `https://falkordb-browser.local/` (HTTPS via OrbStack proxy)
- **No port conflicts**: Each service uses its own OrbStack domain (falkordb.local vs redis.langfuse.local)

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

# Connect using OrbStack domain
driver = FalkorDriver(
    host="falkordb.local",  # OrbStack domain
    port=6379,  # Standard Redis port
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
        host="falkordb.local",  # OrbStack domain
        port=6379,  # Standard Redis port
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
With OrbStack domains, port conflicts are eliminated:
```bash
# FalkorDB is accessible at:
falkordb.local:6379  # Redis protocol
falkordb-browser.local  # Browser UI (HTTPS enabled)

# Other services use their own domains:
redis.langfuse.local:6379  # Langfuse Redis
postgres.langfuse.local:5432  # Langfuse PostgreSQL
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

1. **Connection endpoints**:
   - Redis protocol: `falkordb.local:6379`
   - Browser UI: `https://falkordb-browser.local/`
2. **Backup & Restore**:
   - **Sophisticated System** (offen/docker-volume-backup):
     - Start service: `make backup-up` (automated every 6 hours)
     - Manual backup: `make backup-manual`
     - Check status: `make backup-status`
     - Backups stored: `~/FalkorDBBackups/`
     - External sync: Auto-syncs to `/Volumes/SanDisk/` when mounted
   - **Legacy Scripts** (still available):
     - Manual backup: `./scripts/backup.sh`
     - Restore: `./scripts/restore.sh`
3. **Data persistence**: Named volume `falkordb_data` survives container restarts
4. **M3 optimization**: Configured for 8 performance cores (adjust THREAD_COUNT if needed)
5. **Default graph**: `shared_knowledge_graph` is used by all Graphiti instances
6. **Health checks**: Increased timeouts prevent false failures during initialization

## Backup Architecture (offen/docker-volume-backup)

The sophisticated backup system uses `offen/docker-volume-backup` for enterprise-grade features:

### Features
- **Automated Scheduling**: Runs every 6 hours via built-in cron
- **Zero Downtime**: Uses Redis BGSAVE for consistent backups without stopping FalkorDB
- **Dual Storage**: Local backups in `~/FalkorDBBackups/` with optional external drive sync
- **Retention Management**: Automatic cleanup of backups older than 7 days
- **Manual Triggers**: On-demand backups via `make backup-manual`
- **Monitoring**: Check status with `make backup-status`, view logs with `make backup-logs`

### Configuration
Edit `.env` file to adjust:
- `BACKUP_CRON`: Schedule (default: "0 */6 * * *")
- `BACKUP_RETENTION_DAYS`: Days to keep (default: 7)
- `BACKUP_DIR`: Storage location (default: ~/FalkorDBBackups)

### External Drive Support
To enable external drive sync:
1. Edit `docker-compose.backup.yml`
2. Uncomment the line: `- /Volumes/SanDisk/FalkorDBBackups:/external:rw`
3. Restart backup service: `make backup-down && make backup-up`

When the external drive is mounted, backups automatically sync using rsync.