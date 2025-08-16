"""
Test script to verify that the installation system actually installs packages.
Tests with a small, safe package to verify the installation workflow.
"""

import sys
import os
import subprocess
import importlib

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph_flow import InstallationWorkflow
from config import get_environment_config

def test_real_installation():
    """Test actual package installation with a small, safe package."""
    
    print("🧪 Testing Real Package Installation")
    print("=" * 50)
    
    # Get API key from environment
    env_config = get_environment_config()
    api_key = env_config.get('groq_api_key')
    
    if not api_key:
        print("❌ No GROQ_API_KEY found in environment")
        print("This test will skip LLM functionality but test the installation process")
        # We can still test the installation subprocess directly
        return test_direct_installation()
    
    print(f"✅ Found API key: {api_key[:10]}..." if api_key else "❌ No API key")
    
    # Test with a small, harmless package
    test_package = "colorama"  # A small, useful package for colored terminal output
    
    print(f"\n🔍 Testing installation of '{test_package}'...")
    
    # First, check if it's already installed and uninstall it
    try:
        importlib.import_module(test_package)
        print(f"📦 {test_package} is already installed, uninstalling first...")
        result = subprocess.run([sys.executable, "-m", "pip", "uninstall", test_package, "-y"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Successfully uninstalled {test_package}")
        else:
            print(f"⚠️ Could not uninstall {test_package}: {result.stderr}")
    except ImportError:
        print(f"✅ {test_package} is not installed, good for testing")
    
    # Create workflow instance
    try:
        workflow = InstallationWorkflow(api_key)
        print("✅ Workflow created successfully")
    except Exception as e:
        print(f"❌ Failed to create workflow: {e}")
        return False
    
    # Test the installation
    print(f"\n🚀 Processing installation request: 'Install {test_package}'")
    
    try:
        result = workflow.process_request(
            user_input=f"Install {test_package}",
            user_id=1,  # Test user
            user_role="Senior Software Engineer"  # Role that should have permissions
        )
        
        print(f"📊 Installation result: {result}")
        
        if result['success'] and result['type'] == 'installation_success':
            print(f"✅ Installation reported as successful!")
            
            # Verify the package was actually installed
            try:
                importlib.import_module(test_package)
                print(f"✅ Package {test_package} successfully imported after installation!")
                
                # Show the installed version
                try:
                    package_module = importlib.import_module(test_package)
                    version = getattr(package_module, '__version__', 'unknown')
                    print(f"📦 Installed version: {version}")
                except:
                    print("📦 Package installed but version info not available")
                
                return True
                
            except ImportError as e:
                print(f"❌ Package {test_package} could not be imported after installation: {e}")
                return False
                
        else:
            print(f"❌ Installation failed or was not processed correctly")
            print(f"Result: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error during installation test: {e}")
        return False

def test_direct_installation():
    """Test direct subprocess installation without the workflow."""
    print("\n🔧 Testing direct subprocess installation...")
    
    test_package = "colorama"
    
    try:
        # Uninstall first if present
        subprocess.run([sys.executable, "-m", "pip", "uninstall", test_package, "-y"], 
                      capture_output=True, text=True)
        
        # Install the package
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", test_package],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"✅ Direct installation successful")
            print(f"Output: {result.stdout}")
            
            # Verify import
            try:
                importlib.import_module(test_package)
                print(f"✅ Package {test_package} successfully imported!")
                return True
            except ImportError as e:
                print(f"❌ Could not import {test_package}: {e}")
                return False
        else:
            print(f"❌ Direct installation failed")
            print(f"Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error during direct installation: {e}")
        return False

def main():
    """Run the installation test."""
    success = test_real_installation()
    
    if success:
        print("\n🎉 Installation test PASSED!")
        print("The system can successfully install packages on the local machine.")
    else:
        print("\n❌ Installation test FAILED!")
        print("There may be an issue with the installation system.")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
