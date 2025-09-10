#!/usr/bin/env python3
"""
CrowdVote Test Runner Script

Runs the complete test suite with coverage reporting and provides
clear test results summary.
"""

import subprocess
import sys
import re
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

def extract_test_results():
    """Extract test results from the pytest output."""
    try:
        # Run pytest with quiet output to capture results
        result = subprocess.run(
            'docker-compose exec web sh -c "export DJANGO_SETTINGS_MODULE=crowdvote.settings && python -m pytest tests/ --cov --cov-report=html --tb=no -q"',
            shell=True, 
            capture_output=True, 
            text=True
        )
        
        # Look for the results line like "137 failed, 322 passed, 1893 warnings"
        lines = result.stdout.split('\n')
        for line in lines:
            if 'failed' in line and 'passed' in line:
                # Parse the results
                failed_match = re.search(r'(\d+) failed', line)
                passed_match = re.search(r'(\d+) passed', line)
                
                if failed_match and passed_match:
                    failed = int(failed_match.group(1))
                    passed = int(passed_match.group(1))
                    total = failed + passed
                    success_rate = (passed / total * 100) if total > 0 else 0
                    
                    return failed, passed, total, success_rate
        
        return None, None, None, None
        
    except Exception as e:
        print(f"   Note: Could not parse test results automatically: {e}")
        return None, None, None, None

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
    
    # Run complete test suite with coverage
    run_command(
        'docker-compose exec web sh -c "export DJANGO_SETTINGS_MODULE=crowdvote.settings && python -m pytest tests/ --cov --cov-report=html --cov-report=term-missing --tb=short"',
        "Running complete test suite with coverage analysis"
    )
    
    # Extract and display test results
    print("\n📊 Extracting test results...")
    failed, passed, total, success_rate = extract_test_results()
    
    # Open coverage report automatically
    run_command(
        "open htmlcov/index.html",
        "Opening HTML coverage report in browser"
    )
    
    # Display results summary
    print("\n" + "=" * 50)
    print("🎉 Test Suite Complete!")
    print("=" * 50)
    
    if failed is not None and passed is not None:
        print(f"\n📈 Test Results Summary:")
        print(f"   • Total Tests: {total}")
        print(f"   • Passing: {passed} ✅")
        print(f"   • Failing: {failed} ❌") 
        print(f"   • Success Rate: {success_rate:.1f}%")
    else:
        print("\n📈 Test Results: See detailed output above")
    
    print(f"\n📊 Coverage Report:")
    print(f"   • HTML Report: htmlcov/index.html (opened in browser)")
    print(f"   • Terminal: See coverage summary above")

if __name__ == "__main__":
    main()
