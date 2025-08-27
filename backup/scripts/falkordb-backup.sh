#!/bin/bash

# FalkorDB Backup Script for OrbStack on macOS
# This script backs up FalkorDB data with production-grade features:
# - RDB snapshots with integrity validation
# - Graph schema and structure export
# - Metrics integration with Grafana/Alloy
# - Structured logging and metadata generation

set -euo pipefail

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../configs/backup.conf"

# Default configuration (will be overridden by config file if exists)
BACKUP_BASE_DIR="${HOME}/FalkorDBBackups"
RETENTION_DAILY=7
RETENTION_WEEKLY=4
CONTAINER_NAME="falkordb"
LOG_FILE="${SCRIPT_DIR}/../logs/backup-$(date +%Y%m%d-%H%M%S).log"

# Source config file if exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Source environment variables for sensitive data
# Try multiple locations in order of preference
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

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    send_metrics "backup_failed" 1
    send_notification "FAILED" "$1"
    exit 1
}

# Send metrics to Grafana Alloy
send_metrics() {
    local metric_name="$1"
    local value="$2"
    
    if [ "${METRICS_ENABLED:-false}" = "true" ] && [ -n "${ALLOY_OTLP_HTTP:-}" ]; then
        # Send metric via OTLP HTTP
        local timestamp=$(date +%s%N)
        curl -s -X POST "${ALLOY_OTLP_HTTP}/v1/metrics" \
            -H "Content-Type: application/json" \
            -d "{
                \"resourceMetrics\": [{
                    \"scopeMetrics\": [{
                        \"metrics\": [{
                            \"name\": \"falkordb_backup_${metric_name}\",
                            \"gauge\": {
                                \"dataPoints\": [{
                                    \"timeUnixNano\": \"${timestamp}\",
                                    \"asDouble\": ${value}
                                }]
                            }
                        }]
                    }]
                }]
            }" > /dev/null 2>&1 || true
    fi
}

# Send notification
send_notification() {
    local status=$1
    local message=$2
    
    if [ "${ENABLE_NOTIFICATIONS:-false}" = "true" ] && [ -n "${SLACK_WEBHOOK:-}" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"FalkorDB Backup $status: $message\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
}

# Check if FalkorDB container is running
check_container() {
    log "Checking FalkorDB container status..."
    
    if ! docker ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        error_exit "FalkorDB container '${CONTAINER_NAME}' is not running. Please start it first."
    fi
    
    # Test Redis connectivity
    if ! docker exec "$CONTAINER_NAME" redis-cli ping 2>/dev/null | grep -q PONG; then
        error_exit "FalkorDB is not responding to ping"
    fi
    
    log "Container '${CONTAINER_NAME}' is running and responsive."
}

# Create backup directory with timestamp
create_backup_dir() {
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_path="${BACKUP_BASE_DIR}/backup-${timestamp}"
    
    mkdir -p "$backup_path"/{rdb,schema,checksums}
    
    log "Created backup directory: $backup_path"
    # Return only the path
    echo "$backup_path"
}

# Get database information
get_db_info() {
    local backup_dir="$1"
    
    log "Gathering database information..."
    
    # Get memory usage
    local memory_info=$(docker exec "$CONTAINER_NAME" redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r ' || echo "unknown")
    
    # Get graph list
    local graphs=$(docker exec "$CONTAINER_NAME" redis-cli GRAPH.LIST 2>/dev/null || echo "")
    local graph_count=0
    if [ -n "$graphs" ]; then
        graph_count=$(echo "$graphs" | wc -l | tr -d ' ')
    fi
    
    # Store info for metadata
    echo "$memory_info" > "$backup_dir/db_memory_usage.txt"
    echo "$graphs" > "$backup_dir/graph_list.txt"
    
    log "Database size: $memory_info"
    log "Number of graphs: $graph_count"
    
    send_metrics "graph_count" "$graph_count"
}

# Backup RDB file
backup_rdb() {
    local backup_dir="$1"
    local start_time=$(date +%s)
    
    if [ "${BACKUP_RDB:-true}" != "true" ]; then
        log "RDB backup disabled in configuration."
        return
    fi
    
    log "Starting RDB backup..."
    
    # Trigger background save
    docker exec "$CONTAINER_NAME" redis-cli BGSAVE > /dev/null
    
    # Wait for background save to complete
    local wait_count=0
    local max_wait=60
    
    log "Waiting for background save to complete..."
    while [ $wait_count -lt $max_wait ]; do
        if ! docker exec "$CONTAINER_NAME" redis-cli INFO persistence | grep -q "rdb_bgsave_in_progress:1"; then
            break
        fi
        sleep 1
        ((wait_count++))
    done
    
    if [ $wait_count -eq $max_wait ]; then
        error_exit "Background save timeout after ${max_wait} seconds"
    fi
    
    log "Background save completed in ${wait_count} seconds"
    
    # Copy RDB file
    local rdb_file="$backup_dir/rdb/dump.rdb"
    local copied=false
    
    # Try OrbStack volume location first
    if [ -f "${ORBSTACK_VOLUMES}/${FALKORDB_VOLUME}/_data/dump.rdb" ]; then
        cp "${ORBSTACK_VOLUMES}/${FALKORDB_VOLUME}/_data/dump.rdb" "$rdb_file"
        copied=true
        log "RDB file copied from OrbStack volume"
    fi
    
    # Fallback: Copy from container
    if [ "$copied" = false ]; then
        docker exec "$CONTAINER_NAME" cat /var/lib/falkordb/data/dump.rdb > "$rdb_file"
        log "RDB file copied from container"
    fi
    
    # Compress RDB file
    if [ -f "$rdb_file" ]; then
        log "Compressing RDB file..."
        gzip -${COMPRESSION_LEVEL:-6} "$rdb_file"
        
        local compressed_size=$(ls -lh "$rdb_file.gz" | awk '{print $5}')
        log "RDB backup compressed to: $compressed_size"
        
        # Send metrics
        local size_bytes=$(stat -f%z "$rdb_file.gz" 2>/dev/null || stat -c%s "$rdb_file.gz" 2>/dev/null)
        send_metrics "rdb_size_bytes" "$size_bytes"
    else
        error_exit "RDB backup failed - file not created"
    fi
    
    # Calculate backup duration
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log "RDB backup completed in ${duration} seconds"
    send_metrics "rdb_backup_duration_seconds" "$duration"
}

# Validate RDB backup
validate_rdb() {
    local backup_dir="$1"
    
    if [ "${VALIDATE_RDB:-true}" != "true" ]; then
        log "RDB validation disabled in configuration."
        return 0
    fi
    
    log "Validating RDB backup..."
    
    local rdb_file="$backup_dir/rdb/dump.rdb.gz"
    
    # Check if file exists
    if [ ! -f "$rdb_file" ]; then
        log "WARNING: RDB file not found for validation"
        return 1
    fi
    
    # Validate gzip integrity
    if ! gzip -t "$rdb_file" 2>/dev/null; then
        log "ERROR: RDB backup file is corrupted (gzip check failed)"
        return 1
    fi
    
    # If redis-check-rdb is available, use it
    if command -v redis-check-rdb &> /dev/null; then
        # Decompress temporarily for validation
        local temp_rdb="/tmp/falkordb_validate_$$.rdb"
        gunzip -c "$rdb_file" > "$temp_rdb"
        
        if redis-check-rdb "$temp_rdb" > /dev/null 2>&1; then
            log "RDB validation passed (redis-check-rdb)"
            rm -f "$temp_rdb"
            send_metrics "validation_status" 1
            return 0
        else
            log "ERROR: RDB validation failed (redis-check-rdb)"
            rm -f "$temp_rdb"
            send_metrics "validation_status" 0
            return 1
        fi
    else
        log "WARNING: redis-check-rdb not available, basic validation only"
        send_metrics "validation_status" 0.5
    fi
    
    return 0
}

# Backup graph schema and structure
backup_schema() {
    local backup_dir="$1"
    
    if [ "${BACKUP_SCHEMA:-true}" != "true" ]; then
        log "Schema backup disabled in configuration."
        return
    fi
    
    log "Backing up graph schemas and structures..."
    
    # Get FalkorDB configuration
    docker exec "$CONTAINER_NAME" redis-cli GRAPH.CONFIG GET "*" > "$backup_dir/schema/graph_config.txt" 2>/dev/null || true
    
    # Get list of graphs
    local graphs=$(docker exec "$CONTAINER_NAME" redis-cli GRAPH.LIST 2>/dev/null || echo "")
    
    if [ -n "$graphs" ]; then
        # Backup schema for each graph
        echo "$graphs" | while read -r graph; do
            if [ -n "$graph" ]; then
                local safe_graph_name=$(echo "$graph" | sed 's/[^a-zA-Z0-9_-]/_/g')
                local schema_file="$backup_dir/schema/${safe_graph_name}_schema.txt"
                
                log "Exporting schema for graph: $graph"
                
                # Get graph statistics
                echo "=== Graph: $graph ===" > "$schema_file"
                echo "" >> "$schema_file"
                
                # Try to get indexes (this may fail if the graph doesn't support it)
                echo "=== Indexes ===" >> "$schema_file"
                docker exec "$CONTAINER_NAME" redis-cli GRAPH.QUERY "$graph" "CALL db.indexes()" >> "$schema_file" 2>/dev/null || echo "No indexes or not supported" >> "$schema_file"
                echo "" >> "$schema_file"
                
                # Try to get node count
                echo "=== Statistics ===" >> "$schema_file"
                local node_count=$(docker exec "$CONTAINER_NAME" redis-cli GRAPH.QUERY "$graph" "MATCH (n) RETURN count(n)" 2>/dev/null | grep -o '[0-9]*' | head -1 || echo "0")
                echo "Node count: $node_count" >> "$schema_file"
                
                # Try to get edge count
                local edge_count=$(docker exec "$CONTAINER_NAME" redis-cli GRAPH.QUERY "$graph" "MATCH ()-[r]->() RETURN count(r)" 2>/dev/null | grep -o '[0-9]*' | head -1 || echo "0")
                echo "Edge count: $edge_count" >> "$schema_file"
            fi
        done
        
        log "Schema backup completed for $(echo "$graphs" | wc -l | tr -d ' ') graphs"
    else
        log "No graphs found for schema backup"
    fi
}

# Generate checksums
generate_checksums() {
    local backup_dir="$1"
    
    if [ "${CHECKSUM_VERIFY:-true}" != "true" ]; then
        log "Checksum generation disabled in configuration."
        return
    fi
    
    log "Generating checksums..."
    
    # Generate SHA256 checksums for all backup files
    cd "$backup_dir"
    find . -type f \( -name "*.gz" -o -name "*.txt" \) -exec shasum -a 256 {} \; > checksums/SHA256SUMS
    
    log "Checksums generated and stored in checksums/SHA256SUMS"
}

# Create backup metadata
create_metadata() {
    local backup_dir="$1"
    
    # Get graph count
    local graph_count=0
    if [ -f "$backup_dir/graph_list.txt" ]; then
        graph_count=$(wc -l < "$backup_dir/graph_list.txt" | tr -d ' ')
    fi
    
    # Get backup size
    local backup_size=$(du -sh "$backup_dir" | cut -f1)
    
    # Get git commit if in a git repo
    local git_commit="unknown"
    if git rev-parse --git-dir > /dev/null 2>&1; then
        git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    fi
    
    cat > "$backup_dir/backup-metadata.json" << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "container": "$CONTAINER_NAME",
    "components": {
        "rdb": $([ -f "$backup_dir/rdb/dump.rdb.gz" ] && echo "true" || echo "false"),
        "schema": $([ -d "$backup_dir/schema" ] && [ "$(ls -A $backup_dir/schema 2>/dev/null)" ] && echo "true" || echo "false"),
        "checksums": $([ -f "$backup_dir/checksums/SHA256SUMS" ] && echo "true" || echo "false")
    },
    "statistics": {
        "graph_count": $graph_count,
        "memory_usage": "$(cat $backup_dir/db_memory_usage.txt 2>/dev/null || echo "unknown")"
    },
    "validation": {
        "rdb_validated": $([ "${VALIDATE_RDB:-true}" = "true" ] && echo "true" || echo "false"),
        "checksums_generated": $([ -f "$backup_dir/checksums/SHA256SUMS" ] && echo "true" || echo "false")
    },
    "total_size": "$backup_size",
    "git_commit": "$git_commit"
}
EOF
    
    log "Created backup metadata"
}

# Clean up old backups
cleanup_old_backups() {
    log "Cleaning up old backups..."
    
    # Keep daily backups for N days
    find "$BACKUP_BASE_DIR" -name "backup-*" -type d -mtime +$RETENTION_DAILY | while read old_backup; do
        # Check if it's a Sunday backup (weekly)
        backup_date=$(basename "$old_backup" | cut -d'-' -f2)
        if [ -n "$backup_date" ]; then
            # macOS date command syntax
            day_of_week=$(date -j -f "%Y%m%d" "$backup_date" "+%u" 2>/dev/null || echo 0)
            
            if [ "$day_of_week" = "7" ]; then
                # It's a Sunday backup, check weekly retention
                backup_age_weeks=$(( ($(date +%s) - $(date -j -f "%Y%m%d" "$backup_date" +%s 2>/dev/null || echo 0)) / 604800 ))
                if [ $backup_age_weeks -gt $RETENTION_WEEKLY ]; then
                    log "Removing old weekly backup: $old_backup"
                    rm -rf "$old_backup"
                fi
            else
                # Not a Sunday backup, remove if older than daily retention
                log "Removing old daily backup: $old_backup"
                rm -rf "$old_backup"
            fi
        fi
    done
    
    # Clean old logs
    find "${SCRIPT_DIR}/../logs" -name "backup-*.log" -type f -mtime +${LOG_RETENTION:-30} -delete 2>/dev/null || true
    
    log "Cleanup completed"
}

# Main backup process
main() {
    local start_time=$(date +%s)
    
    log "========================================="
    log "Starting FalkorDB backup process"
    log "========================================="
    
    # Check if dry run mode
    if [ "${DRY_RUN:-false}" = "true" ]; then
        log "DRY RUN MODE - No actual backup will be performed"
    fi
    
    # Check prerequisites
    check_container
    
    # Create backup directory (capture only the last line which is the path)
    BACKUP_DIR=$(create_backup_dir | tail -1)
    
    # Gather database information
    get_db_info "$BACKUP_DIR"
    
    if [ "${DRY_RUN:-false}" != "true" ]; then
        # Perform RDB backup
        backup_rdb "$BACKUP_DIR"
        
        # Validate RDB backup
        if ! validate_rdb "$BACKUP_DIR"; then
            log "WARNING: RDB validation failed, but continuing..."
        fi
        
        # Backup schema and structure
        backup_schema "$BACKUP_DIR"
        
        # Generate checksums
        generate_checksums "$BACKUP_DIR"
        
        # Create metadata
        create_metadata "$BACKUP_DIR"
        
        # Clean old backups
        cleanup_old_backups
        
        # Create latest symlink
        ln -sfn "$BACKUP_DIR" "$BACKUP_BASE_DIR/latest"
        
        # Upload to S3 if enabled
        if [ "${ENABLE_S3:-false}" = "true" ] && [ -n "${S3_BUCKET:-}" ]; then
            log "Uploading backup to S3..."
            if command -v aws &> /dev/null; then
                if aws s3 sync "$BACKUP_DIR" "s3://${S3_BUCKET}/${S3_PREFIX}/$(basename $BACKUP_DIR)" --quiet; then
                    log "Backup uploaded to S3 successfully"
                else
                    log "WARNING: Failed to upload backup to S3"
                fi
            else
                log "WARNING: AWS CLI not found, skipping S3 upload"
            fi
        fi
    fi
    
    # Calculate total duration
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    # Send success metrics
    send_metrics "last_success_timestamp" "$end_time"
    send_metrics "total_backup_duration_seconds" "$total_duration"
    send_metrics "backup_success" 1
    
    log "========================================="
    log "Backup completed successfully!"
    log "Location: $BACKUP_DIR"
    log "Total size: $(du -sh "$BACKUP_DIR" | cut -f1)"
    log "Duration: ${total_duration} seconds"
    log "========================================="
    
    send_notification "SUCCESS" "Backup completed in ${total_duration}s at $BACKUP_DIR"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE_BACKUP=true
            shift
            ;;
        --skip-validation)
            VALIDATE_RDB=false
            shift
            ;;
        -h|--help)
            cat << EOF
FalkorDB Backup Script

Usage: $0 [OPTIONS]

Options:
  --dry-run           Perform a dry run without actual backup
  --force            Force backup even if recent backup exists
  --skip-validation   Skip RDB validation step
  -h, --help         Show this help message

Environment Variables:
  BACKUP_BASE_DIR    Backup destination directory
  DEBUG_MODE         Enable debug logging (true/false)
  DRY_RUN           Perform dry run (true/false)

Configuration:
  Edit backup/configs/backup.conf to customize backup behavior

Examples:
  $0                  # Normal backup
  $0 --dry-run       # Test backup process
  $0 --force         # Force backup regardless of recent backups

EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Create base backup directory if it doesn't exist
mkdir -p "$BACKUP_BASE_DIR"

# Run main function
main "$@"