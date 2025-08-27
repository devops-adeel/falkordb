#!/bin/bash

# FalkorDB Automated Backup Script
# Supports cron scheduling and optional cloud storage
# Now uses the enhanced backup system with centralized configuration

set -e

# Determine script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Check if new backup system exists
if [ -f "$PROJECT_ROOT/backup/scripts/falkordb-backup.sh" ]; then
    # Use the new enhanced backup system
    NEW_BACKUP_SYSTEM=true
    CONFIG_FILE="$PROJECT_ROOT/backup/configs/backup.conf"
    BACKUP_SCRIPT="$PROJECT_ROOT/backup/scripts/falkordb-backup.sh"
    LOG_DIR="$PROJECT_ROOT/backup/logs"
else
    # Fallback to legacy configuration
    NEW_BACKUP_SYSTEM=false
    CONFIG_FILE=""
    BACKUP_SCRIPT=""
    LOG_DIR="$PROJECT_ROOT/backups"
fi

# Load configuration based on system
if [ "$NEW_BACKUP_SYSTEM" = true ] && [ -f "$CONFIG_FILE" ]; then
    # Load new configuration
    source "$CONFIG_FILE"
    LOG_FILE="$LOG_DIR/automated-backup-$(date +%Y%m%d-%H%M%S).log"
else
    # Legacy configuration
    if [ -f .env ]; then
        set -a
        source <(grep -v '^#' .env | grep -v '^$')
        set +a
    fi
    BACKUP_DIR="${BACKUP_DIR:-./backups}"
    LOG_FILE="${LOG_FILE:-./backups/backup.log}"
    RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
fi

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="falkordb_backup_${DATE}.rdb"

# Cloud backup settings (optional)
ENABLE_S3="${ENABLE_S3:-false}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-falkordb-backups}"

# Notification settings (optional)
ENABLE_NOTIFICATIONS="${ENABLE_NOTIFICATIONS:-false}"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Notification function
send_notification() {
    local status=$1
    local message=$2
    
    if [ "$ENABLE_NOTIFICATIONS" = "true" ] && [ -n "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"FalkorDB Backup $status: $message\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
}

# Function to perform backup
perform_backup() {
    log_message "INFO" "Starting automated backup process"
    
    # If new backup system is available, use it
    if [ "$NEW_BACKUP_SYSTEM" = true ]; then
        log_message "INFO" "Using enhanced backup system"
        
        # Run the new backup script
        if "$BACKUP_SCRIPT" >> "$LOG_FILE" 2>&1; then
            log_message "INFO" "Backup completed successfully using enhanced system"
            send_notification "SUCCESS" "Backup completed using enhanced system"
            return 0
        else
            log_message "ERROR" "Backup failed using enhanced system"
            send_notification "FAILED" "Enhanced backup system failed"
            return 1
        fi
    fi
    
    # Legacy backup process
    log_message "INFO" "Using legacy backup process"
    
    # Check if FalkorDB container is running
    if ! docker ps | grep -q falkordb; then
        log_message "ERROR" "FalkorDB container is not running"
        send_notification "FAILED" "Container not running"
        exit 1
    fi
    
    # Get database size
    DB_SIZE=$(docker exec falkordb redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r ' || echo "unknown")
    log_message "INFO" "Current database size: $DB_SIZE"
    
    # Trigger background save
    log_message "INFO" "Initiating background save"
    docker exec falkordb redis-cli BGSAVE
    
    # Wait for background save to complete
    local wait_count=0
    local max_wait=60  # Maximum 60 seconds
    
    while [ $wait_count -lt $max_wait ]; do
        if ! docker exec falkordb redis-cli INFO persistence | grep -q "rdb_bgsave_in_progress:1"; then
            break
        fi
        sleep 1
        ((wait_count++))
    done
    
    if [ $wait_count -eq $max_wait ]; then
        log_message "ERROR" "Background save timeout"
        send_notification "FAILED" "Background save timeout"
        exit 1
    fi
    
    log_message "INFO" "Background save completed"
    
    # Copy backup from Docker volume
    local backup_copied=false
    
    # Try OrbStack volume location first
    if [ -f ~/OrbStack/docker/volumes/falkordb_falkordb_data/_data/dump.rdb ]; then
        cp ~/OrbStack/docker/volumes/falkordb_falkordb_data/_data/dump.rdb "$BACKUP_DIR/$BACKUP_FILE"
        backup_copied=true
        log_message "INFO" "Backup copied from OrbStack volume"
    fi
    
    # Fallback: Copy from container
    if [ "$backup_copied" = false ]; then
        docker exec falkordb cat /var/lib/falkordb/data/dump.rdb > "$BACKUP_DIR/$BACKUP_FILE"
        log_message "INFO" "Backup copied from container"
    fi
    
    # Verify backup file
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        BACKUP_SIZE=$(ls -lh "$BACKUP_DIR/$BACKUP_FILE" | awk '{print $5}')
        log_message "INFO" "Backup created successfully: $BACKUP_FILE (Size: $BACKUP_SIZE)"
    else
        log_message "ERROR" "Backup failed - file not created"
        send_notification "FAILED" "File creation failed"
        exit 1
    fi
    
    # Upload to S3 if enabled
    if [ "$ENABLE_S3" = "true" ] && [ -n "$S3_BUCKET" ]; then
        log_message "INFO" "Uploading backup to S3"
        
        if command -v aws &> /dev/null; then
            if aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_FILE"; then
                log_message "INFO" "Backup uploaded to S3 successfully"
            else
                log_message "WARNING" "Failed to upload backup to S3"
            fi
        else
            log_message "WARNING" "AWS CLI not found, skipping S3 upload"
        fi
    fi
    
    # Clean up old local backups
    local deleted_count=0
    while IFS= read -r file; do
        log_message "INFO" "Removing old backup: $(basename "$file")"
        rm "$file"
        ((deleted_count++))
    done < <(find "$BACKUP_DIR" -name "falkordb_backup_*.rdb" -type f -mtime +$RETENTION_DAYS)
    
    if [ $deleted_count -gt 0 ]; then
        log_message "INFO" "Removed $deleted_count old backup(s)"
    fi
    
    # Clean up old S3 backups if enabled
    if [ "$ENABLE_S3" = "true" ] && [ -n "$S3_BUCKET" ]; then
        if command -v aws &> /dev/null; then
            log_message "INFO" "Cleaning up old S3 backups"
            
            # List and delete files older than retention period
            aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | while read -r line; do
                file_date=$(echo "$line" | awk '{print $1}')
                file_name=$(echo "$line" | awk '{print $4}')
                
                if [ -n "$file_name" ]; then
                    file_age=$(( ($(date +%s) - $(date -d "$file_date" +%s)) / 86400 ))
                    
                    if [ $file_age -gt $RETENTION_DAYS ]; then
                        aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/$file_name"
                        log_message "INFO" "Deleted old S3 backup: $file_name"
                    fi
                fi
            done 2>/dev/null || true
        fi
    fi
    
    # Generate backup report
    local backup_count=$(ls -1 "$BACKUP_DIR"/falkordb_backup_*.rdb 2>/dev/null | wc -l)
    log_message "INFO" "Backup completed. Total local backups: $backup_count"
    
    send_notification "SUCCESS" "Backup $BACKUP_FILE created (Size: $BACKUP_SIZE)"
}

# Function to setup cron job
setup_cron() {
    local schedule=$1
    local script_path=$(realpath "$0")
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "$script_path"; then
        echo "Cron job already exists. Updating..."
        # Remove existing entry
        (crontab -l 2>/dev/null | grep -v "$script_path") | crontab -
    fi
    
    # Add new cron job
    (crontab -l 2>/dev/null; echo "$schedule cd $(pwd) && $script_path run >> $LOG_FILE 2>&1") | crontab -
    
    echo "Cron job installed successfully"
    echo "Schedule: $schedule"
    echo "View cron jobs: crontab -l"
    echo "Remove cron job: crontab -l | grep -v '$script_path' | crontab -"
}

# Parse command line arguments
ACTION=""
CRON_SCHEDULE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        run)
            ACTION="run"
            shift
            ;;
        setup-cron)
            ACTION="setup-cron"
            CRON_SCHEDULE="${2:-0 */6 * * *}"  # Default: every 6 hours
            shift 2
            ;;
        test)
            ACTION="test"
            shift
            ;;
        -h|--help)
            cat << EOF
FalkorDB Automated Backup Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  run           Perform a backup now
  setup-cron    Setup automated backups via cron
  test          Test backup configuration

Options for setup-cron:
  Schedule format: "minute hour day month weekday"
  
  Examples:
    "0 * * * *"     - Every hour
    "0 */6 * * *"   - Every 6 hours (default)
    "0 2 * * *"     - Daily at 2 AM
    "0 2 * * 0"     - Weekly on Sunday at 2 AM
    "0 2 1 * *"     - Monthly on the 1st at 2 AM

Environment Variables:
  BACKUP_DIR              - Backup directory (default: ./backups)
  BACKUP_RETENTION_DAYS   - Days to keep backups (default: 7)
  ENABLE_S3              - Enable S3 uploads (true/false, default: false)
  S3_BUCKET              - S3 bucket name
  S3_PREFIX              - S3 prefix/folder (default: falkordb-backups)
  ENABLE_NOTIFICATIONS   - Enable Slack notifications (true/false, default: false)
  SLACK_WEBHOOK          - Slack webhook URL

Examples:
  $0 run                           # Run backup now
  $0 setup-cron "0 */6 * * *"     # Setup 6-hour backups
  $0 test                          # Test configuration
  
  # With S3 backup:
  ENABLE_S3=true S3_BUCKET=my-bucket $0 run
  
  # With notifications:
  ENABLE_NOTIFICATIONS=true SLACK_WEBHOOK=https://... $0 run
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

# Execute action
case "$ACTION" in
    run)
        perform_backup
        ;;
    setup-cron)
        setup_cron "$CRON_SCHEDULE"
        ;;
    test)
        echo "Testing backup configuration..."
        echo ""
        echo "Configuration:"
        echo "  Backup directory: $BACKUP_DIR"
        echo "  Retention days: $RETENTION_DAYS"
        echo "  Log file: $LOG_FILE"
        echo "  S3 enabled: $ENABLE_S3"
        if [ "$ENABLE_S3" = "true" ]; then
            echo "  S3 bucket: $S3_BUCKET"
            echo "  S3 prefix: $S3_PREFIX"
            echo "  AWS CLI available: $(command -v aws &> /dev/null && echo "yes" || echo "no")"
        fi
        echo "  Notifications enabled: $ENABLE_NOTIFICATIONS"
        echo ""
        
        # Test FalkorDB connection
        echo "Testing FalkorDB connection..."
        if docker exec falkordb redis-cli ping 2>/dev/null | grep -q PONG; then
            echo "✓ FalkorDB is accessible"
        else
            echo "✗ FalkorDB is not accessible"
            exit 1
        fi
        
        # Test backup directory
        echo "Testing backup directory..."
        if [ -w "$BACKUP_DIR" ] || mkdir -p "$BACKUP_DIR" 2>/dev/null; then
            echo "✓ Backup directory is writable"
        else
            echo "✗ Cannot write to backup directory"
            exit 1
        fi
        
        echo ""
        echo "Configuration test completed successfully"
        ;;
    *)
        echo "No action specified. Use --help for usage information"
        exit 1
        ;;
esac