#!/bin/bash

# FalkorDB Post-Backup Hook Script
# Executed by offen/docker-volume-backup after creating the backup archive
# This script extracts the RDB file for quick restore and validates the backup

set -e

# Configuration from environment or defaults
BACKUP_DIR="${BACKUP_DIR:-${HOME}/FalkorDBBackups}"
RDB_DIR="${BACKUP_DIR}/rdb"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

# Colors for output (if terminal supports it)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    GREEN=''
    YELLOW=''
    RED=''
    BLUE=''
    NC=''
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting FalkorDB post-backup processing..."

# Create RDB directory structure if it doesn't exist
mkdir -p "$RDB_DIR"

# Function to validate RDB file
validate_rdb() {
    local rdb_file=$1
    
    # Check if file exists and has size > 0
    if [ ! -f "$rdb_file" ] || [ ! -s "$rdb_file" ]; then
        return 1
    fi
    
    # Check RDB file magic string (should start with REDIS)
    if command -v xxd >/dev/null 2>&1; then
        local magic=$(xxd -l 5 -p "$rdb_file" 2>/dev/null | tr -d '\n')
        if [[ "$magic" == "5245444953"* ]]; then
            return 0  # Valid RDB file
        fi
    elif command -v hexdump >/dev/null 2>&1; then
        local magic=$(hexdump -n 5 -e '5/1 "%02x"' "$rdb_file" 2>/dev/null)
        if [[ "$magic" == "5245444953"* ]]; then
            return 0  # Valid RDB file
        fi
    else
        # Fallback: just check if file has reasonable size
        local size=$(stat -f%z "$rdb_file" 2>/dev/null || stat -c%s "$rdb_file" 2>/dev/null || echo 0)
        if [ "$size" -gt 100 ]; then
            return 0  # Probably valid
        fi
    fi
    
    return 1
}

# Copy the current dump.rdb directly from the backup volume
RDB_SOURCE="/backup/falkordb/dump.rdb"
RDB_DEST="$RDB_DIR/falkordb_${DATE}.rdb"

if [ -f "$RDB_SOURCE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Copying RDB file for quick restore..."
    
    # Copy the RDB file
    cp "$RDB_SOURCE" "$RDB_DEST"
    
    # Get file size for logging
    RDB_SIZE=$(ls -lh "$RDB_DEST" 2>/dev/null | awk '{print $5}' || echo "unknown")
    
    # Validate the copied RDB file
    if validate_rdb "$RDB_DEST"; then
        echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ RDB file saved: falkordb_${DATE}.rdb (Size: $RDB_SIZE)${NC}"
        
        # Create/update symlink to latest RDB
        ln -sf "$(basename "$RDB_DEST")" "$RDB_DIR/falkordb_latest.rdb"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Updated latest symlink: falkordb_latest.rdb"
        
        # Additional validation using redis-check-rdb if available
        if command -v redis-check-rdb >/dev/null 2>&1; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running redis-check-rdb validation..."
            if redis-check-rdb "$RDB_DEST" >/dev/null 2>&1; then
                echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ RDB validation: PASSED${NC}"
            else
                echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠ RDB validation: WARNINGS (backup is usable but check logs)${NC}"
            fi
        fi
    else
        echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗ ERROR: RDB file validation failed${NC}"
        rm -f "$RDB_DEST"  # Remove invalid file
        exit 1
    fi
else
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠ WARNING: RDB source file not found at $RDB_SOURCE${NC}"
fi

# Clean up old RDB files (keep based on retention policy)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning up old RDB files (keeping ${RETENTION_DAYS} days)..."
DELETED_COUNT=0

while IFS= read -r old_file; do
    if [ -f "$old_file" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')]   Removing: $(basename "$old_file")"
        rm -f "$old_file"
        ((DELETED_COUNT++))
    fi
done < <(find "$RDB_DIR" -name "falkordb_*.rdb" -type f -mtime +${RETENTION_DAYS} 2>/dev/null)

if [ $DELETED_COUNT -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Removed $DELETED_COUNT old RDB file(s)"
fi

# Generate backup summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}            FalkorDB Backup Summary                    ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup completed successfully"
echo ""

# List recent backups
echo "Recent tar.gz archives:"
ls -lht "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -3 | while read line; do
    echo "  $line"
done

echo ""
echo "Recent RDB files:"
ls -lht "$RDB_DIR"/falkordb_*.rdb 2>/dev/null | head -3 | while read line; do
    echo "  $line"
done

# Check external drive sync status
echo ""
if [ -d /external ]; then
    EXTERNAL_COUNT=$(ls -1 /external/*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}✓ External drive synced ($EXTERNAL_COUNT archives)${NC}"
else
    echo "✓ External drive not mounted (will sync when available)"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Quick restore instructions
echo "Quick Restore Commands:"
echo "  Latest RDB:  docker exec -i falkordb redis-cli --rdb $RDB_DIR/falkordb_latest.rdb"
echo "  From archive: docker run --rm -v falkordb_data:/data -v $BACKUP_DIR:/backup alpine tar -xzf /backup/falkordb-latest.tar.gz -C /data"

exit 0