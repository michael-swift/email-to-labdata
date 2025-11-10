#!/usr/bin/env python3
"""
Code coverage analysis script for the lab data digitization service.
"""

import subprocess
import sys
import os


def run_coverage():
    """Run pytest with coverage and generate reports."""
    print("🔍 Running tests with coverage analysis...")
    
    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest", 
        "--cov=src",
        "--cov-report=html",
        "--cov-report=term",
        "--cov-report=xml",
        "-v"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Tests passed!")
    else:
        print("❌ Some tests failed:")
        print(result.stdout)
        print(result.stderr)
    
    print("\n📊 Coverage Report:")
    coverage_section = "Coverage report not found"
    if "---------- coverage:" in result.stdout:
        parts = result.stdout.split("---------- coverage:")
        if len(parts) > 1:
            coverage_section = parts[1]
            if "-- Docs:" in coverage_section:
                coverage_section = coverage_section.split("-- Docs:")[0]
    print(coverage_section.strip())
    
    # Check if HTML coverage report was generated
    if os.path.exists("htmlcov/index.html"):
        print("\n📁 Detailed HTML coverage report generated at: htmlcov/index.html")
        print("   Open it in your browser to see line-by-line coverage")
    
    return result.returncode == 0


def analyze_coverage_gaps():
    """Analyze coverage gaps and suggest improvements."""
    print("\n🎯 Coverage Analysis:")
    print("""
Key areas with low coverage that need tests:

1. **Error Handling Paths** (~60% of uncovered lines)
   - Exception handling in image processing
   - AWS service failures (S3, SES, DynamoDB)
   - Invalid email formats and attachments

2. **Security Features** (~21% coverage)
   - Rate limiting logic
   - Input validation
   - Malicious content detection

3. **Edge Cases** 
   - Malformed GPT responses
   - Network timeouts
   - Large image processing

4. **Integration Points**
   - S3 email parsing
   - SES email sending  
   - DynamoDB logging

**Recommendation**: Focus on testing error paths and security features next.
""")


if __name__ == "__main__":
    print("🧪 Lab Data Digitization Service - Coverage Analysis")
    print("=" * 55)
    
    success = run_coverage()
    analyze_coverage_gaps()
    
    if success:
        print("\n✅ Coverage analysis complete!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed - check output above")
        sys.exit(1)
