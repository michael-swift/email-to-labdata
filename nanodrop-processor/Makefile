# Nanodrop Processor - Development Workflow
# Usage: make <target>

.PHONY: help dev-test prod-deploy accuracy-check logs live-test debug-last tail-logs

# Default target
help:
	@echo "🧬 Nanodrop Processor - Available Commands:"
	@echo ""
	@echo "  📧 Quick Testing:"
	@echo "    make dev-test      - Deploy to dev + send test email + check results"
	@echo "    make live-test     - Interactive testing loop"
	@echo "    make test-suite    - Test all instrument types"
	@echo ""
	@echo "  🚀 Deployment:"
	@echo "    make prod-deploy   - Deploy to production (with safety checks)"
	@echo "    make dev-deploy    - Deploy to development only"
	@echo ""
	@echo "  📊 Analysis:"
	@echo "    make accuracy-check - Check latest extraction accuracy"
	@echo "    make debug-last     - Download & analyze last processed request"
	@echo "    make monitor        - Show system health and metrics"
	@echo ""
	@echo "  📋 Logs:"
	@echo "    make logs          - Show recent logs from both environments"
	@echo "    make tail-logs     - Live log streaming"
	@echo "    make dev-logs      - Show dev environment logs only"
	@echo "    make prod-logs     - Show prod environment logs only"
	@echo ""
	@echo "  🧹 Maintenance:"
	@echo "    make clean         - Clean up temporary files"
	@echo "    make status        - Show git status and AWS resources"

# Quick development testing workflow
dev-test:
	@echo "🧪 Starting dev testing workflow..."
	@echo "1️⃣  Deploying to development environment..."
	./deploy/deploy_lambda_env.sh dev
	@echo "2️⃣  Sending test email..."
	sleep 10
	python scripts/send_test_email.py --dev
	@echo "3️⃣  Waiting for processing (60 seconds)..."
	sleep 60
	@echo "4️⃣  Checking results..."
	-python scripts/check_logs.py --dev --last-run
	@echo "✅ Dev test complete!"

# Production deployment with safety checks
prod-deploy:
	@echo "🚀 Production deployment with safety checks..."
	@echo "⚠️  WARNING: This will deploy to PRODUCTION!"
	@read -p "Continue? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "1️⃣  Running dev tests first..."
	make dev-test
	@echo "2️⃣  Dev tests passed. Deploying to production..."
	./deploy/deploy_lambda_env.sh prod
	@echo "✅ Production deployment complete!"

# Development deploy only
dev-deploy:
	@echo "🧪 Deploying to development environment..."
	./deploy/deploy_lambda_env.sh dev

# Check accuracy of latest extractions
accuracy-check:
	@echo "📊 Checking extraction accuracy..."
	python scripts/download_latest_data.py
	python scripts/accuracy_checker.py
	@echo "✅ Accuracy check complete!"

# Download and analyze last processed request
debug-last:
	@echo "🔍 Downloading latest processed request..."
	python scripts/download_latest_data.py --latest
	python scripts/accuracy_checker.py
	python scripts/analyze_request.py
	@echo "✅ Debug analysis complete!"

# Interactive testing loop
live-test:
	@echo "🔄 Starting interactive testing loop..."
	python scripts/live_test.py

# Test all instrument types
test-suite:
	@echo "🧪 Running comprehensive test suite..."
	python scripts/test_email_pipeline.py --env dev
	@echo "✅ Test suite complete!"

# Show recent logs from both environments
logs:
	@echo "📋 Recent logs from both environments:"
	@echo ""
	@echo "🧪 DEVELOPMENT LOGS:"
	python scripts/check_logs.py --dev --recent
	@echo ""
	@echo "🚀 PRODUCTION LOGS:"  
	python scripts/check_logs.py --prod --recent

# Live log streaming
tail-logs:
	@echo "📡 Streaming live logs (Ctrl+C to stop)..."
	python scripts/tail_logs.py

# Development logs only
dev-logs:
	@echo "📋 Development environment logs:"
	python scripts/check_logs.py --dev --recent

# Production logs only  
prod-logs:
	@echo "📋 Production environment logs:"
	python scripts/check_logs.py --prod --recent

# System monitoring
monitor:
	@echo "📊 System health and metrics:"
	python scripts/monitor.py

# Clean up temporary files
clean:
	@echo "🧹 Cleaning up temporary files..."
	rm -f *.json *.csv *.tmp
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".DS_Store" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete!"

# Show system status
status:
	@echo "📊 System Status:"
	@echo ""
	@echo "📁 Git Status:"
	git status --short
	@echo ""
	@echo "☁️  AWS Lambda Functions:"
	aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `nanodrop`)].FunctionName' --output table
	@echo ""
	@echo "📧 SES Rules:"
	aws ses describe-active-receipt-rule-set --query 'Rules[*].[Name,Recipients[0]]' --output table