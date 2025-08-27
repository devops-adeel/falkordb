#!/bin/bash

# FalkorDB Restore Script
# Restores FalkorDB data from a backup file

set -e

# Load environment variables
if [ -f .env ]; then
    set -a
    source <(grep -v '^#' .env | grep -v '^$')
    set +a
fi

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATA_DIR="${DATA_DIR:-~/OrbStack/docker/volumes/falkordb_falkordb_data/_data}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}         FalkorDB Restore Utility              ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# Function to list available backups
list_backups() {
    echo -e "${YELLOW}Available backups:${NC}"
    if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.rdb 2>/dev/null | wc -l)" -gt 0 ]; then
        ls -lht "$BACKUP_DIR"/*.rdb 2>/dev/null | head -10 | while IFS= read -r line; do
            echo "  $line"
        done
    else
        echo "  No backups found in $BACKUP_DIR"
        exit 1
    fi
    echo ""
}

# Function to validate backup file
validate_backup() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        echo -e "${RED}Error: Backup file not found: $backup_file${NC}"
        exit 1
    fi
    
    # Check if it's a valid RDB file (starts with REDIS)
    if ! head -c 5 "$backup_file" | grep -q "REDIS"; then
        echo -e "${RED}Error: Invalid RDB file format${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Backup file validated${NC}"
}

# Parse command line arguments
BACKUP_FILE=""
FORCE_RESTORE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--file)
            BACKUP_FILE="$2"
            shift 2
            ;;
        --force)
            FORCE_RESTORE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -f, --file FILE    Specify backup file to restore"
            echo "  --force           Skip confirmation prompt"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                 # Interactive mode - choose from list"
            echo "  $0 -f backup.rdb   # Restore specific backup"
            echo "  $0 --force -f backup.rdb  # Restore without confirmation"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# If no backup file specified, show list and prompt for selection
if [ -z "$BACKUP_FILE" ]; then
    list_backups
    
    echo -e "${YELLOW}Enter the backup filename to restore (or full path):${NC}"
    read -r BACKUP_INPUT
    
    # Check if it's a filename or full path
    if [[ "$BACKUP_INPUT" = /* ]]; then
        BACKUP_FILE="$BACKUP_INPUT"
    else
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_INPUT"
    fi
fi

# Validate the backup file
echo -e "${YELLOW}Validating backup file...${NC}"
validate_backup "$BACKUP_FILE"

# Show backup details
BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
BACKUP_DATE=$(ls -l "$BACKUP_FILE" | awk '{print $6, $7, $8}')
echo ""
echo -e "${YELLOW}Backup Details:${NC}"
echo "  File: $BACKUP_FILE"
echo "  Size: $BACKUP_SIZE"
echo "  Date: $BACKUP_DATE"
echo ""

# Warning and confirmation
if [ "$FORCE_RESTORE" = false ]; then
    echo -e "${RED}WARNING: This will replace all current FalkorDB data!${NC}"
    echo -e "${YELLOW}Are you sure you want to restore from this backup? (yes/no)${NC}"
    read -r CONFIRMATION
    
    if [ "$CONFIRMATION" != "yes" ]; then
        echo -e "${YELLOW}Restore cancelled${NC}"
        exit 0
    fi
fi

echo ""
echo -e "${YELLOW}Starting restore process...${NC}"

# Check if FalkorDB is running
if docker ps | grep -q falkordb; then
    echo "Stopping FalkorDB container..."
    docker compose down
    
    # Wait for container to fully stop
    sleep 3
else
    echo "FalkorDB container is not running"
fi

# Backup current data (just in case)
if [ -f "$DATA_DIR/dump.rdb" ]; then
    SAFETY_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).rdb"
    echo "Creating safety backup of current data..."
    cp "$DATA_DIR/dump.rdb" "$SAFETY_BACKUP"
    echo -e "${GREEN}✓ Safety backup created: $SAFETY_BACKUP${NC}"
fi

# Restore the backup
echo "Restoring backup..."

# Method 1: Try OrbStack volume location first
if [ -d "$DATA_DIR" ]; then
    cp "$BACKUP_FILE" "$DATA_DIR/dump.rdb"
    echo -e "${GREEN}✓ Backup restored to OrbStack volume${NC}"
else
    # Method 2: Copy to container after starting
    echo "OrbStack volume not found, will restore after container starts..."
    RESTORE_AFTER_START=true
fi

# Start FalkorDB
echo ""
echo "Starting FalkorDB with restored data..."
docker compose up -d

# Wait for container to be ready
echo "Waiting for FalkorDB to initialize..."
RETRY_COUNT=0
MAX_RETRIES=30

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec falkordb redis-cli ping 2>/dev/null | grep -q PONG; then
        echo -e "${GREEN}✓ FalkorDB is ready${NC}"
        break
    fi
    
    echo -n "."
    sleep 2
    ((RETRY_COUNT++))
done

echo ""

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}Error: FalkorDB failed to start properly${NC}"
    exit 1
fi

# If we couldn't restore to volume directly, do it now
if [ "$RESTORE_AFTER_START" = true ]; then
    echo "Copying backup to container..."
    docker cp "$BACKUP_FILE" falkordb:/var/lib/falkordb/data/dump.rdb
    
    echo "Restarting FalkorDB to load restored data..."
    docker compose restart
    
    # Wait again for startup
    sleep 5
    
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if docker exec falkordb redis-cli ping 2>/dev/null | grep -q PONG; then
            echo -e "${GREEN}✓ FalkorDB restarted successfully${NC}"
            break
        fi
        echo -n "."
        sleep 2
        ((RETRY_COUNT++))
    done
fi

# Verify restoration
echo ""
echo -e "${YELLOW}Verifying restoration...${NC}"

# Check if graphs exist
GRAPHS=$(docker exec falkordb redis-cli GRAPH.LIST 2>/dev/null || echo "")
if [ -n "$GRAPHS" ] && [ "$GRAPHS" != "" ]; then
    echo -e "${GREEN}✓ Graphs restored successfully:${NC}"
    echo "$GRAPHS" | while read graph; do
        if [ -n "$graph" ]; then
            echo "  - $graph"
            
            # Try to get node count for each graph
            NODE_COUNT=$(docker exec falkordb redis-cli GRAPH.QUERY "$graph" "MATCH (n) RETURN count(n)" 2>/dev/null | grep -o '[0-9]*' | head -1 || echo "0")
            if [ -n "$NODE_COUNT" ] && [ "$NODE_COUNT" != "0" ]; then
                echo "    Nodes: $NODE_COUNT"
            fi
        fi
    done
else
    echo -e "${YELLOW}No graphs found (database may have been empty)${NC}"
fi

# Show memory usage
echo ""
echo -e "${YELLOW}Current Memory Usage:${NC}"
docker exec falkordb redis-cli INFO memory | grep used_memory_human | cut -d: -f2

echo ""
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}Restore completed successfully at $(date)${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""
echo "You can verify the restoration by:"
echo "  1. Running: docker exec falkordb redis-cli GRAPH.LIST"
echo "  2. Opening the browser UI: https://falkordb-browser.local/"
echo "  3. Running the monitoring script: ./scripts/monitor.sh"