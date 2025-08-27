#!/bin/bash

# FalkorDB Restore Script for OrbStack on macOS
# This script restores FalkorDB data from backups with production-grade features:
# - Backup validation before restore
# - Metadata verification
# - Structured logging
# - Post-restore validation

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../configs/backup.conf"

# Default configuration
BACKUP_BASE_DIR="${HOME}/FalkorDBBackups"
CONTAINER_NAME="falkordb"
DATA_DIR="${HOME}/OrbStack/docker/volumes/falkordb_falkordb_data/_data"
LOG_FILE="${SCRIPT_DIR}/../logs/restore-$(date +%Y%m%d-%H%M%S).log"

# Source config file if exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Source environment variables
if [ -f "$HOME/.env" ]; then
    set -a
    source "$HOME/.env"
    set +a
elif [ -f "$(dirname "$SCRIPT_DIR")/../.env" ]; then
    set -a
    source "$(dirname "$SCRIPT_DIR")/../.env"
    set +a
fi

# Create log directory if doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    echo -e "${RED}ERROR: $1${NC}"
    exit 1
}

# List available backups
list_backups() {
    echo -e "${YELLOW}Available backups in $BACKUP_BASE_DIR:${NC}"
    
    if [ ! -d "$BACKUP_BASE_DIR" ]; then
        error_exit "Backup directory does not exist: $BACKUP_BASE_DIR"
    fi
    
    local backup_found=false
    
    # List backups with metadata
    for backup_dir in "$BACKUP_BASE_DIR"/backup-*/; do
        if [ -d "$backup_dir" ]; then
            backup_found=true
            local backup_name=$(basename "$backup_dir")
            local metadata_file="$backup_dir/backup-metadata.json"
            
            if [ -f "$metadata_file" ]; then
                # Parse metadata using basic tools (no jq dependency)
                local timestamp=$(grep -o '"timestamp"[[:space:]]*:[[:space:]]*"[^"]*"' "$metadata_file" | cut -d'"' -f4)
                local graph_count=$(grep -o '"graph_count"[[:space:]]*:[[:space:]]*[0-9]*' "$metadata_file" | grep -o '[0-9]*$')
                local total_size=$(grep -o '"total_size"[[:space:]]*:[[:space:]]*"[^"]*"' "$metadata_file" | cut -d'"' -f4)
                
                echo -e "  ${GREEN}$backup_name${NC}"
                echo "    Timestamp: $timestamp"
                echo "    Graphs: $graph_count"
                echo "    Size: $total_size"
            else
                # No metadata, show basic info
                local backup_date=$(echo "$backup_name" | cut -d'-' -f2-3)
                local backup_size=$(du -sh "$backup_dir" 2>/dev/null | cut -f1)
                echo -e "  ${GREEN}$backup_name${NC} (Size: $backup_size, No metadata)"
            fi
        fi
    done
    
    # Check for latest symlink
    if [ -L "$BACKUP_BASE_DIR/latest" ]; then
        local latest_target=$(readlink "$BACKUP_BASE_DIR/latest")
        echo ""
        echo -e "${BLUE}Latest backup:${NC} $(basename "$latest_target")"
    fi
    
    if [ "$backup_found" = false ]; then
        error_exit "No backups found in $BACKUP_BASE_DIR"
    fi
    
    echo ""
}

# Validate backup before restore
validate_backup() {
    local backup_path="$1"
    
    log "Validating backup: $backup_path"
    
    # Check if backup directory exists
    if [ ! -d "$backup_path" ]; then
        error_exit "Backup directory not found: $backup_path"
    fi
    
    # Check for RDB file
    local rdb_file="$backup_path/rdb/dump.rdb.gz"
    if [ ! -f "$rdb_file" ]; then
        error_exit "RDB backup file not found: $rdb_file"
    fi
    
    # Validate gzip integrity
    log "Checking RDB file integrity..."
    if ! gzip -t "$rdb_file" 2>/dev/null; then
        error_exit "RDB backup file is corrupted (gzip check failed)"
    fi
    
    # If checksums exist, verify them
    if [ -f "$backup_path/checksums/SHA256SUMS" ]; then
        log "Verifying checksums..."
        cd "$backup_path"
        if shasum -a 256 -c checksums/SHA256SUMS > /dev/null 2>&1; then
            log "Checksum verification passed"
        else
            error_exit "Checksum verification failed"
        fi
        cd - > /dev/null
    else
        log "WARNING: No checksums found for verification"
    fi
    
    # If redis-check-rdb is available, use it
    if command -v redis-check-rdb &> /dev/null; then
        log "Running redis-check-rdb validation..."
        local temp_rdb="/tmp/falkordb_restore_validate_$$.rdb"
        gunzip -c "$rdb_file" > "$temp_rdb"
        
        if redis-check-rdb "$temp_rdb" > /dev/null 2>&1; then
            log "RDB validation passed (redis-check-rdb)"
            rm -f "$temp_rdb"
        else
            rm -f "$temp_rdb"
            error_exit "RDB validation failed (redis-check-rdb)"
        fi
    fi
    
    # Read metadata if available
    if [ -f "$backup_path/backup-metadata.json" ]; then
        log "Reading backup metadata..."
        cat "$backup_path/backup-metadata.json" >> "$LOG_FILE"
    fi
    
    echo -e "${GREEN}✓ Backup validation completed successfully${NC}"
}

# Create safety backup
create_safety_backup() {
    local safety_dir="${BACKUP_BASE_DIR}/safety-backups"
    mkdir -p "$safety_dir"
    
    local safety_backup="$safety_dir/pre_restore_$(date +%Y%m%d_%H%M%S).rdb"
    
    log "Creating safety backup before restore..."
    
    # Check if current data exists
    if [ -f "$DATA_DIR/dump.rdb" ]; then
        cp "$DATA_DIR/dump.rdb" "$safety_backup"
        gzip -6 "$safety_backup"
        log "Safety backup created: ${safety_backup}.gz"
        echo -e "${GREEN}✓ Safety backup created${NC}"
    else
        log "No existing data to backup"
    fi
}

# Restore from backup
perform_restore() {
    local backup_path="$1"
    local rdb_file="$backup_path/rdb/dump.rdb.gz"
    
    log "Starting restore from: $backup_path"
    
    # Stop FalkorDB if running
    if docker ps | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${YELLOW}Stopping FalkorDB container...${NC}"
        docker compose down || docker stop "$CONTAINER_NAME"
        sleep 3
    fi
    
    # Decompress and restore RDB file
    log "Restoring RDB file..."
    
    # Check if we can write to OrbStack volume
    if [ -d "$DATA_DIR" ]; then
        gunzip -c "$rdb_file" > "$DATA_DIR/dump.rdb"
        log "RDB file restored to OrbStack volume"
        RESTORE_METHOD="volume"
    else
        # Will need to restore after container starts
        log "OrbStack volume not accessible, will restore after container starts"
        RESTORE_METHOD="container"
    fi
    
    # Start FalkorDB
    echo -e "${YELLOW}Starting FalkorDB with restored data...${NC}"
    docker compose up -d || docker run -d --name "$CONTAINER_NAME" \
        -v falkordb_data:/var/lib/falkordb/data \
        -p ${REDIS_PORT:-6379}:6379 \
        falkordb/falkordb:edge
    
    # Wait for container to be ready
    log "Waiting for FalkorDB to initialize..."
    local retry_count=0
    local max_retries=30
    
    while [ $retry_count -lt $max_retries ]; do
        if docker exec "$CONTAINER_NAME" redis-cli ping 2>/dev/null | grep -q PONG; then
            echo -e "${GREEN}✓ FalkorDB is ready${NC}"
            break
        fi
        echo -n "."
        sleep 2
        ((retry_count++))
    done
    
    echo ""
    
    if [ $retry_count -eq $max_retries ]; then
        error_exit "FalkorDB failed to start properly after ${max_retries} attempts"
    fi
    
    # If we couldn't restore to volume directly, do it now
    if [ "$RESTORE_METHOD" = "container" ]; then
        log "Copying backup to container..."
        
        # Create temporary decompressed file
        local temp_rdb="/tmp/falkordb_restore_$$.rdb"
        gunzip -c "$rdb_file" > "$temp_rdb"
        
        # Copy to container
        docker cp "$temp_rdb" "${CONTAINER_NAME}:/var/lib/falkordb/data/dump.rdb"
        rm -f "$temp_rdb"
        
        log "Restarting FalkorDB to load restored data..."
        docker compose restart || docker restart "$CONTAINER_NAME"
        
        # Wait again for startup
        sleep 5
        retry_count=0
        while [ $retry_count -lt $max_retries ]; do
            if docker exec "$CONTAINER_NAME" redis-cli ping 2>/dev/null | grep -q PONG; then
                echo -e "${GREEN}✓ FalkorDB restarted successfully${NC}"
                break
            fi
            echo -n "."
            sleep 2
            ((retry_count++))
        done
        echo ""
    fi
    
    log "Restore process completed"
}

# Verify restoration
verify_restoration() {
    local backup_path="$1"
    
    echo ""
    echo -e "${YELLOW}Verifying restoration...${NC}"
    log "Starting post-restore verification..."
    
    # Check if graphs exist
    local current_graphs=$(docker exec "$CONTAINER_NAME" redis-cli GRAPH.LIST 2>/dev/null || echo "")
    
    if [ -n "$current_graphs" ]; then
        echo -e "${GREEN}✓ Graphs restored successfully:${NC}"
        echo "$current_graphs" | while read graph; do
            if [ -n "$graph" ]; then
                echo "  - $graph"
                
                # Get node count for verification
                local node_count=$(docker exec "$CONTAINER_NAME" redis-cli GRAPH.QUERY "$graph" "MATCH (n) RETURN count(n)" 2>/dev/null | grep -o '[0-9]*' | head -1 || echo "0")
                if [ -n "$node_count" ] && [ "$node_count" != "0" ]; then
                    echo "    Nodes: $node_count"
                fi
            fi
        done
        
        local current_graph_count=$(echo "$current_graphs" | wc -l | tr -d ' ')
        log "Restored $current_graph_count graphs"
    else
        echo -e "${YELLOW}No graphs found (database may have been empty)${NC}"
        log "No graphs found after restore"
    fi
    
    # Compare with backup metadata if available
    if [ -f "$backup_path/backup-metadata.json" ]; then
        local expected_graphs=$(grep -o '"graph_count"[[:space:]]*:[[:space:]]*[0-9]*' "$backup_path/backup-metadata.json" | grep -o '[0-9]*$')
        if [ -n "$expected_graphs" ] && [ -n "$current_graph_count" ]; then
            if [ "$expected_graphs" = "$current_graph_count" ]; then
                echo -e "${GREEN}✓ Graph count matches backup metadata ($expected_graphs graphs)${NC}"
                log "Graph count verification passed"
            else
                echo -e "${YELLOW}⚠ Graph count mismatch: expected $expected_graphs, found $current_graph_count${NC}"
                log "WARNING: Graph count mismatch"
            fi
        fi
    fi
    
    # Show memory usage
    echo ""
    echo -e "${YELLOW}Current Memory Usage:${NC}"
    local memory_usage=$(docker exec "$CONTAINER_NAME" redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r ')
    echo "  $memory_usage"
    log "Current memory usage: $memory_usage"
    
    echo ""
    echo -e "${GREEN}✓ Restoration verification completed${NC}"
}

# Parse command line arguments
BACKUP_PATH=""
FORCE_RESTORE=false
SKIP_SAFETY=false
TEST_RESTORE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--backup)
            BACKUP_PATH="$2"
            shift 2
            ;;
        --latest)
            BACKUP_PATH="$BACKUP_BASE_DIR/latest"
            shift
            ;;
        --force)
            FORCE_RESTORE=true
            shift
            ;;
        --skip-safety)
            SKIP_SAFETY=true
            shift
            ;;
        --test)
            TEST_RESTORE=true
            shift
            ;;
        -h|--help)
            cat << EOF
FalkorDB Restore Script

Usage: $0 [OPTIONS]

Options:
  -b, --backup PATH   Specify backup directory to restore
  --latest           Restore from the latest backup
  --force            Skip confirmation prompt
  --skip-safety      Skip creating safety backup
  --test             Test restore to temporary container
  -h, --help         Show this help message

Examples:
  $0                                    # Interactive mode - choose from list
  $0 --latest                          # Restore from latest backup
  $0 -b backup-20241122-143022        # Restore specific backup
  $0 --latest --force                  # Restore latest without confirmation
  $0 --test -b backup-20241122-143022 # Test restore to temp container

Environment Variables:
  BACKUP_BASE_DIR    Location of backups (default: ~/FalkorDBBackups)
  CONTAINER_NAME     FalkorDB container name (default: falkordb)

EOF
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Main restore process
echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}         FalkorDB Restore Utility              ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

log "========================================="
log "Starting FalkorDB restore process"
log "========================================="

# If no backup specified, show list and prompt
if [ -z "$BACKUP_PATH" ]; then
    list_backups
    
    echo -e "${YELLOW}Enter the backup name to restore (e.g., backup-20241122-143022):${NC}"
    read -r BACKUP_NAME
    
    if [ -z "$BACKUP_NAME" ]; then
        error_exit "No backup specified"
    fi
    
    # Handle full path or just backup name
    if [[ "$BACKUP_NAME" = /* ]]; then
        BACKUP_PATH="$BACKUP_NAME"
    else
        BACKUP_PATH="$BACKUP_BASE_DIR/$BACKUP_NAME"
    fi
fi

# Resolve symlink if using latest
if [ -L "$BACKUP_PATH" ]; then
    BACKUP_PATH=$(readlink -f "$BACKUP_PATH")
    log "Resolved symlink to: $BACKUP_PATH"
fi

# Validate the backup
validate_backup "$BACKUP_PATH"

# Show backup details
echo ""
echo -e "${YELLOW}Backup Details:${NC}"
echo "  Path: $BACKUP_PATH"
echo "  Size: $(du -sh "$BACKUP_PATH" | cut -f1)"

if [ -f "$BACKUP_PATH/backup-metadata.json" ]; then
    echo "  Timestamp: $(grep -o '"timestamp"[[:space:]]*:[[:space:]]*"[^"]*"' "$BACKUP_PATH/backup-metadata.json" | cut -d'"' -f4)"
    echo "  Graphs: $(grep -o '"graph_count"[[:space:]]*:[[:space:]]*[0-9]*' "$BACKUP_PATH/backup-metadata.json" | grep -o '[0-9]*$')"
fi

echo ""

# Test restore mode
if [ "$TEST_RESTORE" = true ]; then
    echo -e "${BLUE}TEST RESTORE MODE - Will restore to temporary container${NC}"
    log "Running in test restore mode"
    
    # Modify container name for test
    ORIGINAL_CONTAINER="$CONTAINER_NAME"
    CONTAINER_NAME="${TEST_RESTORE_CONTAINER:-falkordb-test-restore}"
    REDIS_PORT="${TEST_RESTORE_PORT:-6380}"
    
    echo "Test container: $CONTAINER_NAME (port: $REDIS_PORT)"
fi

# Warning and confirmation
if [ "$FORCE_RESTORE" = false ]; then
    echo -e "${RED}WARNING: This will replace all current FalkorDB data!${NC}"
    echo -e "${YELLOW}Are you sure you want to restore from this backup? (yes/no)${NC}"
    read -r CONFIRMATION
    
    if [ "$CONFIRMATION" != "yes" ]; then
        echo -e "${YELLOW}Restore cancelled${NC}"
        log "Restore cancelled by user"
        exit 0
    fi
fi

# Create safety backup (unless skipped or in test mode)
if [ "$SKIP_SAFETY" = false ] && [ "$TEST_RESTORE" = false ]; then
    create_safety_backup
fi

# Perform the restore
perform_restore "$BACKUP_PATH"

# Verify the restoration
verify_restoration "$BACKUP_PATH"

# Cleanup test container if in test mode
if [ "$TEST_RESTORE" = true ]; then
    echo ""
    echo -e "${YELLOW}Test restore completed. Test container is running on port $REDIS_PORT${NC}"
    echo "To connect: redis-cli -p $REDIS_PORT"
    echo "To stop test container: docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
    
    # Restore original container name
    CONTAINER_NAME="$ORIGINAL_CONTAINER"
fi

log "========================================="
log "Restore completed at $(date)"
log "========================================="

echo ""
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}Restore completed successfully at $(date)${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""
echo "You can verify the restoration by:"
echo "  1. Running: docker exec $CONTAINER_NAME redis-cli GRAPH.LIST"
echo "  2. Opening the browser UI: https://falkordb-browser.local/"
echo "  3. Running the monitoring script: ./scripts/monitor.sh"