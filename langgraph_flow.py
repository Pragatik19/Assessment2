"""
LangGraph workflow implementation for automated installation system.
Handles the complete flow from request interpretation to installation execution.
"""

import re
import subprocess
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import os
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from db_setup import log_request, update_request_status
from permissions_manager import PermissionManager

# Configure logging
logger = logging.getLogger(__name__)

class InstallationState(TypedDict):
    """State object for the installation workflow."""
    messages: Annotated[list, add_messages]
    user_id: int
    user_role: str
    user_input: str
    intent: str
    package_name: str
    version: str
    request_id: Optional[int]
    permission_granted: bool
    available_versions: List[str]
    installation_result: Dict[str, Any]
    error_message: Optional[str]

class InstallationWorkflow:
    """LangGraph-based workflow for handling installation requests."""
    
    def __init__(self, groq_api_key: str):
        # Use provided key or fall back to environment
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.llm = ChatGroq(
            groq_api_key=self.groq_api_key,
            model_name="gemma-2-9b-it",
            temperature=0.1
        )
        self.permission_manager = PermissionManager()
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(InstallationState)
        
        # Add nodes
        workflow.add_node("interpret_intent", self.interpret_intent)
        workflow.add_node("log_request", self.log_request_node)
        workflow.add_node("check_permissions", self.check_permissions)
        workflow.add_node("check_versions", self.check_versions)
        workflow.add_node("execute_installation", self.execute_installation)
        workflow.add_node("update_completion", self.update_completion)
        workflow.add_node("handle_denial", self.handle_denial)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point
        workflow.set_entry_point("interpret_intent")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "interpret_intent",
            self.route_after_intent,
            {
                "install": "log_request",
                "not_install": END,
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("log_request", "check_permissions")
        
        workflow.add_conditional_edges(
            "check_permissions",
            self.route_after_permissions,
            {
                "granted": "check_versions",
                "denied": "handle_denial"
            }
        )
        
        workflow.add_conditional_edges(
            "check_versions",
            self.route_after_versions,
            {
                "proceed": "execute_installation",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "execute_installation",
            self.route_after_installation,
            {
                "success": "update_completion",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("update_completion", END)
        workflow.add_edge("handle_denial", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    def interpret_intent(self, state: InstallationState) -> InstallationState:
        """Interpret user intent using LLM."""
        try:
            # First, try simple pattern matching for common install phrases
            user_input_lower = state['user_input'].lower().strip()
            
            # Common install patterns
            install_patterns = [
                r'install\s+([a-zA-Z0-9_-]+)',
                r'please\s+install\s+([a-zA-Z0-9_-]+)',
                r'can\s+you\s+install\s+([a-zA-Z0-9_-]+)',
                r'i\s+need\s+([a-zA-Z0-9_-]+)',
                r'setup\s+([a-zA-Z0-9_-]+)',
                r'add\s+([a-zA-Z0-9_-]+)',
                r'get\s+([a-zA-Z0-9_-]+)',
                r'download\s+([a-zA-Z0-9_-]+)',
                r'pip\s+install\s+([a-zA-Z0-9_-]+)',
                r'conda\s+install\s+([a-zA-Z0-9_-]+)'
            ]
            
            import re
            package_found = None
            for pattern in install_patterns:
                match = re.search(pattern, user_input_lower)
                if match:
                    package_found = match.group(1)
                    break
            
            # If we found a package through pattern matching, it's definitely an install request
            if package_found:
                state["intent"] = "install"
                state["package_name"] = package_found
                state["version"] = None
                
                # Try to extract version if mentioned
                version_patterns = [
                    r'version\s+(\d+\.?\d*\.?\d*)',
                    r'v(\d+\.?\d*\.?\d*)',
                    r'==\s*(\d+\.?\d*\.?\d*)',
                    r'>=\s*(\d+\.?\d*\.?\d*)',
                    r'(\d+\.?\d*\.?\d*)\s*version'
                ]
                
                for version_pattern in version_patterns:
                    version_match = re.search(version_pattern, user_input_lower)
                    if version_match:
                        state["version"] = version_match.group(1)
                        break
                
                logger.info(f"Pattern-matched intent: install {package_found} version {state.get('version', 'latest')}")
                return state
            
            # If no pattern match, fall back to LLM
            prompt = f"""
            Analyze the following user input to determine if it's an installation request:
            
            User input: "{state['user_input']}"
            
            Installation requests include any request to:
            - Install, setup, add, or download a software package
            - Get or obtain a library or tool
            - Use pip, conda, or other package managers
            
            Common phrases that indicate installation:
            - "Install [package]"
            - "Please install [package]"
            - "Can you install [package]"
            - "I need [package]"
            - "Setup [package]"
            - "Add [package]"
            - "Get [package]"
            - "Download [package]"
            
            Respond with JSON format:
            {{
                "intent": "install" or "not_install",
                "package_name": "extracted package name if install intent, else null",
                "version": "specific version if mentioned, else null"
            }}
            
            Examples:
            - "Install numpy" -> {{"intent": "install", "package_name": "numpy", "version": null}}
            - "Please install pandas" -> {{"intent": "install", "package_name": "pandas", "version": null}}
            - "Install TensorFlow 2.13" -> {{"intent": "install", "package_name": "tensorflow", "version": "2.13"}}
            - "What is PyTorch?" -> {{"intent": "not_install", "package_name": null, "version": null}}
            - "How does numpy work?" -> {{"intent": "not_install", "package_name": null, "version": null}}
            """
            
            response = self.llm.invoke(prompt)
            result = json.loads(response.content)
            
            state["intent"] = result["intent"]
            state["package_name"] = result["package_name"]
            state["version"] = result["version"]
            
            logger.info(f"LLM interpreted intent: {state['intent']} for package {state['package_name']}")
            
        except Exception as e:
            logger.error(f"Error interpreting intent: {e}")
            state["intent"] = "error"
            state["error_message"] = f"Failed to interpret request: {str(e)}"
        
        return state
    
    def route_after_intent(self, state: InstallationState) -> str:
        """Route based on interpreted intent."""
        if state["intent"] == "install":
            return "install"
        elif state["intent"] == "error":
            return "error"
        else:
            return "not_install"
    
    def log_request_node(self, state: InstallationState) -> InstallationState:
        """Log the installation request to database."""
        try:
            request_id = log_request(
                user_id=state["user_id"],
                package_name=state["package_name"],
                version=state["version"]
            )
            state["request_id"] = request_id
            logger.info(f"Request logged with ID: {request_id}")
        except Exception as e:
            logger.error(f"Error logging request: {e}")
            state["error_message"] = f"Failed to log request: {str(e)}"
        
        return state
    
    def check_permissions(self, state: InstallationState) -> InstallationState:
        """Check if user has permission to install the package."""
        try:
            is_allowed = self.permission_manager.is_package_allowed(
                state["user_role"],
                state["package_name"]
            )
            state["permission_granted"] = is_allowed
            
            if is_allowed:
                logger.info(f"Permission granted for {state['package_name']} to {state['user_role']}")
            else:
                logger.info(f"Permission denied for {state['package_name']} to {state['user_role']}")
                
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            state["permission_granted"] = False
            state["error_message"] = f"Failed to check permissions: {str(e)}"
        
        return state
    
    def route_after_permissions(self, state: InstallationState) -> str:
        """Route based on permission check result."""
        return "granted" if state["permission_granted"] else "denied"
    
    def check_versions(self, state: InstallationState) -> InstallationState:
        """Check available versions of the package."""
        try:
            # Use pip to check available versions
            result = subprocess.run(
                ["pip", "index", "versions", state["package_name"]],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse available versions (simplified)
                versions = ["latest"]  # Default to latest
                if "Available versions:" in result.stdout:
                    version_line = result.stdout.split("Available versions:")[1].split("\n")[0]
                    versions = [v.strip() for v in version_line.split(",")[:5]]  # Limit to 5 versions
                
                state["available_versions"] = versions
                logger.info(f"Found versions for {state['package_name']}: {versions}")
            else:
                # Package might not exist in PyPI, but we'll try to install anyway
                state["available_versions"] = ["latest"]
                logger.warning(f"Could not fetch versions for {state['package_name']}")
                
        except Exception as e:
            logger.error(f"Error checking versions: {e}")
            state["available_versions"] = ["latest"]
        
        return state
    
    def route_after_versions(self, state: InstallationState) -> str:
        """Route after version check."""
        return "proceed"  # Always proceed for now
    
    def execute_installation(self, state: InstallationState) -> InstallationState:
        """Execute the actual package installation."""
        try:
            package_spec = state["package_name"]
            if state["version"] and state["version"] != "latest":
                package_spec = f"{state['package_name']}=={state['version']}"
            
            logger.info(f"Attempting to install: {package_spec}")
            
            # Use sys.executable to ensure we use the same Python interpreter
            import sys
            
            # Execute pip install using the current Python interpreter
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_spec, "--upgrade"],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=os.getcwd()  # Use current working directory
            )
            
            if result.returncode == 0:
                # Try to verify installation by importing (for Python packages)
                verification_success = self._verify_package_installation(state["package_name"])
                
                state["installation_result"] = {
                    "success": True,
                    "package": package_spec,
                    "output": result.stdout,
                    "error": result.stderr if result.stderr else None,
                    "verified": verification_success,
                    "timestamp": datetime.now().isoformat()
                }
                logger.info(f"Successfully installed {package_spec}")
                logger.info(f"Installation output: {result.stdout}")
                
                if result.stderr:
                    logger.warning(f"Installation warnings: {result.stderr}")
                    
            else:
                state["installation_result"] = {
                    "success": False,
                    "package": package_spec,
                    "error": result.stderr,
                    "output": result.stdout,
                    "timestamp": datetime.now().isoformat()
                }
                state["error_message"] = f"Installation failed: {result.stderr}"
                logger.error(f"Installation failed for {package_spec}")
                logger.error(f"Error output: {result.stderr}")
                logger.error(f"Stdout: {result.stdout}")
                
        except subprocess.TimeoutExpired:
            error_msg = f"Installation timed out for {state['package_name']} after 5 minutes"
            state["error_message"] = error_msg
            state["installation_result"] = {"success": False, "error": error_msg}
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Installation error: {str(e)}"
            state["error_message"] = error_msg
            state["installation_result"] = {"success": False, "error": error_msg}
            logger.error(f"Installation exception: {e}")
        
        return state
    
    def _verify_package_installation(self, package_name: str) -> bool:
        """Verify that a package was successfully installed by trying to import it."""
        try:
            # Common package name mappings
            import_name_mapping = {
                'scikit-learn': 'sklearn',
                'pillow': 'PIL',
                'opencv-python': 'cv2',
                'beautifulsoup4': 'bs4',
                'pyyaml': 'yaml',
                'python-dateutil': 'dateutil',
                'msgpack-python': 'msgpack'
            }
            
            import_name = import_name_mapping.get(package_name.lower(), package_name)
            
            # Try to import the package
            import importlib
            importlib.import_module(import_name)
            logger.info(f"Successfully verified import of {import_name}")
            return True
            
        except ImportError as e:
            logger.warning(f"Could not verify installation of {package_name}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error during package verification: {e}")
            return False
    
    def route_after_installation(self, state: InstallationState) -> str:
        """Route based on installation result."""
        if state["installation_result"]["success"]:
            return "success"
        else:
            return "error"
    
    def update_completion(self, state: InstallationState) -> InstallationState:
        """Update database with successful completion."""
        try:
            if state["request_id"]:
                installed_version = "latest"  # Could be parsed from pip output
                update_request_status(
                    request_id=state["request_id"],
                    status="completed",
                    version=installed_version
                )
            logger.info(f"Request {state['request_id']} marked as completed")
        except Exception as e:
            logger.error(f"Error updating completion status: {e}")
        
        return state
    
    def handle_denial(self, state: InstallationState) -> InstallationState:
        """Handle permission denied cases."""
        try:
            if state["request_id"]:
                update_request_status(
                    request_id=state["request_id"],
                    status="denied",
                    error_message="Insufficient permissions"
                )
            logger.info(f"Request {state['request_id']} marked as denied")
        except Exception as e:
            logger.error(f"Error updating denial status: {e}")
        
        return state
    
    def handle_error(self, state: InstallationState) -> InstallationState:
        """Handle error cases."""
        try:
            if state["request_id"]:
                update_request_status(
                    request_id=state["request_id"],
                    status="failed",
                    error_message=state.get("error_message", "Unknown error")
                )
            logger.info(f"Request {state['request_id']} marked as failed")
        except Exception as e:
            logger.error(f"Error updating error status: {e}")
        
        return state
    
    def process_request(self, user_input: str, user_id: int, user_role: str) -> Dict[str, Any]:
        """Process an installation request through the complete workflow."""
        initial_state = InstallationState(
            messages=[],
            user_id=user_id,
            user_role=user_role,
            user_input=user_input,
            intent="",
            package_name="",
            version="",
            request_id=None,
            permission_granted=False,
            available_versions=[],
            installation_result={},
            error_message=None
        )
        
        try:
            final_state = self.workflow.invoke(initial_state)
            return self._format_response(final_state)
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return {
                "success": False,
                "message": f"Workflow error: {str(e)}",
                "type": "error"
            }
    
    def _format_response(self, state: InstallationState) -> Dict[str, Any]:
        """Format the final response based on workflow state."""
        if state["intent"] != "install":
            return {
                "success": False,
                "message": "This doesn't appear to be an installation request.",
                "type": "not_install"
            }
        
        if not state["permission_granted"]:
            allowed_packages = self.permission_manager.get_allowed_packages(state["user_role"])
            return {
                "success": False,
                "message": f"You don't have permission to install {state['package_name']}. Please contact admin.",
                "type": "permission_denied",
                "allowed_packages": list(allowed_packages)[:10]  # Show first 10
            }
        
        if state.get("installation_result", {}).get("success"):
            installation_result = state["installation_result"]
            message = f"Successfully installed {state['package_name']}!"
            
            # Add verification status to message
            if installation_result.get("verified"):
                message += " Package verified and ready to use."
            
            return {
                "success": True,
                "message": message,
                "type": "installation_success",
                "package": state["package_name"],
                "version": state.get("version", "latest"),
                "request_id": state["request_id"],
                "installation_output": installation_result.get("output", ""),
                "verified": installation_result.get("verified", False)
            }
        
        return {
            "success": False,
            "message": f"Installation failed: {state.get('error_message', 'Unknown error')}",
            "type": "installation_error",
            "error": state.get("error_message")
        }

# Factory function to create workflow instance
def create_installation_workflow(groq_api_key: str) -> InstallationWorkflow:
    """Factory function to create an installation workflow instance."""
    return InstallationWorkflow(groq_api_key)
