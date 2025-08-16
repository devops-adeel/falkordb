#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Export environment variables from ~/.env
export $(grep -v '^#' ~/.env | xargs)

# Run tests with proper configuration
echo "Running FalkorDB-Graphiti Integration Tests..."
echo "=================================="

# Run a simple connectivity test first
pytest tests/test_concurrent_access_int.py::test_five_agents_concurrent_write -v --asyncio-mode=auto -s

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Initial test passed!"
else
    echo "❌ Initial test failed. Check the output above."
fi