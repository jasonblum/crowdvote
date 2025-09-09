#!/bin/bash

# CrowdVote Test Runner Script
# Runs the complete test suite with coverage reporting

echo "🧪 CrowdVote Test Suite Runner"
echo "=================================================="

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose not found"
    echo "   Please install Docker and Docker Compose"
    exit 1
fi

# Check if containers are running
echo ""
echo "🔍 Checking Docker environment..."
if ! docker-compose ps | grep -q "web"; then
    echo "❌ Error: CrowdVote web container not running"
    echo "   Please run: docker-compose up -d"
    exit 1
fi

echo "✅ Docker environment ready"

# Run tests with coverage
echo ""
echo "🔄 Running tests with coverage analysis"
echo "   Running: docker-compose exec web pytest --cov --cov-report=html --cov-report=term"
echo "   ──────────────────────────────────────────────────"

if docker-compose exec web pytest --cov --cov-report=html --cov-report=term; then
    echo "✅ Tests completed successfully"
else
    echo "❌ Tests failed! Please check the output above for details."
    exit 1
fi

# Generate additional coverage report
echo ""
echo "🔄 Generating detailed HTML coverage report"
echo "   Running: docker-compose exec web coverage html"
echo "   ──────────────────────────────────────────────────"

docker-compose exec web coverage html

# Display results and next steps
echo ""
echo "=================================================="
echo "🎉 Test Suite Complete!"
echo "=================================================="

echo ""
echo "📊 Coverage Reports Available:"
echo "   • Terminal: See coverage summary above"
echo "   • HTML Report: Open htmlcov/index.html in your browser"

echo ""
echo "🔍 Next Steps:"
echo "   • Review failing tests (if any) and fix issues"
echo "   • Check coverage report for untested code"
echo "   • Aim for 80%+ overall coverage, 95%+ for services.py"

echo ""
echo "💡 Quick Commands:"
echo "   • Run specific tests: docker-compose exec web pytest tests/test_services/ -v"
echo "   • Run with verbose output: docker-compose exec web pytest -v"
echo "   • Check coverage only: docker-compose exec web coverage report"

echo ""
echo "✨ Happy testing!"
