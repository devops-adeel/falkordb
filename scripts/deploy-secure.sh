#!/bin/bash

# FalkorDB Secure Deployment with 1Password
# This script deploys FalkorDB with secrets from 1Password
# Following the strict security pattern from langfuse-deployment

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SECRETS_DIR="$PROJECT_ROOT/secrets"
TEMP_ENV="/tmp/.falkordb-env-$$"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-falkordb}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Cleanup function - secure deletion of temporary files
cleanup() {
    if [ -f "$TEMP_ENV" ]; then
        log_info "Cleaning up temporary files..."
        # Use shred for secure deletion if available, otherwise rm
        if command -v shred &> /dev/null; then
            shred -u "$TEMP_ENV" 2>/dev/null || true
        else
            rm -f "$TEMP_ENV"
        fi
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    local missing_deps=()
    
    # Check for 1Password CLI
    if ! command -v op &> /dev/null; then
        missing_deps+=("1Password CLI (op)")
        log_error "1Password CLI is not installed."
        log_info "  Install with: brew install --cask 1password-cli"
    fi
    
    # Check for Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("Docker")
        log_error "Docker is not installed."
    fi
    
    # Check for Docker Compose
    if ! docker compose version &> /dev/null 2>&1; then
        missing_deps+=("Docker Compose")
        log_error "Docker Compose is not available."
    fi
    
    # Exit if any dependencies are missing
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        exit 1
    fi
    
    log_info "✓ All prerequisites met"
}

# Check 1Password authentication
check_1password_auth() {
    log_step "Checking 1Password authentication..."
    
    if ! op account list &> /dev/null; then
        log_warn "Not signed in to 1Password."
        log_info "Please sign in to 1Password:"
        
        if ! op signin; then
            log_error "Failed to sign in to 1Password."
            exit 1
        fi
    else
        log_info "✓ Already signed in to 1Password"
    fi
}

# Verify HomeLab vault exists
verify_vault() {
    log_step "Verifying HomeLab vault..."
    
    if ! op vault get HomeLab &> /dev/null; then
        log_error "HomeLab vault not found."
        log_info "  Create it with: make setup-vault"
        log_info "  Or manually: op vault create HomeLab"
        exit 1
    fi
    
    log_info "✓ HomeLab vault exists"
}

# Inject secrets from 1Password
inject_secrets() {
    log_step "Injecting secrets from 1Password..."
    
    local template_file="$SECRETS_DIR/.env.1password"
    
    # Check if template exists
    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        exit 1
    fi
    
    # Inject secrets into temporary file
    if ! op inject -i "$template_file" -o "$TEMP_ENV" 2>/dev/null; then
        log_error "Failed to inject secrets from 1Password."
        log_info "Please ensure all required secrets exist in HomeLab vault."
        log_info "Run 'make setup-vault' to create missing secrets."
        exit 1
    fi
    
    # Verify no unresolved references remain
    if grep -q "op://" "$TEMP_ENV"; then
        log_error "Some secrets were not resolved:"
        grep "op://" "$TEMP_ENV" | head -5
        log_info ""
        log_info "Create missing secrets with: make setup-vault"
        exit 1
    fi
    
    log_info "✓ Secrets successfully injected"
}

# Deploy FalkorDB with secrets
deploy_services() {
    log_step "Deploying FalkorDB services..."
    
    cd "$PROJECT_ROOT"
    
    # Check if FalkorDB is already running
    if docker compose ps --services --status running | grep -q falkordb; then
        log_info "FalkorDB is already running, restarting with new configuration..."
        docker compose down
        sleep 2
    fi
    
    # Deploy with injected secrets
    log_info "Starting FalkorDB with secure configuration..."
    
    if docker compose --env-file "$TEMP_ENV" up -d; then
        log_info "✓ Services started successfully"
    else
        log_error "Failed to start services"
        exit 1
    fi
}

# Wait for services to be healthy
wait_for_health() {
    log_step "Waiting for services to be healthy..."
    
    local max_wait=30
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        if docker exec falkordb redis-cli ping 2>/dev/null | grep -q PONG; then
            log_info "✓ FalkorDB is healthy"
            return 0
        fi
        
        echo -n "."
        sleep 2
        wait_time=$((wait_time + 2))
    done
    
    echo
    log_warn "FalkorDB may not be fully ready. Check with: docker logs falkordb"
}

# Show deployment information
show_deployment_info() {
    echo
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}       FalkorDB Secure Deployment Complete          ${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo
    echo "  Redis Protocol:  falkordb.local:6379"
    echo "  Browser UI:      http://falkordb-browser.local"
    echo "  Project:         $COMPOSE_PROJECT_NAME"
    echo
    echo "  Commands:"
    echo "    View logs:     docker compose logs -f falkordb"
    echo "    Check status:  docker compose ps"
    echo "    Stop:          docker compose down"
    echo "    Test:          docker exec falkordb redis-cli ping"
    echo
    echo -e "${GREEN}✅ Deployment successful with 1Password secrets${NC}"
    echo
}

# Main execution
main() {
    log_info "Starting FalkorDB secure deployment..."
    echo
    
    check_prerequisites
    check_1password_auth
    verify_vault
    inject_secrets
    deploy_services
    wait_for_health
    show_deployment_info
}

# Run main function
main "$@"