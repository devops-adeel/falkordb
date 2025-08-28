#!/bin/bash
#
# FalkorDB Maintenance Script
# Monitors memory usage and checks for duplicate nodes
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== FalkorDB Maintenance Check ===${NC}"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if FalkorDB container is running
if ! docker ps | grep -q falkordb; then
    echo -e "${RED}Error: FalkorDB container is not running${NC}"
    exit 1
fi

# Check memory usage
echo -e "${YELLOW}Memory Usage:${NC}"
docker exec falkordb redis-cli INFO memory | grep -E "(used_memory_human|used_memory_peak_human|used_memory_rss_human)"
echo ""

# Check graph memory if exists
echo -e "${YELLOW}Graph Memory Usage:${NC}"
if docker exec falkordb redis-cli GRAPH.LIST 2>/dev/null | grep -q "shared_gtd_knowledge"; then
    docker exec falkordb redis-cli GRAPH.MEMORY USAGE shared_gtd_knowledge 2>/dev/null || echo "Graph not found or empty"
else
    echo "No shared_gtd_knowledge graph found"
fi
echo ""

# Check for duplicate UUIDs
echo -e "${YELLOW}Checking for Duplicate UUIDs:${NC}"
DUPLICATE_CHECK=$(docker exec falkordb redis-cli GRAPH.QUERY shared_gtd_knowledge \
    "MATCH (n) WHERE EXISTS(n.uuid) RETURN n.uuid as uuid, COUNT(*) as cnt ORDER BY cnt DESC LIMIT 10" 2>/dev/null || echo "")

if [ -n "$DUPLICATE_CHECK" ]; then
    echo "$DUPLICATE_CHECK"
    
    # Check if any duplicates found
    if echo "$DUPLICATE_CHECK" | grep -q "cnt.*[2-9]"; then
        echo -e "${RED}WARNING: Duplicate UUIDs detected!${NC}"
    else
        echo -e "${GREEN}No duplicate UUIDs found${NC}"
    fi
else
    echo "Unable to check for duplicates (graph may be empty)"
fi
echo ""

# Check slow queries
echo -e "${YELLOW}Recent Slow Queries (last 5):${NC}"
docker exec falkordb redis-cli SLOWLOG GET 5 2>/dev/null || echo "No slow queries logged"
echo ""

# Check configuration
echo -e "${YELLOW}Current Configuration:${NC}"
docker exec falkordb redis-cli CONFIG GET maxmemory 2>/dev/null
docker exec falkordb redis-cli CONFIG GET maxmemory-policy 2>/dev/null
echo ""

# Memory warning thresholds
MEMORY_USAGE=$(docker exec falkordb redis-cli INFO memory | grep "used_memory:" | cut -d: -f2 | tr -d '\r')
MAX_MEMORY=$(docker exec falkordb redis-cli CONFIG GET maxmemory | tail -1 | tr -d '\r')

if [ "$MAX_MEMORY" != "0" ] && [ "$MEMORY_USAGE" -gt 0 ]; then
    USAGE_PERCENT=$((MEMORY_USAGE * 100 / MAX_MEMORY))
    
    if [ "$USAGE_PERCENT" -gt 90 ]; then
        echo -e "${RED}CRITICAL: Memory usage is at ${USAGE_PERCENT}%${NC}"
    elif [ "$USAGE_PERCENT" -gt 75 ]; then
        echo -e "${YELLOW}WARNING: Memory usage is at ${USAGE_PERCENT}%${NC}"
    else
        echo -e "${GREEN}Memory usage is at ${USAGE_PERCENT}%${NC}"
    fi
fi

echo ""
echo -e "${GREEN}=== Maintenance Check Complete ===${NC}"