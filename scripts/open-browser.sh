#!/bin/bash

# Open FalkorDB Browser Interface

echo "Opening FalkorDB Browser Interface..."
echo "URL: https://falkordb.local"
echo ""
echo "Note: Make sure FalkorDB is running (docker compose up -d)"
echo "Alternative URLs:"
echo "  - http://falkordb.local (HTTP)"
echo "  - https://falkordb.orb.local (auto-generated OrbStack domain)"
echo ""

# Check if FalkorDB is running
if ! docker ps | grep -q falkordb; then
    echo "Error: FalkorDB container is not running"
    echo "Run 'docker compose up -d' to start it"
    exit 1
fi

# Open browser (macOS specific) - using HTTPS by default
open https://falkordb.local