#!/bin/bash

# FalkorDB Backup Monitoring Script
# Checks backup health and sends alerts

set -euo pipefail

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../configs/backup.conf"

# Default configuration
BACKUP_BASE_DIR="${HOME}/FalkorDBBackups"
LOG_DIR="${SCRIPT_DIR}/../logs"
ALERT_THRESHOLD_HOURS=26  # Alert if no backup in 26 hours
SIZE_WARNING_GB=10        # Warn if total backups exceed this size
MIN_BACKUP_SIZE_MB=1      # Minimum expected backup size

# Source config file if exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Source environment variables
if [ -f "$HOME/.env" ]; then
    set -a
    source "$HOME/.env"
    set +a
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Tracking variables
OVERALL_STATUS="HEALTHY"
ISSUES=()

# Send metrics to Grafana Alloy
send_metrics() {
    local metric_name="$1"
    local value="$2"
    
    if [ "${METRICS_ENABLED:-false}" = "true" ] && [ -n "${ALLOY_OTLP_HTTP:-}" ]; then
        local timestamp=$(date +%s%N)
        curl -s -X POST "${ALLOY_OTLP_HTTP}/v1/metrics" \
            -H "Content-Type: application/json" \
            -d "{
                \"resourceMetrics\": [{
                    \"scopeMetrics\": [{
                        \"metrics\": [{
                            \"name\": \"falkordb_backup_monitor_${metric_name}\",
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

# Check last backup time
check_last_backup() {
    local latest_backup=""
    local latest_time=0
    
    if [ ! -d "$BACKUP_BASE_DIR" ]; then
        echo -e "${RED}✗ Backup directory does not exist: $BACKUP_BASE_DIR${NC}"
        OVERALL_STATUS="CRITICAL"
        ISSUES+=("Backup directory missing")
        send_metrics "backup_directory_exists" 0
        return 1
    fi
    
    send_metrics "backup_directory_exists" 1
    
    # Find most recent backup
    for backup_dir in "$BACKUP_BASE_DIR"/backup-*/; do
        if [ -d "$backup_dir" ]; then
            # macOS stat command
            dir_time=$(stat -f %m "$backup_dir" 2>/dev/null)
            if [ $dir_time -gt $latest_time ]; then
                latest_time=$dir_time
                latest_backup="$backup_dir"
            fi
        fi
    done
    
    if [ -z "$latest_backup" ]; then
        echo -e "${RED}✗ No backups found${NC}"
        OVERALL_STATUS="CRITICAL"
        ISSUES+=("No backups found")
        send_metrics "backups_exist" 0
        return 1
    fi
    
    send_metrics "backups_exist" 1
    
    # Calculate age in hours
    current_time=$(date +%s)
    age_seconds=$((current_time - latest_time))
    age_hours=$((age_seconds / 3600))
    
    # Send age metric
    send_metrics "last_backup_age_hours" "$age_hours"
    
    if [ $age_hours -gt $ALERT_THRESHOLD_HOURS ]; then
        echo -e "${RED}✗ Last backup is $age_hours hours old (threshold: $ALERT_THRESHOLD_HOURS hours)${NC}"
        echo "  Location: $latest_backup"
        OVERALL_STATUS="WARNING"
        ISSUES+=("Backup overdue by $((age_hours - ALERT_THRESHOLD_HOURS)) hours")
        send_metrics "backup_schedule_ok" 0
        return 1
    else
        echo -e "${GREEN}✓ Last backup is $age_hours hours old${NC}"
        echo "  Location: $latest_backup"
        send_metrics "backup_schedule_ok" 1
        return 0
    fi
}

# Check backup sizes
check_backup_sizes() {
    if [ ! -d "$BACKUP_BASE_DIR" ]; then
        return 1
    fi
    
    # Get total size in KB (macOS du doesn't have -b option)
    total_size_kb=$(du -sk "$BACKUP_BASE_DIR" 2>/dev/null | cut -f1)
    total_size_gb=$((total_size_kb / 1024 / 1024))
    
    # Send size metric
    send_metrics "total_backup_size_gb" "$total_size_gb"
    
    if [ $total_size_gb -gt $SIZE_WARNING_GB ]; then
        echo -e "${YELLOW}⚠ Total backup size: ${total_size_gb}GB (warning threshold: ${SIZE_WARNING_GB}GB)${NC}"
        
        # Show breakdown
        echo "  Breakdown by backup:"
        for backup_dir in "$BACKUP_BASE_DIR"/backup-*/; do
            if [ -d "$backup_dir" ]; then
                size=$(du -sh "$backup_dir" 2>/dev/null | cut -f1)
                name=$(basename "$backup_dir")
                echo "    $name: $size"
            fi
        done
        
        OVERALL_STATUS="WARNING"
        ISSUES+=("Storage usage high: ${total_size_gb}GB")
        send_metrics "storage_usage_ok" 0
        return 1
    else
        echo -e "${GREEN}✓ Total backup size: ${total_size_gb}GB${NC}"
        send_metrics "storage_usage_ok" 1
        return 0
    fi
}

# Check backup integrity
check_backup_integrity() {
    local latest_backup=""
    
    # Get latest backup
    if [ -L "$BACKUP_BASE_DIR/latest" ]; then
        latest_backup=$(readlink "$BACKUP_BASE_DIR/latest")
    else
        # Find most recent backup
        latest_backup=$(ls -dt "$BACKUP_BASE_DIR"/backup-*/ 2>/dev/null | head -1)
    fi
    
    if [ -z "$latest_backup" ] || [ ! -d "$latest_backup" ]; then
        echo -e "${RED}✗ Cannot check integrity - no backups found${NC}"
        send_metrics "integrity_check_passed" 0
        return 1
    fi
    
    local errors=0
    
    # Check RDB backup
    local rdb_file="$latest_backup/rdb/dump.rdb.gz"
    if [ -f "$rdb_file" ]; then
        if gzip -t "$rdb_file" 2>/dev/null; then
            echo -e "${GREEN}✓ RDB backup is valid${NC}"
            
            # Check size
            local size_bytes=$(stat -f%z "$rdb_file" 2>/dev/null)
            local size_mb=$((size_bytes / 1024 / 1024))
            
            if [ $size_mb -lt ${MIN_BACKUP_SIZE_MB:-1} ]; then
                echo -e "${YELLOW}⚠ RDB backup suspiciously small: ${size_mb}MB${NC}"
                ISSUES+=("Small backup size: ${size_mb}MB")
                ((errors++))
            fi
        else
            echo -e "${RED}✗ RDB backup is corrupted${NC}"
            OVERALL_STATUS="CRITICAL"
            ISSUES+=("RDB backup corrupted")
            ((errors++))
        fi
    else
        echo -e "${YELLOW}⚠ RDB backup not found${NC}"
        ISSUES+=("RDB backup missing")
        ((errors++))
    fi
    
    # Check schema backup
    if [ -d "$latest_backup/schema" ] && [ "$(ls -A "$latest_backup/schema" 2>/dev/null)" ]; then
        echo -e "${GREEN}✓ Schema backup exists${NC}"
    else
        echo -e "${YELLOW}⚠ Schema backup not found${NC}"
        ISSUES+=("Schema backup missing")
    fi
    
    # Check checksums
    if [ -f "$latest_backup/checksums/SHA256SUMS" ]; then
        echo -e "${GREEN}✓ Checksums file exists${NC}"
        
        # Verify checksums
        cd "$latest_backup"
        if shasum -a 256 -c checksums/SHA256SUMS > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Checksum verification passed${NC}"
        else
            echo -e "${RED}✗ Checksum verification failed${NC}"
            OVERALL_STATUS="CRITICAL"
            ISSUES+=("Checksum mismatch")
            ((errors++))
        fi
        cd - > /dev/null
    else
        echo -e "${YELLOW}⚠ Checksums not found${NC}"
    fi
    
    # Check metadata
    if [ -f "$latest_backup/backup-metadata.json" ]; then
        echo -e "${GREEN}✓ Metadata file exists${NC}"
        
        # Parse and display key metrics
        local graph_count=$(grep -o '"graph_count"[[:space:]]*:[[:space:]]*[0-9]*' "$latest_backup/backup-metadata.json" | grep -o '[0-9]*$')
        if [ -n "$graph_count" ]; then
            echo "  Graphs in backup: $graph_count"
            send_metrics "backup_graph_count" "$graph_count"
        fi
    else
        echo -e "${YELLOW}⚠ Metadata file not found${NC}"
    fi
    
    if [ $errors -eq 0 ]; then
        send_metrics "integrity_check_passed" 1
        return 0
    else
        send_metrics "integrity_check_passed" 0
        return 1
    fi
}

# Check log files for errors
check_logs() {
    if [ ! -d "$LOG_DIR" ]; then
        echo -e "${YELLOW}⚠ Log directory not found${NC}"
        return 1
    fi
    
    # Find most recent backup log
    latest_log=$(ls -t "$LOG_DIR"/backup-*.log 2>/dev/null | head -1)
    
    if [ -z "$latest_log" ]; then
        echo -e "${YELLOW}⚠ No backup logs found${NC}"
        return 1
    fi
    
    # Check for errors in latest log
    error_count=$(grep -c "ERROR" "$latest_log" 2>/dev/null || echo 0)
    warning_count=$(grep -c "WARNING" "$latest_log" 2>/dev/null || echo 0)
    
    send_metrics "log_error_count" "$error_count"
    send_metrics "log_warning_count" "$warning_count"
    
    if [ "$error_count" -gt 0 ]; then
        echo -e "${RED}✗ Found $error_count errors in latest backup log${NC}"
        echo "  Log: $latest_log"
        echo "  Recent errors:"
        grep "ERROR" "$latest_log" | tail -3 | sed 's/^/    /'
        OVERALL_STATUS="WARNING"
        ISSUES+=("$error_count errors in logs")
        return 1
    elif [ "$warning_count" -gt 0 ]; then
        echo -e "${YELLOW}⚠ Found $warning_count warnings in latest backup log${NC}"
        echo "  Log: $latest_log"
        return 0
    else
        echo -e "${GREEN}✓ No errors in latest backup log${NC}"
        return 0
    fi
}

# Check FalkorDB connectivity
check_falkordb_status() {
    if docker ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME:-falkordb}$"; then
        if docker exec "${CONTAINER_NAME:-falkordb}" redis-cli ping 2>/dev/null | grep -q PONG; then
            echo -e "${GREEN}✓ FalkorDB is running and responsive${NC}"
            send_metrics "falkordb_running" 1
            
            # Get current graph count
            local current_graphs=$(docker exec "${CONTAINER_NAME:-falkordb}" redis-cli GRAPH.LIST 2>/dev/null || echo "")
            if [ -n "$current_graphs" ]; then
                local graph_count=$(echo "$current_graphs" | wc -l | tr -d ' ')
                echo "  Current graphs: $graph_count"
                send_metrics "current_graph_count" "$graph_count"
            fi
        else
            echo -e "${YELLOW}⚠ FalkorDB container running but not responding${NC}"
            send_metrics "falkordb_running" 0.5
        fi
    else
        echo -e "${YELLOW}⚠ FalkorDB container is not running${NC}"
        send_metrics "falkordb_running" 0
    fi
}

# Clean old logs
clean_old_logs() {
    if [ ! -d "$LOG_DIR" ]; then
        return
    fi
    
    # Remove logs older than LOG_RETENTION days
    local cleaned_count=$(find "$LOG_DIR" -name "*.log" -mtime +${LOG_RETENTION:-30} 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$cleaned_count" -gt 0 ]; then
        find "$LOG_DIR" -name "*.log" -mtime +${LOG_RETENTION:-30} -delete 2>/dev/null
        echo -e "${GREEN}✓ Cleaned $cleaned_count logs older than ${LOG_RETENTION:-30} days${NC}"
    else
        echo -e "${GREEN}✓ No old logs to clean${NC}"
    fi
}

# Generate report
generate_report() {
    echo "========================================"
    echo "FalkorDB Backup Monitoring Report"
    echo "$(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"
    echo ""
    
    echo "📅 Backup Schedule Status:"
    check_last_backup
    echo ""
    
    echo "💾 Storage Usage:"
    check_backup_sizes
    echo ""
    
    echo "✅ Backup Integrity:"
    check_backup_integrity
    echo ""
    
    echo "📝 Log Analysis:"
    check_logs
    echo ""
    
    echo "🔄 FalkorDB Status:"
    check_falkordb_status
    echo ""
    
    echo "🧹 Maintenance:"
    clean_old_logs
    echo ""
    
    echo "========================================"
    
    # Determine overall status
    if [ "$OVERALL_STATUS" = "HEALTHY" ]; then
        echo -e "${GREEN}Overall Status: HEALTHY ✓${NC}"
        send_metrics "overall_health" 1
        EXIT_CODE=0
    elif [ "$OVERALL_STATUS" = "WARNING" ]; then
        echo -e "${YELLOW}Overall Status: WARNING ⚠${NC}"
        if [ ${#ISSUES[@]} -gt 0 ]; then
            echo "Issues detected:"
            for issue in "${ISSUES[@]}"; do
                echo "  - $issue"
            done
        fi
        send_metrics "overall_health" 0.5
        EXIT_CODE=1
    else
        echo -e "${RED}Overall Status: CRITICAL ✗${NC}"
        if [ ${#ISSUES[@]} -gt 0 ]; then
            echo "Issues detected:"
            for issue in "${ISSUES[@]}"; do
                echo "  - $issue"
            done
        fi
        send_metrics "overall_health" 0
        EXIT_CODE=2
    fi
    
    echo "========================================"
    
    # Send timestamp of last check
    send_metrics "last_check_timestamp" "$(date +%s)"
    
    return $EXIT_CODE
}

# Send notification
send_notification() {
    local status=$1
    local message=$2
    
    # Check if email notification is configured
    if [ -n "${NOTIFY_EMAIL:-}" ]; then
        if [ "$status" != "HEALTHY" ] || [ "${NOTIFY_ON_SUCCESS:-false}" = "true" ]; then
            echo "$message" | mail -s "FalkorDB Backup Alert: $status" "$NOTIFY_EMAIL" 2>/dev/null || true
        fi
    fi
    
    # Check if Slack notification is configured
    if [ "${ENABLE_NOTIFICATIONS:-false}" = "true" ] && [ -n "${SLACK_WEBHOOK:-}" ]; then
        if [ "$status" != "HEALTHY" ] || [ "${NOTIFY_ON_SUCCESS:-false}" = "true" ]; then
            local color="good"
            [ "$status" = "WARNING" ] && color="warning"
            [ "$status" = "CRITICAL" ] && color="danger"
            
            curl -X POST "$SLACK_WEBHOOK" \
                -H 'Content-Type: application/json' \
                -d "{
                    \"attachments\": [{
                        \"color\": \"$color\",
                        \"title\": \"FalkorDB Backup Status: $status\",
                        \"text\": \"$message\",
                        \"footer\": \"FalkorDB Backup Monitor\",
                        \"ts\": $(date +%s)
                    }]
                }" 2>/dev/null || true
        fi
    fi
}

# Main monitoring process
main() {
    # Check if running in quiet mode
    QUIET_MODE=false
    if [ "${1:-}" = "--quiet" ] || [ "${1:-}" = "-q" ]; then
        QUIET_MODE=true
    fi
    
    # Capture report output
    if [ "$QUIET_MODE" = true ]; then
        report_output=$(generate_report 2>&1)
        exit_code=$?
    else
        generate_report
        exit_code=$?
    fi
    
    # Prepare notification message if needed
    if [ $exit_code -ne 0 ] || [ "${NOTIFY_ON_SUCCESS:-false}" = "true" ]; then
        if [ ${#ISSUES[@]} -gt 0 ]; then
            notification_message="Issues: $(IFS=', '; echo "${ISSUES[*]}")"
        else
            notification_message="All checks passed"
        fi
        
        # Send notifications based on status
        if [ "$OVERALL_STATUS" = "CRITICAL" ]; then
            send_notification "CRITICAL" "$notification_message"
        elif [ "$OVERALL_STATUS" = "WARNING" ]; then
            send_notification "WARNING" "$notification_message"
        elif [ "${NOTIFY_ON_SUCCESS:-false}" = "true" ]; then
            send_notification "HEALTHY" "$notification_message"
        fi
    fi
    
    exit $exit_code
}

# Show help if requested
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat << EOF
FalkorDB Backup Monitoring Script

Usage: $0 [OPTIONS]

Options:
  --quiet, -q    Run in quiet mode (suppress output)
  --help, -h     Show this help message

This script checks:
  - Last backup age
  - Backup integrity
  - Storage usage
  - Log errors
  - FalkorDB status

Exit codes:
  0 - All checks passed (HEALTHY)
  1 - Warnings detected (WARNING)
  2 - Critical issues found (CRITICAL)

Configuration:
  Edit backup/configs/backup.conf to customize monitoring behavior

Environment Variables:
  ALERT_THRESHOLD_HOURS  Hours before alerting about missing backup
  SIZE_WARNING_GB        GB threshold for storage warning
  METRICS_ENABLED        Enable metrics export to Grafana

EOF
    exit 0
fi

# Run main function
main "$@"