"""
Utility functions for the Automated System Setup Tool.
Contains helpers for validation, error handling, and common operations.
"""

import re
import subprocess
import logging
import functools
import time
from typing import Optional, Dict, Any, List, Callable, Tuple
from datetime import datetime, timedelta
import traceback

from config import INSTALLATION_CONFIG, SECURITY_CONFIG

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

class InstallationError(Exception):
    """Custom exception for installation errors."""
    pass

class PermissionError(Exception):
    """Custom exception for permission errors."""
    pass

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry function execution on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise e
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator

def log_execution_time(func: Callable) -> Callable:
    """Decorator to log function execution time."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"Function {func.__name__} executed successfully in {execution_time:.2f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Function {func.__name__} failed after {execution_time:.2f}s: {e}")
            raise
    return wrapper

def safe_execute(func: Callable, *args, **kwargs) -> Tuple[bool, Any, Optional[str]]:
    """
    Safely execute a function and return success status, result, and error message.
    
    Returns:
        Tuple of (success: bool, result: Any, error_message: Optional[str])
    """
    try:
        result = func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Safe execution failed: {error_msg}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        return False, None, error_msg

def validate_package_name(package_name: str) -> bool:
    """
    Validate package name format and safety.
    
    Args:
        package_name: Name of the package to validate
        
    Returns:
        True if package name is valid and safe
        
    Raises:
        ValidationError: If package name is invalid or unsafe
    """
    if not package_name or not isinstance(package_name, str):
        raise ValidationError("Package name must be a non-empty string")
    
    # Remove version specifiers for validation
    base_name = re.split(r'[=<>!]', package_name)[0].strip()
    
    # Check for blocked packages
    if base_name.lower() in INSTALLATION_CONFIG["blocked_packages"]:
        raise ValidationError(f"Package '{base_name}' is not allowed for security reasons")
    
    # Validate package name format (PEP 508)
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$', base_name):
        raise ValidationError(f"Invalid package name format: '{base_name}'")
    
    # Check length
    if len(base_name) > 100:
        raise ValidationError("Package name too long (max 100 characters)")
    
    logger.debug(f"Package name '{package_name}' validated successfully")
    return True

def validate_version_specifier(version: str) -> bool:
    """
    Validate version specifier format.
    
    Args:
        version: Version string to validate
        
    Returns:
        True if version is valid
        
    Raises:
        ValidationError: If version format is invalid
    """
    if not version or version.lower() == "latest":
        return True
    
    # Simple version validation (semantic versioning)
    version_pattern = r'^(\d+)(\.\d+)*([a-zA-Z]\d*)?$'
    if not re.match(version_pattern, version):
        raise ValidationError(f"Invalid version format: '{version}'")
    
    logger.debug(f"Version '{version}' validated successfully")
    return True

@retry_on_failure(max_retries=2)
@log_execution_time
def check_package_exists(package_name: str) -> Tuple[bool, List[str]]:
    """
    Check if a package exists in PyPI and get available versions.
    
    Args:
        package_name: Name of the package to check
        
    Returns:
        Tuple of (exists: bool, versions: List[str])
    """
    try:
        # Use pip to check package existence
        result = subprocess.run(
            ["pip", "index", "versions", package_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            versions = ["latest"]
            # Try to parse versions from output
            if "Available versions:" in result.stdout:
                version_line = result.stdout.split("Available versions:")[1].split("\n")[0]
                parsed_versions = [v.strip() for v in version_line.split(",")]
                if parsed_versions:
                    versions = parsed_versions[:10]  # Limit to 10 versions
            
            logger.info(f"Package '{package_name}' exists with versions: {versions}")
            return True, versions
        else:
            logger.warning(f"Package '{package_name}' not found in PyPI")
            return False, []
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout checking package '{package_name}'")
        return False, []
    except Exception as e:
        logger.error(f"Error checking package '{package_name}': {e}")
        return False, []

@log_execution_time
def format_error_message(error: Exception, context: str = "") -> str:
    """
    Format error message for user display.
    
    Args:
        error: Exception object
        context: Additional context information
        
    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Common error translations
    error_translations = {
        "FileNotFoundError": "Required file not found",
        "PermissionError": "Insufficient permissions",
        "TimeoutError": "Operation timed out",
        "ConnectionError": "Network connection failed",
        "ValidationError": "Invalid input provided",
        "InstallationError": "Installation failed",
    }
    
    user_friendly_type = error_translations.get(error_type, error_type)
    
    if context:
        return f"{context}: {user_friendly_type} - {error_msg}"
    else:
        return f"{user_friendly_type}: {error_msg}"

def sanitize_input(user_input: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        user_input: Raw user input
        
    Returns:
        Sanitized input string
    """
    if not isinstance(user_input, str):
        return str(user_input)
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[;&|`$()]', '', user_input)
    
    # Limit length
    sanitized = sanitized[:500]
    
    # Strip whitespace
    sanitized = sanitized.strip()
    
    return sanitized

def validate_user_role(role: str) -> bool:
    """
    Validate user role format and value.
    
    Args:
        role: User role string
        
    Returns:
        True if role is valid
        
    Raises:
        ValidationError: If role is invalid
    """
    valid_roles = {
        "Associate Software Engineer",
        "Senior Software Engineer", 
        "Lead Software Engineer",
        "Principal Software Engineer",
        "Staff Software Engineer",
        "Senior Staff Software Engineer"
    }
    
    if role not in valid_roles:
        raise ValidationError(f"Invalid user role: '{role}'")
    
    return True

def create_audit_log_entry(
    user_id: int,
    action: str,
    details: Dict[str, Any],
    success: bool = True
) -> Dict[str, Any]:
    """
    Create a standardized audit log entry.
    
    Args:
        user_id: ID of the user performing the action
        action: Action being performed
        details: Additional details about the action
        success: Whether the action was successful
        
    Returns:
        Audit log entry dictionary
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details,
        "success": success,
        "session_id": f"session_{user_id}_{int(time.time())}"
    }

def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive data in dictionaries for logging.
    
    Args:
        data: Dictionary potentially containing sensitive data
        
    Returns:
        Dictionary with sensitive data masked
    """
    sensitive_keys = {"password", "api_key", "token", "secret", "key"}
    masked_data = data.copy()
    
    for key, value in masked_data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                masked_data[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
            else:
                masked_data[key] = "***"
    
    return masked_data

def get_system_info() -> Dict[str, Any]:
    """
    Get system information for debugging and logging.
    
    Returns:
        Dictionary containing system information
    """
    import platform
    import sys
    
    return {
        "platform": platform.platform(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Test utility functions
    print("Testing utility functions...")
    
    # Test package validation
    try:
        validate_package_name("numpy")
        print("✅ Package validation test passed")
    except ValidationError as e:
        print(f"❌ Package validation test failed: {e}")
    
    # Test version validation
    try:
        validate_version_specifier("1.21.0")
        print("✅ Version validation test passed")
    except ValidationError as e:
        print(f"❌ Version validation test failed: {e}")
    
    # Test system info
    info = get_system_info()
    print(f"✅ System info: {info['platform']}")
    
    print("Utility functions test completed!")
