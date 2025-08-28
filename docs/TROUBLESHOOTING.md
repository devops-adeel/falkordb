# FalkorDB + Graphiti Troubleshooting Guide

> **Purpose**: Systematic diagnostic workflows for common issues with FalkorDB in GraphRAG workloads

## Quick Diagnosis Flowchart

```
Container won't start? → Check [Startup Issues](#startup-issues)
                ↓
High memory usage? → Check [Memory Problems](#memory-problems)
                ↓
Slow queries? → Check [Performance Issues](#performance-issues)
                ↓
Data inconsistency? → Check [Data Integrity](#data-integrity)
                ↓
Connection errors? → Check [Connection Problems](#connection-problems)
```

---

## Table of Contents
1. [Startup Issues](#startup-issues)
2. [Memory Problems](#memory-problems)
3. [Performance Issues](#performance-issues)
4. [Data Integrity](#data-integrity)
5. [Connection Problems](#connection-problems)
6. [Backup and Recovery](#backup-and-recovery)
7. [Emergency Procedures](#emergency-procedures)
8. [Diagnostic Scripts](#diagnostic-scripts)

---

## Startup Issues

### Container Fails to Start

#### Symptom: Exit Code 137

```bash
docker logs falkordb
# Shows: "falkordb exited with code 137"
```

**Diagnosis**: OOM (Out of Memory) kill

**Solution**:
```bash
# 1. Check available memory
docker system df
free -h

# 2. Reduce memory limits
# Edit docker-compose.yml:
    environment:
      - REDIS_ARGS=--maxmemory 1gb  # Reduce from 2gb
    deploy:
      resources:
        limits:
          memory: 2G  # Reduce from 4G

# 3. Restart with clean state
docker compose down
docker volume rm falkordb_data  # WARNING: Deletes data!
docker compose up -d
```

#### Symptom: Port Already in Use

```bash
docker compose up
# Error: bind: address already in use
```

**Diagnosis**: Port conflict

**Solution**:
```bash
# 1. Find what's using the port
lsof -i :6379
# or
netstat -anp | grep 6379

# 2. Option A: Stop conflicting service
brew services stop redis  # If homebrew Redis

# 3. Option B: Use different port
# Edit docker-compose.yml:
    ports:
      - "6380:6379"  # Map to different host port

# 4. Update connection strings
export FALKORDB_PORT=6380
```

#### Symptom: Volume Mount Issues

```bash
docker compose up
# Error: mount: permission denied
```

**Solution**:
```bash
# 1. Check volume permissions
ls -la ~/OrbStack/docker/volumes/falkordb_data/

# 2. Fix permissions
sudo chown -R $(whoami):$(whoami) ~/OrbStack/docker/volumes/falkordb_data/

# 3. Or use named volume instead of bind mount
# In docker-compose.yml:
volumes:
  falkordb_data:
    driver: local  # Use Docker-managed volume
```

### FalkorDB Module Won't Load

```bash
docker logs falkordb
# Error: "Module /var/lib/falkordb/bin/falkordb.so failed to load"
```

**Diagnosis**: Architecture mismatch or corrupted module

**Solution**:
```bash
# 1. Verify architecture
docker exec falkordb uname -m
# Should match your system (arm64 for M3)

# 2. Pull correct image
docker pull falkordb/falkordb:v4.2.2-arm64

# 3. Force recreate
docker compose down
docker compose up -d --force-recreate
```

---

## Memory Problems

### Detecting Memory Issues

```bash
#!/bin/bash
# memory_monitor.sh - Real-time memory monitoring

while true; do
    echo "=== $(date) ==="
    
    # Container stats
    docker stats --no-stream falkordb | grep -v CONTAINER
    
    # Redis memory info
    docker exec falkordb redis-cli INFO memory | grep -E "used_memory_human|used_memory_peak_human|mem_fragmentation_ratio"
    
    # Graph memory
    docker exec falkordb redis-cli GRAPH.MEMORY USAGE shared_knowledge_graph 2>/dev/null || echo "No graph yet"
    
    sleep 5
done
```

### Memory Explosion (7,762x Issue)

**Symptoms**:
- Memory usage jumps from MB to GB suddenly
- Container crashes with exit code 137
- System becomes unresponsive

**Root Cause Check**:
```bash
# Check for duplicate UUIDs (primary cause)
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH (n)
  WHERE EXISTS(n.uuid)
  WITH n.uuid as uuid, COUNT(*) as cnt
  WHERE cnt > 1
  RETURN uuid, cnt
  ORDER BY cnt DESC
  LIMIT 10
"

# Check NODE_CREATION_BUFFER setting
docker exec falkordb redis-cli GRAPH.CONFIG GET NODE_CREATION_BUFFER
# Should be 512 or less, NOT 16384!
```

**Emergency Fix**:
```bash
# 1. Stop container immediately
docker compose stop falkordb

# 2. Create emergency config
cat > docker-compose.override.yml << EOF
services:
  falkordb:
    environment:
      - FALKORDB_ARGS=NODE_CREATION_BUFFER 256 QUERY_MEM_CAPACITY 134217728
      - REDIS_ARGS=--maxmemory 1gb --maxmemory-policy volatile-lru
EOF

# 3. Start with override
docker compose up -d

# 4. Clean up duplicates
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH (n)
  WHERE EXISTS(n.uuid)
  WITH n.uuid as uuid, COLLECT(n) as nodes
  WHERE SIZE(nodes) > 1
  UNWIND nodes[1..] as duplicate
  DETACH DELETE duplicate
"
```

### Memory Leak Detection

```python
#!/usr/bin/env python3
# detect_memory_leak.py

import time
import docker
import matplotlib.pyplot as plt

client = docker.from_env()
container = client.containers.get('falkordb')

memory_samples = []
timestamps = []
start_time = time.time()

print("Monitoring memory for 10 minutes...")
for _ in range(120):  # 10 minutes at 5-second intervals
    stats = container.stats(stream=False)
    memory_mb = stats['memory_stats']['usage'] / 1024 / 1024
    elapsed = time.time() - start_time
    
    memory_samples.append(memory_mb)
    timestamps.append(elapsed)
    
    # Detect sudden spike
    if len(memory_samples) > 1:
        growth_rate = (memory_samples[-1] - memory_samples[-2]) / memory_samples[-2]
        if growth_rate > 0.5:  # 50% growth in 5 seconds
            print(f"⚠️ SPIKE DETECTED: {growth_rate*100:.1f}% growth at {elapsed:.1f}s")
    
    time.sleep(5)

# Check for steady growth (leak indicator)
first_quarter = sum(memory_samples[:30]) / 30
last_quarter = sum(memory_samples[-30:]) / 30
leak_indicator = (last_quarter - first_quarter) / first_quarter

if leak_indicator > 0.2:  # 20% growth over 10 minutes
    print(f"🚨 POSSIBLE MEMORY LEAK: {leak_indicator*100:.1f}% growth")
else:
    print(f"✅ Memory stable: {leak_indicator*100:.1f}% change")

# Plot results
plt.plot(timestamps, memory_samples)
plt.xlabel('Time (seconds)')
plt.ylabel('Memory (MB)')
plt.title('FalkorDB Memory Usage Over Time')
plt.savefig('memory_analysis.png')
print("Graph saved to memory_analysis.png")
```

---

## Performance Issues

### Slow Query Diagnosis

```bash
#!/bin/bash
# slow_query_analyzer.sh

echo "=== Slow Query Analysis ==="

# 1. Get slow log
echo "Recent slow queries:"
docker exec falkordb redis-cli SLOWLOG GET 10

# 2. Check current query
echo -e "\nCurrently executing:"
docker exec falkordb redis-cli CLIENT LIST | grep -E "cmd=GRAPH.QUERY"

# 3. Get query execution plan
echo -e "\nTesting query performance:"
time docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  EXPLAIN
  MATCH (n:Entity)-[:RELATES_TO*1..3]-(m:Entity)
  WHERE n.group_id = 'test'
  RETURN n, m
  LIMIT 10
"

# 4. Check indices
echo -e "\nAvailable indices:"
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "CALL db.indexes()"
```

### Query Optimization Workflow

```cypher
-- Step 1: Profile the slow query
PROFILE
MATCH (n:Entity {group_id: 'tech'})-[:RELATES_TO*1..3]-(m:Entity)
WHERE n.confidence > 0.8
RETURN n, m
LIMIT 10

-- Step 2: Check if indices are being used
CALL db.indexes()

-- Step 3: Create missing indices
CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.group_id)
CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.confidence)

-- Step 4: Rewrite query for efficiency
-- Instead of variable-length path:
MATCH (n:Entity {group_id: 'tech'})
WHERE n.confidence > 0.8
CALL {
  WITH n
  MATCH (n)-[:RELATES_TO]-(m1:Entity)
  RETURN m1 as m
  UNION
  WITH n  
  MATCH (n)-[:RELATES_TO*2]-(m2:Entity)
  RETURN m2 as m
  UNION
  WITH n
  MATCH (n)-[:RELATES_TO*3]-(m3:Entity)
  RETURN m3 as m
}
RETURN n, m
LIMIT 10
```

### Cache Tuning

```bash
# Check cache statistics
docker exec falkordb redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"

# Calculate hit rate
docker exec falkordb bash -c "
  redis-cli INFO stats | grep -E 'keyspace_(hits|misses)' | 
  awk -F: '{print \$2}' | 
  awk '{s+=\$1} END {print \"Hit rate: \" (NR==2 ? s/(s+\$1)*100 : 0) \"%\"}'
"

# Adjust cache size if hit rate < 70%
docker exec falkordb redis-cli GRAPH.CONFIG SET CACHE_SIZE 100

# Clear cache if stale
docker exec falkordb redis-cli GRAPH.CONFIG SET CACHE_SIZE 0
docker exec falkordb redis-cli GRAPH.CONFIG SET CACHE_SIZE 50
```

---

## Data Integrity

### Duplicate UUID Detection and Cleanup

```python
#!/usr/bin/env python3
# cleanup_duplicates.py

import redis
import json
from collections import defaultdict

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Find all duplicates
query = """
MATCH (n)
WHERE EXISTS(n.uuid)
RETURN n.uuid as uuid, 
       ID(n) as internal_id,
       labels(n) as labels,
       n.created as created,
       properties(n) as props
ORDER BY n.uuid, n.created
"""

result = r.execute_command('GRAPH.QUERY', 'shared_knowledge_graph', query)

# Group by UUID
duplicates = defaultdict(list)
for row in result[1:-1]:  # Skip header and stats
    uuid = row[0]
    duplicates[uuid].append({
        'internal_id': row[1],
        'labels': row[2],
        'created': row[3],
        'props': row[4]
    })

# Process duplicates
for uuid, nodes in duplicates.items():
    if len(nodes) > 1:
        print(f"\n[DUPLICATE] UUID: {uuid}")
        print(f"  Found {len(nodes)} instances")
        
        # Keep the oldest (or customize logic)
        nodes.sort(key=lambda x: x['created'] or 0)
        keeper = nodes[0]
        to_delete = nodes[1:]
        
        print(f"  Keeping: ID={keeper['internal_id']} created={keeper['created']}")
        
        for node in to_delete:
            print(f"  Deleting: ID={node['internal_id']}")
            delete_query = f"MATCH (n) WHERE ID(n) = {node['internal_id']} DETACH DELETE n"
            r.execute_command('GRAPH.QUERY', 'shared_knowledge_graph', delete_query)

print(f"\n✅ Cleanup complete. Processed {len([d for d in duplicates.values() if len(d) > 1])} duplicate sets")
```

### Data Validation

```bash
#!/bin/bash
# validate_graph.sh

echo "=== Graph Validation ==="

# 1. Check node counts
echo "Node statistics:"
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH (n)
  RETURN labels(n)[0] as label, COUNT(*) as count
  ORDER BY count DESC
"

# 2. Check relationship counts
echo -e "\nRelationship statistics:"
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH ()-[r]-()
  RETURN type(r) as type, COUNT(*) as count
  ORDER BY count DESC
"

# 3. Check for orphaned nodes
echo -e "\nOrphaned nodes:"
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH (n)
  WHERE NOT EXISTS((n)-[]-())
  RETURN labels(n)[0] as label, COUNT(*) as orphaned
"

# 4. Check temporal consistency
echo -e "\nTemporal inconsistencies:"
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH (n:Fact)
  WHERE EXISTS(n.valid_from) AND EXISTS(n.valid_to)
    AND n.valid_from > n.valid_to
  RETURN COUNT(*) as invalid_temporal_facts
"

# 5. Check UUID uniqueness
echo -e "\nUUID duplicates:"
docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH (n)
  WHERE EXISTS(n.uuid)
  WITH n.uuid as uuid, COUNT(*) as cnt
  WHERE cnt > 1
  RETURN COUNT(*) as duplicate_uuid_groups
"
```

---

## Connection Problems

### Connection Pool Exhaustion

**Symptoms**:
- Timeout errors
- "Too many connections" errors
- Intermittent connection failures

**Diagnosis**:
```bash
# Check current connections
docker exec falkordb redis-cli CLIENT LIST | wc -l

# Check connection details
docker exec falkordb redis-cli CLIENT LIST | awk '{print $2}' | cut -d= -f2 | sort | uniq -c

# Check max connections
docker exec falkordb redis-cli CONFIG GET maxclients
```

**Solution**:
```python
# Fix connection leak in Python
from contextlib import contextmanager
import redis
from redis.connection import ConnectionPool

# Create global pool
pool = ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,
    socket_keepalive=True,
    socket_connect_timeout=5,
    retry_on_timeout=True
)

@contextmanager
def get_redis_connection():
    """Ensure connections are properly returned to pool"""
    conn = redis.Redis(connection_pool=pool)
    try:
        yield conn
    finally:
        # Connection automatically returned to pool
        pass

# Usage
with get_redis_connection() as r:
    r.execute_command('GRAPH.QUERY', 'shared_knowledge_graph', 'RETURN 1')
```

### Network Issues

```bash
#!/bin/bash
# network_diagnostic.sh

echo "=== Network Diagnostics ==="

# 1. Test basic connectivity
echo "Ping test:"
docker exec falkordb redis-cli ping

# 2. Test from different locations
echo -e "\nFrom localhost:"
redis-cli -h localhost -p 6379 ping 2>/dev/null || echo "Failed"

echo "From Docker network:"
docker run --rm --network falkordb_default redis:alpine redis-cli -h falkordb ping 2>/dev/null || echo "Failed"

# 3. Check DNS resolution (OrbStack)
echo -e "\nDNS resolution:"
nslookup falkordb.local
ping -c 1 falkordb.local

# 4. Check port binding
echo -e "\nPort binding:"
docker port falkordb

# 5. Check firewall (macOS)
echo -e "\nFirewall status:"
sudo pfctl -s rules 2>/dev/null | grep 6379 || echo "No specific rules for port 6379"
```

---

## Backup and Recovery

### Automated Backup Verification

```bash
#!/bin/bash
# verify_backup.sh

BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup.rdb>"
    exit 1
fi

echo "=== Backup Verification ==="

# 1. Check file integrity
echo "File details:"
ls -lh $BACKUP_FILE
file $BACKUP_FILE

# 2. Validate RDB format
echo -e "\nRDB validation:"
redis-check-rdb $BACKUP_FILE

# 3. Test restore in temporary container
echo -e "\nTest restore:"
docker run -d --name falkordb-test \
    -v $(pwd)/$BACKUP_FILE:/data/dump.rdb:ro \
    falkordb/falkordb:v4.2.2

sleep 5

# 4. Verify data
echo -e "\nData verification:"
docker exec falkordb-test redis-cli GRAPH.LIST
docker exec falkordb-test redis-cli GRAPH.QUERY shared_knowledge_graph "MATCH (n) RETURN COUNT(n)"

# 5. Cleanup
docker rm -f falkordb-test

echo -e "\n✅ Backup verification complete"
```

### Point-in-Time Recovery

```bash
#!/bin/bash
# point_in_time_recovery.sh

RECOVERY_TIME=$1  # Format: "2025-01-15 14:00:00"

echo "=== Point-in-Time Recovery ==="

# 1. Find appropriate backup
BACKUP_DIR=~/FalkorDBBackups
RECOVERY_TIMESTAMP=$(date -d "$RECOVERY_TIME" +%s)

BEST_BACKUP=""
BEST_DIFF=999999999

for backup in $BACKUP_DIR/*.rdb; do
    BACKUP_TIME=$(stat -f %m "$backup" 2>/dev/null || stat -c %Y "$backup")
    DIFF=$((RECOVERY_TIMESTAMP - BACKUP_TIME))
    
    if [ $DIFF -ge 0 ] && [ $DIFF -lt $BEST_DIFF ]; then
        BEST_BACKUP=$backup
        BEST_DIFF=$DIFF
    fi
done

if [ -z "$BEST_BACKUP" ]; then
    echo "❌ No suitable backup found"
    exit 1
fi

echo "Found backup: $BEST_BACKUP"
echo "Backup is $((BEST_DIFF / 3600)) hours before recovery point"

# 2. Stop current instance
docker compose stop falkordb

# 3. Backup current data
cp ~/OrbStack/docker/volumes/falkordb_data/_data/dump.rdb \
   ~/OrbStack/docker/volumes/falkordb_data/_data/dump.rdb.before_recovery

# 4. Restore backup
cp $BEST_BACKUP ~/OrbStack/docker/volumes/falkordb_data/_data/dump.rdb

# 5. Start with replay from point
docker compose up -d

echo "✅ Recovered to nearest point before $RECOVERY_TIME"
```

---

## Emergency Procedures

### Emergency Memory Relief

```bash
#!/bin/bash
# emergency_memory_relief.sh

echo "🚨 EMERGENCY MEMORY RELIEF PROCEDURE"

# 1. Immediate cache clear
docker exec falkordb redis-cli FLUSHDB ASYNC

# 2. Drop query cache
docker exec falkordb redis-cli GRAPH.CONFIG SET CACHE_SIZE 0

# 3. Force garbage collection
docker exec falkordb redis-cli MEMORY PURGE

# 4. Reduce memory limit dynamically
docker exec falkordb redis-cli CONFIG SET maxmemory 500mb
docker exec falkordb redis-cli CONFIG SET maxmemory-policy volatile-lru

# 5. Kill long-running queries
docker exec falkordb redis-cli CLIENT LIST | grep "GRAPH.QUERY" | \
    awk '{print $1}' | cut -d= -f2 | \
    xargs -I{} docker exec falkordb redis-cli CLIENT KILL ID {}

echo "✅ Emergency procedures applied"
echo "⚠️ Restart container when stable: docker compose restart falkordb"
```

### Data Export Before Crash

```python
#!/usr/bin/env python3
# emergency_export.py

import redis
import json
import sys

print("🚨 EMERGENCY DATA EXPORT")

try:
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Export critical nodes
    query = """
    MATCH (n)
    WHERE EXISTS(n.uuid)
    RETURN n.uuid as uuid, 
           labels(n) as labels,
           properties(n) as props
    LIMIT 10000
    """
    
    result = r.execute_command('GRAPH.QUERY', 'shared_knowledge_graph', query)
    
    # Save to file
    with open('emergency_export.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ Exported {len(result)-2} nodes to emergency_export.json")
    
except Exception as e:
    print(f"❌ Export failed: {e}")
    sys.exit(1)
```

### Container Recovery

```bash
#!/bin/bash
# container_recovery.sh

echo "=== Container Recovery Procedure ==="

# 1. Get container state
CONTAINER_STATE=$(docker inspect falkordb --format='{{.State.Status}}')
echo "Container state: $CONTAINER_STATE"

if [ "$CONTAINER_STATE" = "running" ]; then
    echo "Container is running, checking health..."
    
    # 2. Health check
    if docker exec falkordb redis-cli ping > /dev/null 2>&1; then
        echo "✅ Container is healthy"
    else
        echo "⚠️ Container unresponsive, restarting..."
        docker compose restart falkordb
    fi
    
elif [ "$CONTAINER_STATE" = "exited" ]; then
    # 3. Check exit code
    EXIT_CODE=$(docker inspect falkordb --format='{{.State.ExitCode}}')
    echo "Exit code: $EXIT_CODE"
    
    if [ "$EXIT_CODE" = "137" ]; then
        echo "❌ OOM Kill detected, reducing memory..."
        # Apply memory reduction
        sed -i.bak 's/maxmemory 4gb/maxmemory 2gb/' docker-compose.yml
    fi
    
    # 4. Start container
    docker compose up -d
    
else
    echo "❌ Unknown state, recreating container..."
    docker compose down
    docker compose up -d
fi

# 5. Verify recovery
sleep 5
if docker exec falkordb redis-cli ping > /dev/null 2>&1; then
    echo "✅ Recovery successful"
else
    echo "❌ Recovery failed, check logs: docker logs falkordb"
fi
```

---

## Diagnostic Scripts

### All-in-One Health Check

```bash
#!/bin/bash
# falkordb_health_check.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== FalkorDB Health Check ==="

# Function to check status
check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

ERRORS=0

# 1. Container status
docker inspect falkordb > /dev/null 2>&1
check_status $? "Container exists"

# 2. Connectivity
docker exec falkordb redis-cli ping > /dev/null 2>&1
check_status $? "Redis responding"

# 3. Memory usage
MEMORY_MB=$(docker exec falkordb redis-cli INFO memory | grep used_memory: | cut -d: -f2 | tr -d '\r' | awk '{print $1/1024/1024}')
if (( $(echo "$MEMORY_MB > 1000" | bc -l) )); then
    echo -e "${YELLOW}⚠️ High memory usage: ${MEMORY_MB}MB${NC}"
else
    echo -e "${GREEN}✅ Memory usage: ${MEMORY_MB}MB${NC}"
fi

# 4. Check for duplicates
DUPLICATES=$(docker exec falkordb redis-cli GRAPH.QUERY shared_knowledge_graph "
  MATCH (n) WHERE EXISTS(n.uuid)
  WITH n.uuid as uuid, COUNT(*) as cnt
  WHERE cnt > 1
  RETURN COUNT(*)" 2>/dev/null | grep -o '[0-9]*' | tail -1)

if [ -n "$DUPLICATES" ] && [ "$DUPLICATES" -gt 0 ]; then
    echo -e "${YELLOW}⚠️ Found $DUPLICATES duplicate UUID groups${NC}"
else
    echo -e "${GREEN}✅ No duplicate UUIDs${NC}"
fi

# 5. Configuration check
BUFFER=$(docker exec falkordb redis-cli GRAPH.CONFIG GET NODE_CREATION_BUFFER | tail -1 | tr -d '"')
if [ "$BUFFER" -gt 1024 ]; then
    echo -e "${RED}❌ NODE_CREATION_BUFFER too high: $BUFFER${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ NODE_CREATION_BUFFER: $BUFFER${NC}"
fi

# Summary
echo ""
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}=== All checks passed ===${NC}"
else
    echo -e "${RED}=== $ERRORS issues found ===${NC}"
fi
```

### Performance Profiler

```python
#!/usr/bin/env python3
# performance_profiler.py

import redis
import time
import statistics

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def profile_query(query, iterations=10):
    """Profile query performance"""
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        r.execute_command('GRAPH.QUERY', 'shared_knowledge_graph', query)
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # Convert to ms
    
    return {
        'min': min(times),
        'max': max(times),
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0
    }

# Test queries
queries = [
    ("Simple match", "MATCH (n:Entity) RETURN n LIMIT 1"),
    ("Property filter", "MATCH (n:Entity) WHERE n.confidence > 0.8 RETURN n LIMIT 10"),
    ("1-hop path", "MATCH (n:Entity)-[]-(m:Entity) RETURN n, m LIMIT 10"),
    ("2-hop path", "MATCH (n:Entity)-[*2]-(m:Entity) RETURN n, m LIMIT 10"),
    ("Aggregation", "MATCH (n:Entity) RETURN COUNT(n)"),
]

print("=== Query Performance Profile ===\n")
for name, query in queries:
    print(f"{name}:")
    stats = profile_query(query)
    print(f"  Mean: {stats['mean']:.2f}ms")
    print(f"  Median: {stats['median']:.2f}ms")
    print(f"  Min/Max: {stats['min']:.2f}ms / {stats['max']:.2f}ms")
    print(f"  StdDev: {stats['stdev']:.2f}ms\n")
    
    if stats['mean'] > 100:
        print(f"  ⚠️ WARNING: Query is slow (>100ms)")
    elif stats['mean'] > 50:
        print(f"  ⚠️ NOTICE: Query could be optimized (>50ms)")
```

---

## Summary

### Quick Reference

| Issue | Command | Expected Output |
|-------|---------|-----------------|
| Container status | `docker ps -a | grep falkordb` | Status: Up |
| Memory usage | `docker exec falkordb redis-cli INFO memory | grep used_memory_human` | < 2GB |
| Duplicate check | See duplicate detection script | 0 duplicates |
| Slow queries | `docker exec falkordb redis-cli SLOWLOG GET 5` | < 100ms |
| Connection count | `docker exec falkordb redis-cli CLIENT LIST | wc -l` | < 50 |

### Emergency Contacts

- **FalkorDB Issues**: [github.com/FalkorDB/FalkorDB/issues](https://github.com/FalkorDB/FalkorDB/issues)
- **Graphiti Support**: [github.com/getzep/graphiti/issues](https://github.com/getzep/graphiti/issues)
- **OrbStack Support**: [orbstack.dev/support](https://orbstack.dev/support)

### Prevention Checklist

✅ **Set NODE_CREATION_BUFFER ≤ 512**

✅ **Monitor memory weekly**

✅ **Check for duplicates before imports**

✅ **Backup before schema changes**

✅ **Test queries with EXPLAIN first**

✅ **Use connection pooling**

✅ **Set memory limits explicitly**

✅ **Enable query timeouts**

✅ **Log slow queries**

✅ **Automate health checks**

🚨 **Remember**: When in doubt, reduce NODE_CREATION_BUFFER first - it's the #1 cause of memory explosions with Graphiti workloads.