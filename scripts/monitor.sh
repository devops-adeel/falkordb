#!/bin/bash

# FalkorDB Monitoring Script
# Provides insights into memory usage, connections, and performance

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}       FalkorDB Monitoring Dashboard           ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# Check if FalkorDB container is running
if ! docker ps | grep -q falkordb; then
    echo -e "${RED}Error: FalkorDB container is not running${NC}"
    echo "Run 'docker compose up -d' to start it"
    exit 1
fi

# Function to check FalkorDB health
check_health() {
    echo -e "${YELLOW}Health Status:${NC}"
    if docker exec falkordb redis-cli ping > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ FalkorDB is responding${NC}"
    else
        echo -e "  ${RED}✗ FalkorDB is not responding${NC}"
    fi
    echo ""
}

# Function to show memory usage
show_memory() {
    echo -e "${YELLOW}Memory Usage:${NC}"
    
    # Redis memory info
    docker exec falkordb redis-cli INFO memory | grep -E "used_memory_human|used_memory_peak_human|maxmemory_human" | while IFS=: read -r key value; do
        printf "  %-25s: %s\n" "$key" "$value"
    done
    
    # Graph-specific memory if database exists
    if docker exec falkordb redis-cli GRAPH.LIST 2>/dev/null | grep -q "shared_knowledge_graph"; then
        echo ""
        echo -e "${YELLOW}Graph Memory Usage (shared_knowledge_graph):${NC}"
        docker exec falkordb redis-cli GRAPH.MEMORY USAGE shared_knowledge_graph 2>/dev/null || echo "  No detailed memory stats available yet"
    fi
    echo ""
}

# Function to show connected clients
show_clients() {
    echo -e "${YELLOW}Connected Clients:${NC}"
    CLIENT_COUNT=$(docker exec falkordb redis-cli CLIENT LIST | wc -l)
    echo "  Total connected clients: $CLIENT_COUNT"
    
    if [ "$CLIENT_COUNT" -gt 0 ]; then
        echo "  Client details:"
        docker exec falkordb redis-cli CLIENT LIST | head -5 | while read line; do
            echo "    $line" | cut -d' ' -f1-3
        done
        if [ "$CLIENT_COUNT" -gt 5 ]; then
            echo "    ... and $((CLIENT_COUNT - 5)) more"
        fi
    fi
    echo ""
}

# Function to show database statistics
show_stats() {
    echo -e "${YELLOW}Database Statistics:${NC}"
    
    # General Redis stats
    docker exec falkordb redis-cli INFO stats | grep -E "total_commands_processed|instantaneous_ops_per_sec|total_connections_received" | while IFS=: read -r key value; do
        printf "  %-30s: %s\n" "$key" "$value"
    done
    
    # List all graphs
    echo ""
    echo -e "${YELLOW}Available Graphs:${NC}"
    GRAPHS=$(docker exec falkordb redis-cli GRAPH.LIST 2>/dev/null || echo "")
    if [ -z "$GRAPHS" ]; then
        echo "  No graphs created yet"
    else
        echo "$GRAPHS" | while read graph; do
            echo "  - $graph"
        done
    fi
    echo ""
}

# Function to show slow queries
show_slow_queries() {
    echo -e "${YELLOW}Recent Slow Queries:${NC}"
    SLOW_COUNT=$(docker exec falkordb redis-cli SLOWLOG LEN | tr -d '\r')
    
    if [ "$SLOW_COUNT" -eq 0 ]; then
        echo "  No slow queries logged"
    else
        echo "  Last 5 slow queries:"
        docker exec falkordb redis-cli SLOWLOG GET 5 | head -20
    fi
    echo ""
}

# Function to show performance metrics
show_performance() {
    echo -e "${YELLOW}Performance Metrics:${NC}"
    
    # Get instantaneous metrics
    OPS=$(docker exec falkordb redis-cli INFO stats | grep instantaneous_ops_per_sec | cut -d: -f2 | tr -d '\r ')
    INPUT=$(docker exec falkordb redis-cli INFO stats | grep instantaneous_input_kbps | cut -d: -f2 | tr -d '\r ')
    OUTPUT=$(docker exec falkordb redis-cli INFO stats | grep instantaneous_output_kbps | cut -d: -f2 | tr -d '\r ')
    
    echo "  Operations per second: $OPS"
    echo "  Input bandwidth: ${INPUT} KB/s"
    echo "  Output bandwidth: ${OUTPUT} KB/s"
    echo ""
}

# Main monitoring flow
check_health
show_memory
show_clients
show_stats
show_performance
show_slow_queries

echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}Monitoring complete at $(date)${NC}"
echo -e "${BLUE}===============================================${NC}"