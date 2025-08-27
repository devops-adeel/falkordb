#!/bin/sh

# FalkorDB Pre-Backup Hook Script
# Executed by offen/docker-volume-backup before creating the backup archive
# This script triggers BGSAVE and waits for completion to ensure consistency
# Note: Uses sh instead of bash as the backup container is Alpine-based

set -e

# Colors for output (if terminal supports it)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m' # No Color
else
    GREEN=''
    YELLOW=''
    RED=''
    NC=''
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting FalkorDB pre-backup process..."

# Function to get current LASTSAVE timestamp
get_lastsave() {
    redis-cli LASTSAVE 2>/dev/null | tr -d '\r\n'
}

# Function to check if BGSAVE is in progress
is_bgsave_running() {
    redis-cli INFO persistence 2>/dev/null | grep -q "rdb_bgsave_in_progress:1"
}

# Get memory usage for logging
DB_SIZE=$(redis-cli INFO memory 2>/dev/null | grep used_memory_human | cut -d: -f2 | tr -d '\r ' || echo "unknown")
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Current database size: $DB_SIZE"

# Record the current LASTSAVE timestamp before triggering BGSAVE
LAST_SAVE=$(get_lastsave)
if [ -z "$LAST_SAVE" ]; then
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Could not connect to FalkorDB${NC}"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Last save timestamp: $LAST_SAVE"

# Trigger BGSAVE
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Triggering BGSAVE..."
if ! redis-cli BGSAVE 2>/dev/null | grep -q "Background saving started"; then
    # Check if a BGSAVE is already in progress
    if is_bgsave_running; then
        echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] BGSAVE already in progress, waiting...${NC}"
    else
        echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Failed to trigger BGSAVE${NC}"
        exit 1
    fi
fi

# Wait for BGSAVE to complete (max 120 seconds for large databases)
WAIT_COUNT=0
MAX_WAIT=120
PROGRESS_SHOWN=false

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for BGSAVE to complete..."

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    # Check if LASTSAVE timestamp has changed
    NEW_SAVE=$(get_lastsave)
    
    if [ "$NEW_SAVE" != "$LAST_SAVE" ] && [ -n "$NEW_SAVE" ]; then
        echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ BGSAVE completed successfully${NC}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] New save timestamp: $NEW_SAVE"
        
        # Get final RDB file info
        if [ -f /var/lib/falkordb/data/dump.rdb ]; then
            RDB_SIZE=$(ls -lh /var/lib/falkordb/data/dump.rdb 2>/dev/null | awk '{print $5}' || echo "unknown")
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] RDB file size: $RDB_SIZE"
        fi
        
        exit 0
    fi
    
    # Also check if BGSAVE is no longer in progress (alternative completion check)
    if [ $WAIT_COUNT -gt 2 ] && ! is_bgsave_running; then
        # Double-check with LASTSAVE
        NEW_SAVE=$(get_lastsave)
        if [ "$NEW_SAVE" != "$LAST_SAVE" ]; then
            echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ BGSAVE completed${NC}"
            exit 0
        fi
    fi
    
    # Show progress indicator every 10 seconds
    if [ $((WAIT_COUNT % 10)) -eq 0 ] && [ $WAIT_COUNT -gt 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Still waiting... (${WAIT_COUNT}s elapsed)"
        PROGRESS_SHOWN=true
    fi
    
    sleep 1
    ((WAIT_COUNT++))
done

# Timeout reached
echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: BGSAVE timeout after ${MAX_WAIT} seconds${NC}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Proceeding with backup anyway (data might be slightly outdated)"

# Exit with warning code but don't fail the backup
exit 0