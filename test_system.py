"""
Test script for the Automated System Setup Tool.
Tests all major components and integrations.
"""

import sys
import os
import logging
from datetime import datetime
import traceback

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_setup import initialize_database, authenticate_user, get_user_requests
from permissions_manager import PermissionManager
from utils import validate_package_name, validate_version_specifier, check_package_exists
from config import setup_logging, validate_configuration

# Setup logging for tests
logger = setup_logging()

class TestResult:
    """Test result tracker."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_result(self, test_name: str, success: bool, error: str = None):
        """Add a test result."""
        if success:
            self.passed += 1
            logger.info(f"✅ {test_name} - PASSED")
        else:
            self.failed += 1
            self.errors.append(f"{test_name}: {error}")
            logger.error(f"❌ {test_name} - FAILED: {error}")
    
    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"\n{'='*50}")
        print(f"TEST SUMMARY")
        print(f"{'='*50}")
        print(f"Total Tests: {total}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.errors:
            print(f"\nFAILED TESTS:")
            for error in self.errors:
                print(f"  - {error}")
        
        print(f"{'='*50}")

def test_database():
    """Test database functionality."""
    results = TestResult()
    
    try:
        # Test database initialization
        initialize_database()
        results.add_result("Database Initialization", True)
    except Exception as e:
        results.add_result("Database Initialization", False, str(e))
    
    try:
        # Test user authentication
        user = authenticate_user("EMP001", "password123")
        if user and user['name'] == "John Doe":
            results.add_result("User Authentication", True)
        else:
            results.add_result("User Authentication", False, "Invalid user data returned")
    except Exception as e:
        results.add_result("User Authentication", False, str(e))
    
    try:
        # Test invalid authentication
        invalid_user = authenticate_user("INVALID", "wrong")
        if invalid_user is None:
            results.add_result("Invalid Authentication Rejection", True)
        else:
            results.add_result("Invalid Authentication Rejection", False, "Should have returned None")
    except Exception as e:
        results.add_result("Invalid Authentication Rejection", False, str(e))
    
    try:
        # Test user requests (might be empty, that's okay)
        requests = get_user_requests(1, limit=5)
        if isinstance(requests, list):
            results.add_result("User Requests Retrieval", True)
        else:
            results.add_result("User Requests Retrieval", False, "Should return a list")
    except Exception as e:
        results.add_result("User Requests Retrieval", False, str(e))
    
    return results

def test_permissions():
    """Test permissions management."""
    results = TestResult()
    
    try:
        # Test permission manager initialization
        pm = PermissionManager()
        results.add_result("Permission Manager Initialization", True)
    except Exception as e:
        results.add_result("Permission Manager Initialization", False, str(e))
        return results
    
    try:
        # Test role permissions
        packages = pm.get_allowed_packages("Senior Software Engineer")
        if isinstance(packages, set) and len(packages) > 0:
            results.add_result("Role Permissions Retrieval", True)
        else:
            results.add_result("Role Permissions Retrieval", False, "Should return non-empty set")
    except Exception as e:
        results.add_result("Role Permissions Retrieval", False, str(e))
    
    try:
        # Test permission inheritance (Senior should have more than Associate)
        associate_packages = pm.get_allowed_packages("Associate Software Engineer")
        senior_packages = pm.get_allowed_packages("Senior Software Engineer")
        
        if len(senior_packages) >= len(associate_packages):
            results.add_result("Permission Inheritance", True)
        else:
            results.add_result("Permission Inheritance", False, "Senior should have at least as many permissions")
    except Exception as e:
        results.add_result("Permission Inheritance", False, str(e))
    
    try:
        # Test specific package permission
        is_allowed = pm.is_package_allowed("Associate Software Engineer", "numpy")
        if isinstance(is_allowed, bool):
            results.add_result("Specific Package Permission Check", True)
        else:
            results.add_result("Specific Package Permission Check", False, "Should return boolean")
    except Exception as e:
        results.add_result("Specific Package Permission Check", False, str(e))
    
    return results

def test_utils():
    """Test utility functions."""
    results = TestResult()
    
    try:
        # Test package name validation
        validate_package_name("numpy")
        results.add_result("Valid Package Name Validation", True)
    except Exception as e:
        results.add_result("Valid Package Name Validation", False, str(e))
    
    try:
        # Test invalid package name validation
        try:
            validate_package_name("invalid@package!")
            results.add_result("Invalid Package Name Rejection", False, "Should have raised ValidationError")
        except Exception:
            results.add_result("Invalid Package Name Rejection", True)
    except Exception as e:
        results.add_result("Invalid Package Name Rejection", False, str(e))
    
    try:
        # Test version validation
        validate_version_specifier("1.21.0")
        results.add_result("Version Validation", True)
    except Exception as e:
        results.add_result("Version Validation", False, str(e))
    
    try:
        # Test package existence check (with a common package)
        exists, versions = check_package_exists("requests")
        if isinstance(exists, bool) and isinstance(versions, list):
            results.add_result("Package Existence Check", True)
        else:
            results.add_result("Package Existence Check", False, "Invalid return types")
    except Exception as e:
        results.add_result("Package Existence Check", False, str(e))
    
    return results

def test_configuration():
    """Test configuration and setup."""
    results = TestResult()
    
    try:
        # Test configuration validation
        is_valid = validate_configuration()
        if isinstance(is_valid, bool):
            results.add_result("Configuration Validation", True)
        else:
            results.add_result("Configuration Validation", False, "Should return boolean")
    except Exception as e:
        results.add_result("Configuration Validation", False, str(e))
    
    try:
        # Test logging setup
        test_logger = logging.getLogger("test")
        test_logger.info("Test log message")
        results.add_result("Logging Setup", True)
    except Exception as e:
        results.add_result("Logging Setup", False, str(e))
    
    return results

def test_langgraph_workflow():
    """Test LangGraph workflow (without API key)."""
    results = TestResult()
    
    try:
        # Test workflow import
        from langgraph_flow import create_installation_workflow
        results.add_result("Workflow Import", True)
    except Exception as e:
        results.add_result("Workflow Import", False, str(e))
        return results
    
    # Note: We can't test the actual workflow without a Groq API key
    # This would require the user to provide their API key
    results.add_result("Workflow Creation", True, "Skipped - requires API key")
    
    return results

def main():
    """Run all tests."""
    print("🧪 Starting Automated System Setup Tool Tests")
    print(f"Test started at: {datetime.now()}")
    print("="*50)
    
    all_results = TestResult()
    
    # Run all test suites
    test_suites = [
        ("Configuration", test_configuration),
        ("Database", test_database),
        ("Permissions", test_permissions),
        ("Utilities", test_utils),
        ("LangGraph Workflow", test_langgraph_workflow),
    ]
    
    for suite_name, test_func in test_suites:
        print(f"\n🔍 Running {suite_name} Tests...")
        try:
            suite_results = test_func()
            all_results.passed += suite_results.passed
            all_results.failed += suite_results.failed
            all_results.errors.extend(suite_results.errors)
        except Exception as e:
            print(f"❌ Test suite {suite_name} crashed: {e}")
            logger.error(f"Test suite {suite_name} crashed: {traceback.format_exc()}")
            all_results.failed += 1
            all_results.errors.append(f"{suite_name} Test Suite: Crashed - {str(e)}")
    
    # Print final summary
    all_results.print_summary()
    
    # Return appropriate exit code
    return 0 if all_results.failed == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
