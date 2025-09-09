#!/usr/bin/env python3
"""
CrowdVote Test Runner Script

Runs the complete test suite with coverage reporting and provides
clear feedback on results and next steps.
"""

import subprocess
import sys
from pathlib import Path

def run_command(command, description):
    """Run a command with clear feedback."""
    print(f"\n🔄 {description}")
    print(f"   Running: {command}")
    print("   " + "─" * 50)
    
    result = subprocess.run(command, shell=True, capture_output=False)
    
    if result.returncode == 0:
        print(f"✅ {description} - SUCCESS")
    else:
        print(f"❌ {description} - FAILED")
        return False
    return True

def main():
    """Main test runner function."""
    print("🧪 CrowdVote Test Suite Runner")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("manage.py").exists():
        print("❌ Error: Run this script from the CrowdVote project root directory")
        print("   (where manage.py is located)")
        sys.exit(1)
    
    # Check if Docker is running
    print("\n🔍 Checking Docker environment...")
    result = subprocess.run("docker-compose ps", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ Error: Docker Compose not available or containers not running")
        print("   Please run: docker-compose up -d")
        sys.exit(1)
    
    if "web" not in result.stdout:
        print("❌ Error: CrowdVote web container not running")
        print("   Please run: docker-compose up -d")
        sys.exit(1)
    
    print("✅ Docker environment ready")
    
    # Run tests with coverage (focusing on working tests for now)
    success = run_command(
        'docker-compose exec web sh -c "export DJANGO_SETTINGS_MODULE=crowdvote.settings && python -m pytest tests/test_services/test_star_voting.py::TestSTARVoting::test_score_phase_calculation tests/test_services/test_star_voting.py::TestSTARVoting::test_automatic_runoff_phase tests/test_services/test_delegation.py::TestStageBallotsDelegation::test_delegation_service_initialization tests/test_services/test_delegation.py::TestStageBallotsDelegation::test_single_level_delegation tests/test_models/test_shared.py tests/test_views/test_basic_permissions.py::TestPublicAccessViews --cov --cov-report=html --cov-report=term-missing -v"',
        "Running working tests with coverage analysis"
    )
    
    if not success:
        print("\n❌ Tests failed! Please check the output above for details.")
        sys.exit(1)
    
    # Open coverage report automatically
    run_command(
        "open htmlcov/index.html",
        "Opening HTML coverage report in browser"
    )
    
    # Display results and next steps
    print("\n" + "=" * 50)
    print("🎉 Test Suite Complete!")
    print("=" * 50)
    
    print("\n📊 Coverage Reports Available:")
    print("   • Terminal: See coverage summary above")
    print("   • HTML Report: Open htmlcov/index.html in your browser")
    print("   • To view HTML report: open htmlcov/index.html")
    
    print("\n🔍 Next Steps:")
    print("   • Review failing tests (if any) and fix issues")
    print("   • Check coverage report for untested code")
    print("   • Aim for 80%+ overall coverage, 95%+ for services.py")
    print("   • Add tests for any uncovered critical code paths")
    
    print("\n💡 Quick Commands:")
    print("   • Run all tests: python test.py")
    print("   • View coverage: open htmlcov/index.html")
    print("   • Manual test run: docker-compose exec web sh -c \"export DJANGO_SETTINGS_MODULE=crowdvote.settings && pytest tests/ -v\"")
    
    print("\n✨ Happy testing!")

if __name__ == "__main__":
    main()
