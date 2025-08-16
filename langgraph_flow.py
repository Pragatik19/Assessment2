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

from db_setup import log_request, update_request_status, is_package_already_installed, check_package_installation_history
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
    already_installed: bool
    installation_history: Optional[Dict[str, Any]]
    available_versions: List[str]
    installation_result: Dict[str, Any]
    error_message: Optional[str]

class InstallationWorkflow:
    """LangGraph-based workflow for handling installation requests."""
    
    def __init__(self, groq_api_key: str):
        # Use provided key or fall back to environment
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.llm = ChatGroq(
            groq_api_key=self.groq_api_key,
            model_name="gemma2-9b-it",
            temperature=0.0  # Use 0 temperature for more consistent JSON output
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
        workflow.add_node("check_installation_history", self.check_installation_history)
        workflow.add_node("check_versions", self.check_versions)
        workflow.add_node("execute_installation", self.execute_installation)
        workflow.add_node("update_completion", self.update_completion)
        workflow.add_node("handle_denial", self.handle_denial)
        workflow.add_node("handle_already_installed", self.handle_already_installed)
        workflow.add_node("handle_qa_response", self.handle_qa_response)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point
        workflow.set_entry_point("interpret_intent")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "interpret_intent",
            self.route_after_intent,
            {
                "install": "log_request",
                "qa": "handle_qa_response",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("log_request", "check_permissions")
        
        workflow.add_conditional_edges(
            "check_permissions",
            self.route_after_permissions,
            {
                "granted": "check_installation_history",
                "denied": "handle_denial"
            }
        )
        
        workflow.add_conditional_edges(
            "check_installation_history",
            self.route_after_installation_check,
            {
                "already_installed": "handle_already_installed",
                "not_installed": "check_versions"
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
        workflow.add_edge("handle_already_installed", END)
        workflow.add_edge("handle_qa_response", END)
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
            You must analyze the user input and respond with ONLY a valid JSON object, no other text.
            
            User input: "{state['user_input']}"
            
            Determine if this is an installation request. Installation requests include:
            - Install, setup, add, or download a software package
            - Get or obtain a library or tool
            - Use pip, conda, or other package managers
            
            Return ONLY this JSON format (no explanations):
            {{
                "intent": "install" or "not_install",
                "package_name": "package_name_if_install_else_null",
                "version": "version_if_specified_else_null"
            }}
            
            Examples:
            Input: "Install numpy" -> {{"intent": "install", "package_name": "numpy", "version": null}}
            Input: "What is Python?" -> {{"intent": "not_install", "package_name": null, "version": null}}
            Input: "Install pandas 1.5.0" -> {{"intent": "install", "package_name": "pandas", "version": "1.5.0"}}
            
            Respond with ONLY the JSON object:"""
            
            response = self.llm.invoke(prompt)
            
            try:
                # Try to parse as JSON
                result = json.loads(response.content)
                state["intent"] = result["intent"]
                state["package_name"] = result["package_name"]
                state["version"] = result["version"]
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from the response
                response_text = response.content.strip()
                logger.warning(f"Failed to parse JSON directly. Response: {response_text}")
                
                # Look for JSON block in the response using more comprehensive regex
                import re
                # Try to find JSON object with nested structure
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text)
                if not json_match:
                    # Try simpler pattern
                    json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        state["intent"] = result["intent"]
                        state["package_name"] = result["package_name"]
                        state["version"] = result["version"]
                    except json.JSONDecodeError:
                        # If still fails, assume it's not an install request
                        logger.warning(f"Could not extract valid JSON from response: {response_text}")
                        state["intent"] = "not_install"
                        state["package_name"] = None
                        state["version"] = None
                else:
                    # No JSON found, assume it's not an install request
                    logger.warning(f"No JSON found in response: {response_text}")
                    state["intent"] = "not_install" 
                    state["package_name"] = None
                    state["version"] = None
            
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
            return "qa"
    
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
    
    def check_installation_history(self, state: InstallationState) -> InstallationState:
        """Check if the package has been previously installed by the user."""
        try:
            is_installed = is_package_already_installed(state["user_id"], state["package_name"])
            state["already_installed"] = is_installed
            
            if is_installed:
                # Get the installation details
                installation_history = check_package_installation_history(state["user_id"], state["package_name"])
                state["installation_history"] = installation_history
                logger.info(f"Package {state['package_name']} was previously installed by user {state['user_id']}")
            else:
                state["installation_history"] = None
                logger.info(f"Package {state['package_name']} has not been installed before by user {state['user_id']}")
                
        except Exception as e:
            logger.error(f"Error checking installation history: {e}")
            state["already_installed"] = False
            state["installation_history"] = None
        
        return state
    
    def route_after_installation_check(self, state: InstallationState) -> str:
        """Route based on installation history check."""
        return "already_installed" if state["already_installed"] else "not_installed"
    
    def handle_already_installed(self, state: InstallationState) -> InstallationState:
        """Handle case where package is already installed."""
        try:
            # Update request status to indicate already installed
            if state["request_id"]:
                update_request_status(
                    request_id=state["request_id"],
                    status="completed",  # Mark as completed since it's already available
                    error_message="Package already installed"
                )
            logger.info(f"Package {state['package_name']} already installed for user {state['user_id']}")
        except Exception as e:
            logger.error(f"Error updating already installed status: {e}")
        
        return state
    
    def handle_qa_response(self, state: InstallationState) -> InstallationState:
        """Handle general Q&A responses using LLM."""
        try:
            prompt = f"""
            You are a helpful AI assistant for a system setup tool. A user has asked a general question (not an installation request).
            
            User question: "{state['user_input']}"
            
            Please provide a helpful and informative response. If the question is about:
            - Programming concepts: Explain clearly with examples
            - Software tools: Provide usage information and best practices
            - System setup: Give guidance on configuration and setup
            - Package information: Explain what packages do and how they're used
            
            Keep your response concise but informative. If you're not sure about something, say so.
            """
            
            response = self.llm.invoke(prompt)
            
            # Store the AI response in the state for formatting
            state["installation_result"] = {
                "success": True,
                "ai_response": response.content,
                "type": "qa_response"
            }
            
            logger.info(f"Generated Q&A response for user {state['user_id']}")
            
        except Exception as e:
            logger.error(f"Error generating Q&A response: {e}")
            state["error_message"] = f"Failed to generate response: {str(e)}"
            state["installation_result"] = {
                "success": False,
                "error": str(e),
                "type": "qa_error"
            }
        
        return state
    
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
        return self.process_unified_request(user_input, user_id, user_role)
    
    def process_unified_request(self, user_input: str, user_id: int, user_role: str) -> Dict[str, Any]:
        """Process a unified request (Q&A or installation) through the complete workflow."""
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
            already_installed=False,
            installation_history=None,
            available_versions=[],
            installation_result={},
            error_message=None
        )
        
        try:
            final_state = self.workflow.invoke(initial_state)
            return self._format_unified_response(final_state)
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
    
    def _format_unified_response(self, state: InstallationState) -> Dict[str, Any]:
        """Format the final response for unified workflow (handles both Q&A and installation)."""
        # Handle Q&A responses
        if state["intent"] != "install":
            if state.get("installation_result", {}).get("type") == "qa_response":
                return {
                    "success": True,
                    "message": state["installation_result"]["ai_response"],
                    "type": "qa_response"
                }
            else:
                return {
                    "success": False,
                    "message": state.get("error_message", "Failed to generate response"),
                    "type": "qa_error"
                }
        
        # Handle installation requests
        if not state["permission_granted"]:
            allowed_packages = self.permission_manager.get_allowed_packages(state["user_role"])
            return {
                "success": False,
                "message": f"❌ You don't have permission to install {state['package_name']}. Please contact your administrator.",
                "type": "permission_denied",
                "allowed_packages": list(allowed_packages)[:10]  # Show first 10
            }
        
        # Handle already installed packages
        if state["already_installed"]:
            installation_history = state.get("installation_history", {})
            install_date = installation_history.get("complete_time", "unknown date") if installation_history else "unknown date"
            installed_version = installation_history.get("version", "unknown version") if installation_history else "unknown version"
            
            return {
                "success": True,
                "message": f"📦 The package '{state['package_name']}' is already installed (version: {installed_version}, installed: {install_date})",
                "type": "already_installed",
                "package": state["package_name"],
                "version": installed_version,
                "install_date": install_date
            }
        
        # Handle successful new installation
        if state.get("installation_result", {}).get("success"):
            installation_result = state["installation_result"]
            message = f"✅ Successfully installed {state['package_name']}!"
            
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
        
        # Handle installation errors
        return {
            "success": False,
            "message": f"❌ Installation failed: {state.get('error_message', 'Unknown error')}",
            "type": "installation_error",
            "error": state.get("error_message")
        }

# Factory function to create workflow instance
def create_installation_workflow(groq_api_key: str) -> InstallationWorkflow:
    """Factory function to create an installation workflow instance."""
    return InstallationWorkflow(groq_api_key)
