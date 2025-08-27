#!/bin/bash

# FalkorDB Backup Script
# Creates timestamped backups of FalkorDB data

set -e

# Load environment variables
if [ -f .env ]; then
    set -a
    source <(grep -v '^#' .env | grep -v '^$')
    set +a
fi

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="falkordb_backup_${DATE}.rdb"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}         FalkorDB Backup Utility               ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# Check if FalkorDB container is running
if ! docker ps | grep -q falkordb; then
    echo -e "${RED}Error: FalkorDB container is not running${NC}"
    echo "Run 'docker compose up -d' to start it"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Starting backup process...${NC}"
echo "Backup directory: $BACKUP_DIR"
echo "Backup filename: $BACKUP_FILE"
echo ""

# Function to get database size
get_db_size() {
    docker exec falkordb redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r '
}

# Show current database size
DB_SIZE=$(get_db_size)
echo "Current database size: $DB_SIZE"
echo ""

# Trigger background save
echo -e "${YELLOW}Initiating background save...${NC}"
docker exec falkordb redis-cli BGSAVE

# Wait for background save to complete
echo "Waiting for save to complete..."
while [ "$(docker exec falkordb redis-cli LASTSAVE)" = "$(docker exec falkordb redis-cli LASTSAVE)" ]; do
    sleep 1
    if docker exec falkordb redis-cli INFO persistence | grep -q "rdb_bgsave_in_progress:1"; then
        echo -n "."
    else
        break
    fi
done
echo ""

# Copy backup from Docker volume
echo -e "${YELLOW}Copying backup from Docker volume...${NC}"

# Try to copy from OrbStack volume location first
if [ -f ~/OrbStack/docker/volumes/falkordb_falkordb_data/_data/dump.rdb ]; then
    cp ~/OrbStack/docker/volumes/falkordb_falkordb_data/_data/dump.rdb "$BACKUP_DIR/$BACKUP_FILE"
    echo -e "${GREEN}✓ Backup copied from OrbStack volume${NC}"
else
    # Fallback: Copy from container
    docker exec falkordb cat /var/lib/falkordb/data/dump.rdb > "$BACKUP_DIR/$BACKUP_FILE"
    echo -e "${GREEN}✓ Backup copied from container${NC}"
fi

# Verify backup file
if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(ls -lh "$BACKUP_DIR/$BACKUP_FILE" | awk '{print $5}')
    echo -e "${GREEN}✓ Backup created successfully${NC}"
    echo "  File: $BACKUP_DIR/$BACKUP_FILE"
    echo "  Size: $BACKUP_SIZE"
else
    echo -e "${RED}✗ Backup failed - file not created${NC}"
    exit 1
fi

echo ""

# Clean up old backups
echo -e "${YELLOW}Cleaning up old backups...${NC}"
DELETED_COUNT=0
while IFS= read -r file; do
    echo "  Removing: $(basename "$file")"
    rm "$file"
    ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -name "falkordb_backup_*.rdb" -type f -mtime +$RETENTION_DAYS)

if [ $DELETED_COUNT -gt 0 ]; then
    echo -e "${GREEN}✓ Removed $DELETED_COUNT old backup(s)${NC}"
else
    echo "  No old backups to remove"
fi

echo ""

# List current backups
echo -e "${YELLOW}Current backups:${NC}"
ls -lht "$BACKUP_DIR"/falkordb_backup_*.rdb 2>/dev/null | head -10 | while read line; do
    echo "  $line"
done

echo ""
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}Backup completed at $(date)${NC}"
echo -e "${BLUE}===============================================${NC}"

# Optional: Test restore command (commented out for safety)
# echo ""
# echo "To restore from this backup, run:"
# echo "  docker exec -i falkordb redis-cli --rdb $BACKUP_DIR/$BACKUP_FILE"