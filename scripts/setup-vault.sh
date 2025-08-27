#!/bin/bash

# FalkorDB 1Password Vault Setup Script
# Creates and configures HomeLab vault with FalkorDB secrets structure
# Auto-generates secure values for required secrets

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SECRETS_DIR="$PROJECT_ROOT/secrets"
MANIFEST_FILE="$SECRETS_DIR/.env.1password.required"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_create() {
    echo -e "${CYAN}[CREATE]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # Check for 1Password CLI
    if ! command -v op &> /dev/null; then
        log_error "1Password CLI is not installed."
        echo
        echo "To install 1Password CLI:"
        echo "  brew install --cask 1password-cli"
        echo
        echo "Or download from:"
        echo "  https://developer.1password.com/docs/cli/get-started/"
        exit 1
    fi
    
    # Check for required tools
    local missing_tools=()
    
    if ! command -v openssl &> /dev/null; then
        missing_tools+=("openssl")
    fi
    
    if ! command -v uuidgen &> /dev/null; then
        missing_tools+=("uuidgen")
    fi
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    log_info "✓ All prerequisites met"
}

# Check 1Password authentication
check_1password_auth() {
    log_step "Checking 1Password authentication..."
    
    if ! op account list &> /dev/null; then
        log_warn "Not signed in to 1Password."
        echo
        echo "Please sign in to your 1Password account:"
        
        if ! op signin; then
            log_error "Failed to sign in to 1Password."
            exit 1
        fi
    else
        log_info "✓ Signed in to 1Password"
    fi
}

# Create or verify HomeLab vault
ensure_vault() {
    log_step "Setting up HomeLab vault..."
    
    if op vault get HomeLab &> /dev/null; then
        log_info "✓ HomeLab vault already exists"
    else
        log_create "Creating HomeLab vault..."
        
        if op vault create HomeLab &> /dev/null; then
            log_info "✓ HomeLab vault created successfully"
        else
            log_error "Failed to create HomeLab vault"
            exit 1
        fi
    fi
}

# Generate secure password
generate_password() {
    local length="${1:-32}"
    openssl rand -base64 "$length" | tr -d '\n'
}

# Generate secure hex secret
generate_secret() {
    local length="${1:-32}"
    openssl rand -hex "$length"
}

# Generate API key (UUID format)
generate_api_key() {
    uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-'
}

# Create or update a secret in 1Password
create_or_update_secret() {
    local title="$1"
    local field="$2"
    local value="$3"
    local description="${4:-}"
    local update_existing="${5:-false}"
    
    # Check if item already exists
    if op item get "$title" --vault=HomeLab &> /dev/null; then
        if [ "$update_existing" = "true" ]; then
            log_warn "Item '$title' exists, updating field '$field'..."
            
            if op item edit "$title" --vault=HomeLab "$field=$value" &> /dev/null; then
                log_info "✓ Updated $title/$field"
            else
                log_error "Failed to update $title/$field"
                return 1
            fi
        else
            log_info "✓ $title already exists (skipping)"
        fi
    else
        log_create "Creating $title..."
        
        # Create new item with the field
        if op item create \
            --vault=HomeLab \
            --category=Password \
            --title="$title" \
            "$field=$value" \
            ${description:+notes="$description"} &> /dev/null; then
            log_info "✓ Created $title with field '$field'"
        else
            log_error "Failed to create $title"
            return 1
        fi
    fi
}

# Setup core secrets
setup_core_secrets() {
    log_step "Setting up core authentication secrets..."
    
    # Redis password (for future use)
    local redis_password=$(generate_password 32)
    create_or_update_secret \
        "FalkorDB/Core" \
        "redis-password" \
        "$redis_password" \
        "Redis AUTH password for FalkorDB (future use)"
    
    # NextAuth secret
    local nextauth_secret=$(generate_secret 32)
    create_or_update_secret \
        "FalkorDB/Core" \
        "nextauth-secret" \
        "$nextauth_secret" \
        "NextAuth.js secret for session encryption"
}

# Setup integration secrets (placeholders)
setup_integration_secrets() {
    log_step "Setting up integration secret placeholders..."
    
    # Graphiti API key placeholder
    create_or_update_secret \
        "FalkorDB/Integration" \
        "graphiti-api-key" \
        "YOUR-GRAPHITI-API-KEY-HERE" \
        "Replace with your actual Graphiti API key"
    
    # OpenAI API key placeholder
    create_or_update_secret \
        "FalkorDB/Integration" \
        "openai-api-key" \
        "sk-YOUR-OPENAI-API-KEY-HERE" \
        "Replace with your actual OpenAI API key"
    
    log_warn "Integration API keys are placeholders - update them with actual values:"
    echo "  op item edit FalkorDB/Integration --vault=HomeLab"
}

# Setup OAuth secrets (placeholders)
setup_oauth_secrets() {
    log_step "Setting up OAuth secret placeholders..."
    
    # GitHub OAuth
    create_or_update_secret \
        "FalkorDB/OAuth" \
        "github-client-secret" \
        "YOUR-GITHUB-CLIENT-SECRET" \
        "GitHub OAuth app client secret (future feature)"
    
    # Google OAuth
    create_or_update_secret \
        "FalkorDB/OAuth" \
        "google-client-secret" \
        "YOUR-GOOGLE-CLIENT-SECRET" \
        "Google OAuth app client secret (future feature)"
}

# Verify setup
verify_setup() {
    log_step "Verifying vault setup..."
    
    local all_good=true
    local required_items=(
        "FalkorDB/Core"
        "FalkorDB/Integration"
        "FalkorDB/OAuth"
    )
    
    for item in "${required_items[@]}"; do
        if op item get "$item" --vault=HomeLab &> /dev/null; then
            echo -e "  ${GREEN}✓${NC} $item exists"
        else
            echo -e "  ${RED}✗${NC} $item missing"
            all_good=false
        fi
    done
    
    if [ "$all_good" = "true" ]; then
        log_info "✓ All required items are configured"
    else
        log_error "Some items are missing. Please check the setup."
        exit 1
    fi
}

# Show next steps
show_next_steps() {
    echo
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}        FalkorDB 1Password Setup Complete           ${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo
    echo "✅ HomeLab vault is configured with FalkorDB secrets"
    echo
    echo "Next steps:"
    echo
    echo "1. Deploy FalkorDB with secrets:"
    echo "   ${GREEN}make up-secure${NC}"
    echo
    echo "2. Update API keys (if using integrations):"
    echo "   ${YELLOW}op item edit FalkorDB/Integration --vault=HomeLab${NC}"
    echo
    echo "3. View your secrets:"
    echo "   op item get FalkorDB/Core --vault=HomeLab"
    echo "   op item get FalkorDB/Integration --vault=HomeLab"
    echo "   op item get FalkorDB/OAuth --vault=HomeLab"
    echo
    echo "4. Standard deployment (without secrets):"
    echo "   ${GREEN}make up${NC}"
    echo
    echo -e "${CYAN}Tip: Use 'make up' for development, 'make up-secure' for production${NC}"
    echo
}

# Interactive mode check
interactive_mode() {
    if [ "${1:-}" = "--non-interactive" ] || [ "${1:-}" = "-n" ]; then
        return 1
    fi
    return 0
}

# Main execution
main() {
    echo
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}         FalkorDB 1Password Vault Setup             ${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo
    
    check_prerequisites
    check_1password_auth
    ensure_vault
    
    # Ask user if they want to create secrets
    if interactive_mode "$@"; then
        echo
        read -p "Do you want to create/update FalkorDB secrets? [y/N]: " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            setup_core_secrets
            setup_integration_secrets
            setup_oauth_secrets
        else
            log_info "Skipping secret creation (vault verified only)"
        fi
    else
        # Non-interactive mode: create all secrets
        setup_core_secrets
        setup_integration_secrets
        setup_oauth_secrets
    fi
    
    verify_setup
    show_next_steps
}

# Run main function
main "$@"