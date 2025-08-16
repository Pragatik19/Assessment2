"""
Configuration module for the Automated System Setup Tool.
Contains settings, constants, and environment variable management.
"""

import os
import logging
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "system_setup.db"
PERMISSIONS_PATH = BASE_DIR / "permissions.xlsx"
LOG_PATH = BASE_DIR / "logs"

# Create logs directory
LOG_PATH.mkdir(exist_ok=True)

# Database configuration
DATABASE_CONFIG = {
    "path": str(DB_PATH),
    "timeout": 30,
    "check_same_thread": False
}

# LLM Configuration
LLM_CONFIG = {
    "model_name": "mixtral-8x7b-32768",
    "temperature": 0.1,
    "max_tokens": 1024,
    "timeout": 60
}

# Installation configuration
INSTALLATION_CONFIG = {
    "timeout": 300,  # 5 minutes
    "max_retries": 2,
    "safe_packages": {
        "numpy", "pandas", "requests", "matplotlib", "seaborn", 
        "scikit-learn", "scipy", "pillow", "click", "flask",
        "django", "fastapi", "streamlit", "jupyter", "ipython"
    },
    "blocked_packages": {
        "os", "sys", "subprocess", "importlib", "exec", "eval"
    }
}

# Streamlit configuration
STREAMLIT_CONFIG = {
    "page_title": "Automated System Setup Tool",
    "page_icon": "🔧",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": str(LOG_PATH / "app.log"),
            "mode": "a"
        },
        "error_file": {
            "class": "logging.FileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": str(LOG_PATH / "error.log"),
            "mode": "a"
        }
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "error": {
            "handlers": ["error_file"],
            "level": "ERROR",
            "propagate": False
        }
    }
}

# Security configuration
SECURITY_CONFIG = {
    "max_login_attempts": 5,
    "session_timeout": 3600,  # 1 hour
    "password_min_length": 8,
    "require_api_key": True
}

# Feature flags
FEATURE_FLAGS = {
    "enable_version_checking": True,
    "enable_package_validation": True,
    "enable_installation_logging": True,
    "enable_permission_inheritance": True,
    "enable_dry_run_mode": False
}

def get_environment_config() -> Dict[str, Any]:
    """Get configuration from environment variables."""
    return {
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "debug_mode": os.getenv("DEBUG", "false").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        "database_url": os.getenv("DATABASE_URL", str(DB_PATH)),
        "permissions_file": os.getenv("PERMISSIONS_FILE", str(PERMISSIONS_PATH))
    }

def setup_logging():
    """Setup logging configuration."""
    import logging.config
    
    # Create log directory if it doesn't exist
    LOG_PATH.mkdir(exist_ok=True)
    
    # Apply logging configuration
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Set log level from environment
    env_config = get_environment_config()
    log_level = getattr(logging, env_config["log_level"], logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    return logging.getLogger(__name__)

def validate_configuration() -> bool:
    """Validate that all required configuration is present."""
    errors = []
    
    # Check if database directory is writable
    try:
        test_file = DB_PATH.parent / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        errors.append(f"Database directory not writable: {e}")
    
    # Check if logs directory is writable
    try:
        test_file = LOG_PATH / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        errors.append(f"Logs directory not writable: {e}")
    
    if errors:
        logger = logging.getLogger(__name__)
        for error in errors:
            logger.error(error)
        return False
    
    return True

# Initialize logging
logger = setup_logging()

if __name__ == "__main__":
    print("Configuration loaded successfully!")
    print(f"Database path: {DB_PATH}")
    print(f"Permissions path: {PERMISSIONS_PATH}")
    print(f"Logs path: {LOG_PATH}")
    
    env_config = get_environment_config()
    print(f"Environment config: {env_config}")
    
    if validate_configuration():
        print("✅ Configuration validation passed")
    else:
        print("❌ Configuration validation failed")
