# Makefile for FalkorDB-Graphiti Test Suite
# Usage: make [target]

# Variables
PYTHON := python3
VENV := venv
PYTEST := pytest
TEST_DIR := tests
COVERAGE_DIR := htmlcov

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help message
	@echo "$(BLUE)FalkorDB-Graphiti Test Suite$(NC)"
	@echo "$(BLUE)=============================$(NC)"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make test           # Run all tests"
	@echo "  make test-quick     # Run quick smoke tests"
	@echo "  make coverage       # Run tests with coverage"
	@echo "  make docker-up      # Start FalkorDB container"

# Environment setup
.PHONY: venv
venv: ## Create virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Creating virtual environment...$(NC)"; \
		$(PYTHON) -m venv $(VENV); \
		. $(VENV)/bin/activate && pip install --upgrade pip; \
		. $(VENV)/bin/activate && pip install -r $(TEST_DIR)/requirements.txt; \
		echo "$(GREEN)✅ Virtual environment created$(NC)"; \
	else \
		echo "$(GREEN)✅ Virtual environment already exists$(NC)"; \
	fi

.PHONY: install
install: venv ## Install test dependencies
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	@. $(VENV)/bin/activate && pip install -r $(TEST_DIR)/requirements.txt
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

.PHONY: clean
clean: ## Clean test artifacts
	@echo "$(YELLOW)Cleaning test artifacts...$(NC)"
	@rm -rf $(COVERAGE_DIR)
	@rm -rf $(TEST_DIR)/.pytest_cache
	@rm -rf $(TEST_DIR)/__pycache__
	@rm -rf $(TEST_DIR)/**/__pycache__
	@rm -rf $(TEST_DIR)/.coverage
	@rm -rf $(TEST_DIR)/test_results/*.txt
	@find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)✅ Cleaned$(NC)"

# Docker management
.PHONY: docker-up
docker-up: ## Start FalkorDB container
	@echo "$(YELLOW)Starting FalkorDB...$(NC)"
	@docker compose up -d
	@sleep 2
	@if docker exec falkordb redis-cli ping > /dev/null 2>&1; then \
		echo "$(GREEN)✅ FalkorDB is running$(NC)"; \
	else \
		echo "$(RED)❌ FalkorDB failed to start$(NC)"; \
		exit 1; \
	fi

.PHONY: docker-down
docker-down: ## Stop FalkorDB container
	@echo "$(YELLOW)Stopping FalkorDB...$(NC)"
	@docker compose down
	@echo "$(GREEN)✅ FalkorDB stopped$(NC)"

.PHONY: docker-logs
docker-logs: ## Show FalkorDB logs
	@docker compose logs -f falkordb

.PHONY: docker-status
docker-status: ## Check FalkorDB status
	@if docker exec falkordb redis-cli ping > /dev/null 2>&1; then \
		echo "$(GREEN)✅ FalkorDB is running$(NC)"; \
		docker ps | grep falkordb; \
	else \
		echo "$(RED)❌ FalkorDB is not running$(NC)"; \
	fi

# Test targets
.PHONY: test
test: venv docker-status ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) $(TEST_DIR)/ -v --asyncio-mode=auto --tb=short --durations=10

.PHONY: test-quick
test-quick: venv docker-status ## Run quick smoke tests
	@echo "$(BLUE)Running quick smoke tests...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) \
		$(TEST_DIR)/test_basic_connection.py \
		$(TEST_DIR)/test_graphiti_simple.py \
		-v --asyncio-mode=auto

.PHONY: test-basic
test-basic: venv docker-status ## Run basic connectivity test
	@echo "$(BLUE)Running basic connectivity test...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) $(TEST_DIR)/test_basic_connection.py -v --asyncio-mode=auto

.PHONY: test-integration
test-integration: venv docker-status ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) $(TEST_DIR)/test_*_int.py -v --asyncio-mode=auto --tb=short

.PHONY: test-regression
test-regression: venv docker-status ## Run regression tests
	@echo "$(BLUE)Running regression tests...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) \
		$(TEST_DIR)/test_v*.py \
		$(TEST_DIR)/test_*regression*.py \
		$(TEST_DIR)/test_group_id*.py \
		-v --asyncio-mode=auto --tb=short

.PHONY: test-custom
test-custom: venv docker-status ## Run custom entity tests
	@echo "$(BLUE)Running custom entity tests...$(NC)"
	@echo "$(YELLOW)Note: These may fail due to known group_id issue$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) \
		$(TEST_DIR)/test_custom_entities*.py \
		$(TEST_DIR)/test_falkordb_gaps.py \
		$(TEST_DIR)/test_workaround*.py \
		-v --asyncio-mode=auto --tb=short

.PHONY: test-watch
test-watch: venv ## Run tests in watch mode
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) $(TEST_DIR)/ --asyncio-mode=auto --tb=short -f

.PHONY: test-verbose
test-verbose: venv docker-status ## Run tests with verbose output
	@echo "$(BLUE)Running tests with verbose output...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) $(TEST_DIR)/ -vvv -s --asyncio-mode=auto

.PHONY: test-failed
test-failed: venv ## Run only previously failed tests
	@echo "$(BLUE)Running previously failed tests...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) $(TEST_DIR)/ --lf --asyncio-mode=auto

# Coverage targets
.PHONY: coverage
coverage: venv docker-status ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@. $(VENV)/bin/activate && $(PYTEST) $(TEST_DIR)/ \
		--cov=$(TEST_DIR) \
		--cov-report=html \
		--cov-report=term \
		--asyncio-mode=auto
	@echo "$(GREEN)✅ Coverage report generated$(NC)"
	@echo "   HTML report: $(COVERAGE_DIR)/index.html"
	@echo "   Run 'make coverage-open' to view"

.PHONY: coverage-open
coverage-open: ## Open coverage report in browser
	@if [ -d "$(COVERAGE_DIR)" ]; then \
		open $(COVERAGE_DIR)/index.html 2>/dev/null || xdg-open $(COVERAGE_DIR)/index.html 2>/dev/null || echo "Please open $(COVERAGE_DIR)/index.html manually"; \
	else \
		echo "$(RED)No coverage report found. Run 'make coverage' first$(NC)"; \
	fi

# Monitoring
.PHONY: monitor
monitor: ## Run monitoring dashboard
	@./scripts/monitor.sh

.PHONY: backup
backup: ## Create FalkorDB backup
	@./scripts/backup.sh

# Development helpers
.PHONY: shell
shell: venv ## Open Python shell with test environment
	@. $(VENV)/bin/activate && python

.PHONY: lint
lint: venv ## Run linting checks
	@echo "$(BLUE)Running linting checks...$(NC)"
	@. $(VENV)/bin/activate && pip install ruff > /dev/null 2>&1 || true
	@. $(VENV)/bin/activate && ruff check $(TEST_DIR)/ || echo "$(YELLOW)Install ruff for linting: pip install ruff$(NC)"

.PHONY: format
format: venv ## Format test code
	@echo "$(BLUE)Formatting code...$(NC)"
	@. $(VENV)/bin/activate && pip install black > /dev/null 2>&1 || true
	@. $(VENV)/bin/activate && black $(TEST_DIR)/ || echo "$(YELLOW)Install black for formatting: pip install black$(NC)"

# GitHub issue
.PHONY: issue-status
issue-status: ## Check GitHub issue #841 status
	@echo "$(BLUE)Checking issue status...$(NC)"
	@gh issue view 841 --repo getzep/graphiti 2>/dev/null || echo "$(YELLOW)GitHub CLI not configured or issue not accessible$(NC)"

# Combined workflows
.PHONY: ci
ci: clean install lint test ## Run CI pipeline (clean, install, lint, test)
	@echo "$(GREEN)✅ CI pipeline completed$(NC)"

.PHONY: all
all: docker-up test coverage ## Run everything (start docker, run tests, generate coverage)
	@echo "$(GREEN)✅ All tasks completed$(NC)"

.PHONY: reset
reset: docker-down clean docker-up ## Reset environment (stop docker, clean, start docker)
	@echo "$(GREEN)✅ Environment reset$(NC)"