# Debug Commands Quick Reference

Quick lookup for all FalkorDB-Graphiti debugging commands. Copy and paste ready!

## 🚀 Quick Start Commands

```bash
# Start everything
docker compose up -d
pip install 'graphiti-core[falkordb]==0.17.9'
python tests/test_basic_connection.py

# Stop everything
docker compose down

# Full reset
docker compose down -v
rm -rf venv/
```

## 🔍 Connection Debugging

### Basic Health Checks
```bash
# Is FalkorDB running?
docker compose ps | grep falkordb

# Test Redis connection
docker exec falkordb redis-cli ping
# Expected: PONG

# Check port availability
netstat -an | grep 6380
lsof -i :6380

# Test from Python
python -c "import redis; r=redis.Redis(host='localhost', port=6380); print(r.ping())"
```

### Network Diagnostics
```bash
# Check Docker network
docker network ls
docker network inspect falkordb_default

# Test connectivity inside container
docker exec falkordb redis-cli -h localhost -p 6379 ping

# Check OrbStack domains (if using)
ping falkordb.local
curl http://falkordb-browser.local
```

## 📊 Graph Operations

### Graph Management
```bash
# List all graphs
docker exec falkordb redis-cli GRAPH.LIST

# Get graph info
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "MATCH (n) RETURN count(n)"

# Delete a graph (CAUTION!)
docker exec falkordb redis-cli GRAPH.DELETE shared_knowledge_graph

# Create empty graph
docker exec falkordb redis-cli GRAPH.QUERY test_graph "CREATE ()"
```

### Query Monitoring
```bash
# Watch queries in real-time
docker exec -it falkordb redis-cli MONITOR
# Press Ctrl+C to stop

# Check slow queries
docker exec falkordb redis-cli SLOWLOG GET 10

# Get query stats
docker exec falkordb redis-cli INFO commandstats | grep graph
```

## 🐛 Entity Testing

### Test Custom Entities
```bash
# Test all entity domains
python tests/test_custom_entities_basic.py -v

# Test specific domain
python tests/test_custom_entities_basic.py -k arabic -v
python tests/test_custom_entities_basic.py -k gtd -v
python tests/test_custom_entities_basic.py -k islamic -v

# Test minimal reproduction
python tests/test_minimal_group_id_repro.py

# Test with verbose output
pytest tests/test_custom_entities_basic.py -vvs
```

### Entity Validation
```python
# Quick entity validation test
python -c "
from entities.arabic_entities import Student
from entities.gtd_entities import Task
from entities.islamic_finance_entities import Account
print('✅ All entity imports successful')
"

# Test entity creation
python -c "
from entities.gtd_entities import Task, Priority
task = Task(description='Test', context='@home', priority=Priority.B)
print(f'✅ Task created: {task.description}')
"
```

## 🔄 Version Management

### Check Versions
```bash
# Graphiti version
pip show graphiti-core | grep Version
python -c "import graphiti_core; print(graphiti_core.__version__)"

# FalkorDB version
docker exec falkordb redis-cli INFO server | grep redis_version

# Python version
python --version

# All package versions
pip list | grep -E "graphiti|falkor|redis"
```

### Version Testing
```bash
# Test specific version
pip install 'graphiti-core[falkordb]==0.17.9'
python tests/test_v0177.py

# Bisect versions to find regression
for v in 0.17.7 0.17.8 0.17.9 0.17.10 0.17.11; do
    echo "Testing v$v"
    pip install "graphiti-core[falkordb]==$v"
    python tests/test_minimal_group_id_repro.py
done
```

## 📝 Log Analysis

### Container Logs
```bash
# View FalkorDB logs
docker compose logs falkordb

# Follow logs in real-time
docker compose logs -f falkordb

# Last 100 lines
docker compose logs --tail=100 falkordb

# Logs since timestamp
docker compose logs --since 2024-01-01T00:00:00 falkordb

# Search for errors
docker compose logs falkordb 2>&1 | grep -i error
docker compose logs falkordb 2>&1 | grep "group_id"
```

### Test Logs
```bash
# Run tests with detailed output
pytest tests/ -v --tb=short --capture=no

# Save test output
pytest tests/ -v > test_results.txt 2>&1

# Run with debug logging
PYTHONPATH=. python -m pytest tests/ -s -vv --log-cli-level=DEBUG
```

## 🔧 Performance Debugging

### Memory Analysis
```bash
# Check memory usage
docker exec falkordb redis-cli INFO memory

# Get specific memory stats
docker exec falkordb redis-cli INFO memory | grep -E "used_memory_human|used_memory_peak_human"

# Force garbage collection
docker exec falkordb redis-cli MEMORY PURGE

# Check graph memory
docker exec falkordb redis-cli GRAPH.MEMORY USAGE shared_knowledge_graph
```

### Performance Monitoring
```bash
# Monitor performance in real-time
docker stats falkordb

# Check CPU usage
docker exec falkordb top -bn1 | head -20

# Network statistics
docker exec falkordb netstat -an | grep ESTABLISHED

# Disk I/O
docker exec falkordb iostat -x 1
```

## 🛠 Troubleshooting Workflows

### When Connection Fails
```bash
# Step 1: Check if Docker is running
docker info

# Step 2: Check if container is up
docker compose ps

# Step 3: Start if needed
docker compose up -d

# Step 4: Wait for startup
sleep 5

# Step 5: Test connection
docker exec falkordb redis-cli ping

# Step 6: Check logs if still failing
docker compose logs --tail=50 falkordb
```

### When Entities Don't Extract
```bash
# Step 1: Check Graphiti version
pip show graphiti-core | grep Version

# Step 2: If >= 0.17.10, downgrade
pip install 'graphiti-core[falkordb]==0.17.9'

# Step 3: Test entity import
python -c "from entities.arabic_entities import *; print('✅')"

# Step 4: Run minimal test
python tests/test_minimal_group_id_repro.py

# Step 5: Check for errors
docker compose logs falkordb | grep -i error
```

## 🔄 Backup & Restore

### Backup Operations
```bash
# Manual backup
./scripts/backup.sh

# Backup with timestamp
docker exec falkordb redis-cli BGSAVE
docker cp falkordb:/data/dump.rdb ./backups/dump-$(date +%Y%m%d-%H%M%S).rdb

# Check backup status
docker exec falkordb redis-cli LASTSAVE

# List backups
ls -lht ~/FalkorDBBackups/*.tar.gz | head -10
```

### Restore Operations
```bash
# Restore from backup
./scripts/restore.sh

# Restore specific file
docker cp ./backups/dump.rdb falkordb:/data/dump.rdb
docker compose restart falkordb

# Verify restore
docker exec falkordb redis-cli GRAPH.LIST
```

## 🔐 Security & Secrets

### 1Password Integration
```bash
# Check vault
op vault get HomeLab

# Deploy with secrets
make up-secure

# Deploy without secrets (dev)
make up

# Verify secrets injected
docker exec falkordb env | grep -E "NEXTAUTH_SECRET|FALKORDB_AUTH"
```

## 🧪 Testing Commands

### Run Test Suites
```bash
# All tests
make test

# Quick tests
make test-quick

# Integration tests
make test-integration

# Regression tests
make test-regression

# With coverage
make coverage

# Specific test file
pytest tests/test_basic_connection.py -v

# Run tests in watch mode
pytest-watch tests/
```

### Debugging Tests
```bash
# Run with debugger
python -m pdb tests/test_custom_entities_basic.py

# Run with breakpoint
pytest tests/test_custom_entities_basic.py --pdb

# Run single test method
pytest tests/test_custom_entities_basic.py::TestBasicCustomEntities::test_arabic_entity_extraction -v
```

## 🚨 Emergency Commands

### Complete System Reset
```bash
#!/bin/bash
# nuclear_reset.sh - Complete reset when nothing works

# Stop everything
docker compose down -v
docker system prune -af

# Clean Python environment
rm -rf venv/ __pycache__/ .pytest_cache/

# Clean data
rm -rf backups/*.rdb
rm -rf ~/FalkorDBBackups/*

# Reinstall
python -m venv venv
source venv/bin/activate
pip install -r tests/requirements.txt
pip install 'graphiti-core[falkordb]==0.17.9'

# Start fresh
docker compose up -d
sleep 5
docker exec falkordb redis-cli ping

# Test
python tests/test_basic_connection.py
```

### Quick Diagnostic Script
```bash
#!/bin/bash
# diagnose.sh - Quick system diagnostic

echo "=== System Status ==="
echo "Docker: $(docker --version)"
echo "Python: $(python --version)"
echo "Graphiti: $(pip show graphiti-core | grep Version)"
echo ""
echo "=== Container Status ==="
docker compose ps
echo ""
echo "=== Connection Test ==="
docker exec falkordb redis-cli ping
echo ""
echo "=== Graph List ==="
docker exec falkordb redis-cli GRAPH.LIST
echo ""
echo "=== Recent Errors ==="
docker compose logs --tail=20 falkordb | grep -i error
```

## 📋 Copy-Paste Templates

### Debug Session Start
```bash
# Start a debugging session
cd /Users/adeel/Documents/1_projects/falkordb
source venv/bin/activate
docker compose up -d
docker compose ps
docker exec falkordb redis-cli ping
python -c "import graphiti_core; print(f'Graphiti {graphiti_core.__version__}')"
```

### Test Run Template
```bash
# Standard test run
cd /Users/adeel/Documents/1_projects/falkordb
source venv/bin/activate
pytest tests/test_basic_connection.py -v
pytest tests/test_custom_entities_basic.py -v
python tests/test_minimal_group_id_repro.py
```

---

## See Also

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Detailed troubleshooting guide
- [Entity Debugging Visual](entity-debugging-visual.md) - Visual debugging diagrams
- [Version Compatibility Matrix](version-compatibility-matrix.md) - Version compatibility details