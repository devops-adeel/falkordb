# FalkorDB-Graphiti Integration Tests

Comprehensive test suite for validating FalkorDB with multiple Graphiti instances.

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── test_concurrent_access_int.py  # Tests for 5 concurrent agents
├── test_complex_queries_int.py    # Semantic search and reranking tests
├── test_data_persistence_int.py   # Container restart and backup tests
└── fixtures/
    ├── langfuse_fetcher.py        # Fetches real conversation data
    └── test_scenarios.json        # Synthetic test scenarios
```

## Prerequisites

1. **FalkorDB running** on port 6380:
   ```bash
   docker compose up -d
   ```

2. **Python dependencies**:
   ```bash
   pip install pytest pytest-asyncio tenacity docker langfuse graphiti-core[falkordb]
   ```

3. **Environment variables** (optional for Langfuse data):
   ```bash
   export LANGFUSE_PUBLIC_KEY="your_key"
   export LANGFUSE_SECRET_KEY="your_secret"
   export LANGFUSE_HOST="http://langfuse-prod-langfuse-web-1.orb.local"
   export OPENAI_API_KEY="your_openai_key"
   ```

## Running Tests

### Run all integration tests
```bash
pytest tests/ -v --asyncio-mode=auto -k "_int"
```

### Run specific test categories
```bash
# Concurrent access tests (5 agents)
pytest tests/test_concurrent_access_int.py -v

# Complex query tests (semantic search, reranking)
pytest tests/test_complex_queries_int.py -v

# Data persistence tests (restart, backup)
pytest tests/test_data_persistence_int.py -v
```

### Run with performance metrics
```bash
pytest tests/ -v --durations=10 -k "_int"
```

### Run with retry on failures
```bash
pytest tests/ -v --maxfail=3 -x -k "_int"
```

## Test Categories

### Concurrent Access (`test_concurrent_access_int.py`)
- ✅ 5 agents writing simultaneously
- ✅ Read-write consistency
- ✅ Connection pool saturation (16 connections)
- ✅ Agent isolation patterns
- ✅ Concurrent complex queries

### Complex Queries (`test_complex_queries_int.py`)
- ✅ Semantic search with center node reranking
- ✅ Multi-hop fact extraction
- ✅ Cross-agent knowledge discovery
- ✅ Query performance stability as graph grows
- ✅ Edge case handling (empty, special chars, long queries)

### Data Persistence (`test_data_persistence_int.py`)
- ✅ Container restart survival
- ✅ Backup creation and verification
- ✅ Graph consistency after failures
- ✅ Concurrent write persistence
- ✅ Long-term data retention

## Key Features

### 1. **Real LLM Calls**
Tests use actual OpenAI API calls with intelligent retry logic (exponential backoff for rate limits).

### 2. **Langfuse Integration**
Automatically fetches real conversation data from your Langfuse server when available, falls back to synthetic data.

### 3. **Performance Assertions**
Each test measures and asserts operation times:
- Single queries: < 2 seconds
- Concurrent operations: < 5 seconds
- Complex queries: < 3 seconds

### 4. **Async-First Design**
All tests use `pytest-asyncio` for true concurrent testing with `asyncio.gather()`.

### 5. **Docker Container Testing**
Tests actual container restarts and health checks using the Docker API.

## Success Metrics

| Metric | Target | Measured By |
|--------|--------|-------------|
| Concurrent agents | 5 agents no conflicts | `test_five_agents_concurrent_write` |
| Query latency | < 2 seconds | `measure_time` decorator |
| Data persistence | 100% recovery | `test_container_restart_persistence` |
| Connection pool | 95% success rate | `test_connection_pool_saturation` |
| Knowledge sharing | Cross-agent discovery | `test_cross_agent_knowledge_sharing` |

## Troubleshooting

### Tests skip with "Could not connect to FalkorDB"
- Ensure FalkorDB is running: `docker compose ps`
- Check port 6380 is available: `lsof -i :6380`
- Verify container health: `docker exec falkordb redis-cli ping`

### Langfuse data not fetching
- Check environment variables are set
- Verify Langfuse server is accessible
- Tests will use synthetic fallback data automatically

### Slow test execution
- Reduce retry attempts in `conftest.py`
- Run specific test files instead of full suite
- Check FalkorDB performance with `./scripts/monitor.sh`

### Container restart test fails
- Ensure Docker daemon is running
- Check container name is "falkordb"
- Verify sufficient permissions for Docker API

## CI/CD Integration

Add to your CI pipeline:
```yaml
test:
  script:
    - docker compose up -d
    - sleep 5  # Wait for FalkorDB
    - pytest tests/ -v --asyncio-mode=auto -k "_int" --maxfail=3
  timeout: 10 minutes
```

## Coverage Report

Generate HTML coverage report:
```bash
pytest tests/ --cov=. --cov-report=html -k "_int"
open htmlcov/index.html
```

## Notes

- Tests are marked with `@pytest.mark.integration` for easy filtering
- Each test module can run independently
- Clean graph state is maintained between test classes
- Performance metrics are collected and reported
- All tests respect the 5-10 minute total runtime target