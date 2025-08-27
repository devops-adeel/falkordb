#!/bin/bash

# FalkorDB RDB Validation Script
# Validates RDB backup files for integrity and recoverability

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to validate RDB file
validate_rdb_file() {
    local rdb_file="$1"
    local errors=0
    
    echo -e "${BLUE}Validating: $rdb_file${NC}"
    echo "========================================"
    
    # Check if file exists
    if [ ! -f "$rdb_file" ]; then
        echo -e "${RED}✗ File not found${NC}"
        return 1
    fi
    
    # Get file size
    local file_size=$(ls -lh "$rdb_file" | awk '{print $5}')
    echo "File size: $file_size"
    
    # Check if it's a gzip file
    if [[ "$rdb_file" == *.gz ]]; then
        echo -n "Checking gzip integrity... "
        if gzip -t "$rdb_file" 2>/dev/null; then
            echo -e "${GREEN}✓ Valid gzip file${NC}"
            
            # Extract for further validation
            local temp_rdb="/tmp/validate_rdb_$$.rdb"
            gunzip -c "$rdb_file" > "$temp_rdb"
            
            # Validate the uncompressed RDB
            echo -n "Checking RDB format... "
            if head -c 5 "$temp_rdb" | grep -q "REDIS"; then
                echo -e "${GREEN}✓ Valid RDB header${NC}"
            else
                echo -e "${RED}✗ Invalid RDB header${NC}"
                ((errors++))
            fi
            
            # Use redis-check-rdb if available
            if command -v redis-check-rdb &> /dev/null; then
                echo -n "Running redis-check-rdb... "
                if redis-check-rdb "$temp_rdb" > /dev/null 2>&1; then
                    echo -e "${GREEN}✓ RDB structure valid${NC}"
                    
                    # Get detailed info
                    echo ""
                    echo "RDB Details:"
                    redis-check-rdb "$temp_rdb" 2>/dev/null | head -20 || true
                else
                    echo -e "${RED}✗ RDB structure invalid${NC}"
                    ((errors++))
                fi
            else
                echo -e "${YELLOW}⚠ redis-check-rdb not available${NC}"
            fi
            
            # Cleanup
            rm -f "$temp_rdb"
            
        else
            echo -e "${RED}✗ Gzip file corrupted${NC}"
            ((errors++))
        fi
    else
        # Direct RDB file validation
        echo -n "Checking RDB format... "
        if head -c 5 "$rdb_file" | grep -q "REDIS"; then
            echo -e "${GREEN}✓ Valid RDB header${NC}"
            
            # Use redis-check-rdb if available
            if command -v redis-check-rdb &> /dev/null; then
                echo -n "Running redis-check-rdb... "
                if redis-check-rdb "$rdb_file" > /dev/null 2>&1; then
                    echo -e "${GREEN}✓ RDB structure valid${NC}"
                    
                    # Get detailed info
                    echo ""
                    echo "RDB Details:"
                    redis-check-rdb "$rdb_file" 2>/dev/null | head -20 || true
                else
                    echo -e "${RED}✗ RDB structure invalid${NC}"
                    ((errors++))
                fi
            else
                echo -e "${YELLOW}⚠ redis-check-rdb not available${NC}"
            fi
        else
            echo -e "${RED}✗ Invalid RDB header${NC}"
            ((errors++))
        fi
    fi
    
    # Check file age
    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        local file_age_seconds=$(($(date +%s) - $(stat -f %m "$rdb_file")))
    else
        # Linux
        local file_age_seconds=$(($(date +%s) - $(stat -c %Y "$rdb_file")))
    fi
    local file_age_hours=$((file_age_seconds / 3600))
    
    echo "File age: $file_age_hours hours"
    
    if [ $file_age_hours -gt 168 ]; then  # 7 days
        echo -e "${YELLOW}⚠ File is older than 7 days${NC}"
    fi
    
    echo ""
    
    # Return status
    if [ $errors -eq 0 ]; then
        echo -e "${GREEN}✓ Validation PASSED${NC}"
        return 0
    else
        echo -e "${RED}✗ Validation FAILED ($errors errors)${NC}"
        return 1
    fi
}

# Function to validate a backup directory
validate_backup_dir() {
    local backup_dir="$1"
    
    if [ ! -d "$backup_dir" ]; then
        echo -e "${RED}Directory not found: $backup_dir${NC}"
        return 1
    fi
    
    echo -e "${BLUE}===============================================${NC}"
    echo -e "${BLUE}Validating backup: $(basename "$backup_dir")${NC}"
    echo -e "${BLUE}===============================================${NC}"
    echo ""
    
    local validation_passed=true
    
    # Check for RDB file
    local rdb_file="$backup_dir/rdb/dump.rdb.gz"
    if [ -f "$rdb_file" ]; then
        if ! validate_rdb_file "$rdb_file"; then
            validation_passed=false
        fi
    else
        echo -e "${RED}✗ RDB backup not found${NC}"
        validation_passed=false
    fi
    
    # Check metadata
    if [ -f "$backup_dir/backup-metadata.json" ]; then
        echo -e "${GREEN}✓ Metadata file exists${NC}"
        
        # Display key information
        echo "Metadata:"
        grep -E '"timestamp"|"graph_count"|"total_size"' "$backup_dir/backup-metadata.json" | sed 's/^/  /'
    else
        echo -e "${YELLOW}⚠ Metadata file not found${NC}"
    fi
    
    # Check checksums
    if [ -f "$backup_dir/checksums/SHA256SUMS" ]; then
        echo -n "Verifying checksums... "
        cd "$backup_dir"
        if shasum -a 256 -c checksums/SHA256SUMS > /dev/null 2>&1; then
            echo -e "${GREEN}✓ All checksums valid${NC}"
        else
            echo -e "${RED}✗ Checksum mismatch${NC}"
            validation_passed=false
        fi
        cd - > /dev/null
    else
        echo -e "${YELLOW}⚠ No checksums found${NC}"
    fi
    
    echo ""
    
    if [ "$validation_passed" = true ]; then
        echo -e "${GREEN}✓✓✓ Backup validation PASSED ✓✓✓${NC}"
        return 0
    else
        echo -e "${RED}✗✗✗ Backup validation FAILED ✗✗✗${NC}"
        return 1
    fi
}

# Main function
main() {
    local target=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                cat << EOF
FalkorDB RDB Validation Script

Usage: $0 [OPTIONS] [FILE_OR_DIRECTORY]

Options:
  -h, --help     Show this help message

Arguments:
  FILE_OR_DIRECTORY   Path to RDB file or backup directory to validate
                      If not specified, validates the latest backup

Examples:
  $0                                          # Validate latest backup
  $0 ~/FalkorDBBackups/backup-20241122-1430  # Validate specific backup
  $0 /tmp/dump.rdb                           # Validate specific RDB file
  $0 ~/FalkorDBBackups/latest/rdb/dump.rdb.gz # Validate specific compressed RDB

Requirements:
  - redis-check-rdb (optional but recommended)
    Install with: brew install redis (macOS) or apt-get install redis-tools (Linux)

Exit codes:
  0 - Validation passed
  1 - Validation failed

EOF
                exit 0
                ;;
            *)
                target="$1"
                shift
                ;;
        esac
    done
    
    # If no target specified, use latest backup
    if [ -z "$target" ]; then
        # Load configuration to get backup directory
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        CONFIG_FILE="${SCRIPT_DIR}/../configs/backup.conf"
        
        if [ -f "$CONFIG_FILE" ]; then
            source "$CONFIG_FILE"
        fi
        
        BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-${HOME}/FalkorDBBackups}"
        
        if [ -L "$BACKUP_BASE_DIR/latest" ]; then
            target=$(readlink "$BACKUP_BASE_DIR/latest")
            echo "Using latest backup: $target"
            echo ""
        elif [ -d "$BACKUP_BASE_DIR" ]; then
            target=$(ls -dt "$BACKUP_BASE_DIR"/backup-*/ 2>/dev/null | head -1)
            if [ -n "$target" ]; then
                echo "Using most recent backup: $target"
                echo ""
            else
                echo -e "${RED}No backups found in $BACKUP_BASE_DIR${NC}"
                exit 1
            fi
        else
            echo -e "${RED}Backup directory not found: $BACKUP_BASE_DIR${NC}"
            exit 1
        fi
    fi
    
    # Check if redis-check-rdb is available
    if ! command -v redis-check-rdb &> /dev/null; then
        echo -e "${YELLOW}===============================================${NC}"
        echo -e "${YELLOW}WARNING: redis-check-rdb not found${NC}"
        echo -e "${YELLOW}For complete validation, install Redis tools:${NC}"
        echo -e "${YELLOW}  macOS: brew install redis${NC}"
        echo -e "${YELLOW}  Linux: apt-get install redis-tools${NC}"
        echo -e "${YELLOW}===============================================${NC}"
        echo ""
    fi
    
    # Determine if target is a file or directory
    if [ -f "$target" ]; then
        # Validate single RDB file
        if validate_rdb_file "$target"; then
            exit 0
        else
            exit 1
        fi
    elif [ -d "$target" ]; then
        # Validate backup directory
        if validate_backup_dir "$target"; then
            exit 0
        else
            exit 1
        fi
    else
        echo -e "${RED}Target not found: $target${NC}"
        exit 1
    fi
}

# Run main function
main "$@"