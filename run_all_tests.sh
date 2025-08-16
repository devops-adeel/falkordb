#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Export environment variables from ~/.env
export $(grep -v '^#' ~/.env | xargs)

echo "=================================="
echo "FalkorDB-Graphiti Integration Tests"
echo "=================================="
echo ""

# Check FalkorDB status
echo "🔍 Checking FalkorDB status..."
if docker exec falkordb redis-cli -p 6379 ping > /dev/null 2>&1; then
    echo "✅ FalkorDB is running"
else
    echo "❌ FalkorDB is not running. Please start it with: docker compose up -d"
    exit 1
fi

echo ""
echo "📊 Running full test suite..."
echo "=================================="

# Run all integration tests with verbose output
pytest tests/ -v --asyncio-mode=auto -k "_int" --tb=short --durations=10

# Capture exit code
TEST_EXIT_CODE=$?

echo ""
echo "=================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed successfully!"
else
    echo "❌ Some tests failed. Review the output above."
fi

echo ""
echo "📈 Test Summary:"
echo "- Concurrent Access: Tests 5 agents writing/reading simultaneously"
echo "- Complex Queries: Tests semantic search and reranking"
echo "- Data Persistence: Tests container restart and backup"

exit $TEST_EXIT_CODE