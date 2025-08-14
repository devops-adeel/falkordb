#!/bin/bash

# Open FalkorDB Browser Interface

echo "Opening FalkorDB Browser Interface..."
echo "URL: http://localhost:3001"
echo ""
echo "Note: Make sure FalkorDB is running (docker compose up -d)"
echo ""

# Check if FalkorDB is running
if ! docker ps | grep -q falkordb; then
    echo "Error: FalkorDB container is not running"
    echo "Run 'docker compose up -d' to start it"
    exit 1
fi

# Open browser (macOS specific)
open http://localhost:3001