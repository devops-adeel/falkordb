#!/bin/bash

# Test multiple Graphiti versions to find regression point
# Usage: ./test_version_bisect.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "GRAPHITI VERSION BISECTION TEST"
echo "============================================"

# Activate virtual environment
source ../venv/bin/activate

# Load environment variables
export $(grep -v '^#' ~/.env | xargs) 2>/dev/null || true

# Versions to test
versions=(
    "0.17.7"
    "0.17.8"
    "0.17.9"
    "0.17.10"
    "0.17.11"
    "0.18.0"
    "0.18.1"
)

# Test function
test_version() {
    local version=$1
    echo ""
    echo "--------------------------------------------"
    echo "Testing v$version"
    echo "--------------------------------------------"
    
    # Install version
    echo "Installing graphiti-core==$version..."
    pip install "graphiti-core[falkordb]==$version" --quiet 2>/dev/null
    
    # Create test script inline
    python3 - <<EOF 2>/dev/null
import asyncio
from datetime import datetime, timezone

async def test():
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.nodes import EpisodeType
        from graphiti_core.utils.maintenance.graph_data_operations import clear_data
        
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database="test_${version//./_}"
        )
        
        client = Graphiti(graph_driver=driver)
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
        
        await client.add_episode(
            name="Test $version",
            episode_body="Testing group_id issue",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc)
        )
        
        print("✅ v$version WORKS")
        return 0
        
    except Exception as e:
        if "group_id" in str(e):
            print("❌ v$version BROKEN (group_id error)")
            return 1
        else:
            print("⚠️  v$version ERROR:", str(e)[:50])
            return 2

exit(asyncio.run(test()))
EOF
    
    return $?
}

# Results tracking
results_file="/tmp/version_test_results.txt"
> "$results_file"

# Test each version
for version in "${versions[@]}"; do
    test_version "$version"
    echo "$version:$?" >> "$results_file"
done

# Print summary
echo ""
echo "============================================"
echo "SUMMARY"
echo "============================================"

last_working=""
first_broken=""

while IFS=':' read -r version status; do
    if [ "$status" -eq 0 ]; then
        echo -e "${GREEN}✅ v$version: WORKS${NC}"
        last_working=$version
    elif [ "$status" -eq 1 ]; then
        echo -e "${RED}❌ v$version: BROKEN (group_id)${NC}"
        if [ -z "$first_broken" ]; then
            first_broken=$version
        fi
    else
        echo -e "${YELLOW}⚠️  v$version: OTHER ERROR${NC}"
    fi
done < "$results_file"

if [ -n "$last_working" ] && [ -n "$first_broken" ]; then
    echo ""
    echo "============================================"
    echo -e "${YELLOW}REGRESSION FOUND:${NC}"
    echo -e "Last working: ${GREEN}v$last_working${NC}"
    echo -e "First broken: ${RED}v$first_broken${NC}"
    echo "============================================"
fi