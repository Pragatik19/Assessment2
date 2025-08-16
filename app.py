"""
Main Streamlit application for the Automated System Setup Tool.
Provides login, Q&A chat, and installation request interfaces.
"""

import streamlit as st
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import os
import json

from langchain_groq import ChatGroq

from db_setup import authenticate_user, get_user_requests, initialize_database
from langgraph_flow import create_installation_workflow
from permissions_manager import PermissionManager
from config import get_environment_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Automated System Setup Tool",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'groq_api_key' not in st.session_state:
    # Load API key from environment
    env_config = get_environment_config()
    st.session_state.groq_api_key = env_config.get('groq_api_key')
if 'user_allowed_packages' not in st.session_state:
    st.session_state.user_allowed_packages = set()
if 'show_permissions' not in st.session_state:
    st.session_state.show_permissions = False

def initialize_app():
    """Initialize the application and database."""
    try:
        initialize_database()
        logger.info("Application initialized successfully")
    except Exception as e:
        st.error(f"Failed to initialize application: {e}")
        logger.error(f"App initialization error: {e}")

def login_page():
    """Display the login page."""
    st.title("🔧 Automated System Setup Tool")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("🔐 Login")
        
        with st.form("login_form"):
            employee_id = st.text_input("Employee ID", placeholder="EMP001")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            login_button = st.form_submit_button("Login", use_container_width=True)
            
            if login_button:
                if not employee_id or not password:
                    st.error("Please enter both Employee ID and Password")
                else:
                    user = authenticate_user(employee_id, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        logger.info(f"User {user['name']} logged in successfully")
                        st.success(f"Welcome, {user['name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Please try again.")
                        logger.warning(f"Failed login attempt for employee ID: {employee_id}")
        
        # Demo credentials
        with st.expander("🔍 Demo Credentials"):
            st.markdown("""
            **Test Accounts:**
            - **Employee ID:** EMP001, **Password:** password123 (Associate Software Engineer)
            - **Employee ID:** EMP002, **Password:** password456 (Senior Software Engineer)  
            - **Employee ID:** EMP003, **Password:** password789 (Lead Software Engineer)
            - **Employee ID:** EMP004, **Password:** passwordabc (Principal Software Engineer)
            """)

def sidebar_config():
    """Configure the sidebar with user info and settings."""
    with st.sidebar:
        if st.session_state.authenticated and st.session_state.user:
            user = st.session_state.user
            st.markdown(f"### 👤 Welcome, {user['name']}")
            st.markdown(f"**Role:** {user['role']}")
            st.markdown(f"**Employee ID:** {user['employee_id']}")
            st.markdown("---")
            # Load user's allowed packages (for internal use)
            try:
                pm = PermissionManager()
                allowed_packages = pm.get_allowed_packages(user['role'])
                st.session_state.user_allowed_packages = allowed_packages
            except Exception as e:
                st.error(f"Error loading permissions: {e}")
                st.session_state.user_allowed_packages = set()
            
            # Permissions button in sidebar
            if st.button("📦 View My Permissions", use_container_width=True):
                st.session_state.show_permissions = True
            
            # Show permissions modal if button was clicked
            if st.session_state.get('show_permissions', False):
                show_permissions_modal()
                # Add a close button
                if st.button("❌ Close Permissions", use_container_width=True):
                    st.session_state.show_permissions = False
                    st.rerun()
            
            st.markdown("---")
            
            # Recent requests
            try:
                recent_requests = get_user_requests(user['id'], limit=5)
                st.markdown("### 📋 Recent Requests")
                
                if recent_requests:
                    for req in recent_requests:
                        status_emoji = {
                            'completed': '✅',
                            'pending': '⏳',
                            'failed': '❌',
                            'denied': '🚫'
                        }.get(req['status'], '❓')
                        
                        st.markdown(f"{status_emoji} {req['package_name']}")
                else:
                    st.markdown("*No recent requests*")
                    
            except Exception as e:
                st.error(f"Error loading requests: {e}")
            
            st.markdown("---")
            
            # Logout
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.chat_history = []
                st.session_state.user_allowed_packages = set()
                logger.info(f"User {user['name']} logged out")
                st.rerun()

def unified_chat_interface():
    """Unified chat interface that handles both Q&A and installation requests."""
    st.subheader("💬 AI Assistant - Chat & Install Packages")
    
    if not st.session_state.groq_api_key:
        st.warning("⚠️ Please configure your Groq API key in the sidebar to use the chat feature.")
        return
    

    
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if user_input := st.chat_input("Ask me anything or request package installation..."):
        # Add user message to history
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.write(user_input)
        
        # Process the input through unified workflow
        try:
            user = st.session_state.user
            workflow = create_installation_workflow(st.session_state.groq_api_key)
            
            with st.chat_message("assistant"):
                with st.spinner("Processing your request..."):
                    result = workflow.process_unified_request(
                        user_input=user_input,
                        user_id=user['id'],
                        user_role=user['role']
                    )
                    
                    # Display the result
                    st.write(result['message'])
                    
                    # Show additional info if it's an installation
                    if result['type'] == 'installation_success':
                        if result.get('package'):
                            st.info(f"📦 Package: {result['package']}")
                        if result.get('version'):
                            st.info(f"🏷️ Version: {result['version']}")
                        
                        # Show installation details in expander
                        if result.get('installation_output'):
                            with st.expander("Installation Details", expanded=False):
                                st.code(result['installation_output'])
                    
                    elif result['type'] == 'permission_denied':
                        st.error("❌ Permission denied")
                        st.info("💡 Click 'View My Permissions' button in the sidebar to see what packages you can install.")
                    
                    elif result['type'] == 'already_installed':
                        st.info("ℹ️ Package already installed")
            
            # Add AI response to history
            st.session_state.chat_history.append({"role": "assistant", "content": result['message']})
            
        except Exception as e:
            error_msg = f"Error processing request: {e}"
            st.error(error_msg)
            st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
            logger.error(f"Unified chat error: {e}")

def show_permissions_modal():
    """Display user permissions in a modal-like expander."""
    try:
        user = st.session_state.user
        pm = PermissionManager()
        allowed_packages = pm.get_allowed_packages(user['role'])
        
        with st.expander(f"📦 Your Package Permissions ({user['role']})", expanded=True):
            st.markdown(f"**Total Packages Available:** {len(allowed_packages)}")
            
            if allowed_packages:
                # Search functionality
                search_term = st.text_input("🔍 Search packages:", placeholder="Type to filter packages...")
                
                package_list = sorted(list(allowed_packages))
                if search_term:
                    package_list = [p for p in package_list if search_term.lower() in p.lower()]
                
                st.markdown(f"**Showing {len(package_list)} packages:**")
                
                # Display packages in columns
                if package_list:
                    cols = st.columns(3)
                    for i, pkg in enumerate(package_list):
                        with cols[i % 3]:
                            st.write(f"✅ {pkg}")
                else:
                    st.info("No packages match your search.")
            else:
                st.warning("No packages currently allowed for your role.")
                
    except Exception as e:
        st.error(f"Error loading permissions: {e}")
        logger.error(f"Error in permissions modal: {e}")



# def permissions_page():
#     """Display detailed permissions information."""
#     st.subheader("📦 Package Permissions")
    
#     try:
#         pm = PermissionManager()
#         user = st.session_state.user
        
#         # User's permissions
#         user_packages = pm.get_allowed_packages(user['role'])
        
#         col1, col2 = st.columns([3, 2])
        
#         with col1:
#             st.markdown(f"### Your Permissions ({user['role']})")
#             st.markdown(f"**Total Packages:** {len(user_packages)}")
            
#             if user_packages:
#                 # Search and filter
#                 search_term = st.text_input("🔍 Search your packages:", placeholder="Type to filter...")
                
#                 filtered_packages = sorted(list(user_packages))
#                 if search_term:
#                     filtered_packages = [p for p in filtered_packages if search_term.lower() in p.lower()]
                
#                 st.markdown(f"**Showing {len(filtered_packages)} packages:**")
                
#                 # Display in columns for better layout
#                 if filtered_packages:
#                     cols = st.columns(3)
#                     for i, pkg in enumerate(filtered_packages):
#                         with cols[i % 3]:
#                             st.write(f"✅ {pkg}")
#                 else:
#                     st.info("No packages match your search.")
#             else:
#                 st.warning("No packages currently allowed for your role.")
        
#         with col2:
#             st.markdown("### Permission Summary")
            
#             # Show role progression
#             hierarchy = pm.get_role_hierarchy_info()
#             user_level = hierarchy.get(user['role'], {}).get('level', 0)
            
#             st.markdown("**Role Progression:**")
#             for role, info in hierarchy.items():
#                 level = info['level']
#                 is_current = (role == user['role'])
#                 is_lower = level < user_level
#                 is_higher = level > user_level
                
#                 if is_current:
#                     st.success(f"🟢 **{role}** (Your Level)")
#                     st.markdown(f"   📦 {info['total_packages']} packages")
#                 elif is_lower:
#                     st.info(f"🔵 {role}")
#                     st.markdown(f"   📦 {info['total_packages']} packages (inherited)")
#                 else:
#                     st.error(f"🔴 {role}")
#                     st.markdown(f"   📦 {info['total_packages']} packages (not accessible)")
            
#             st.markdown("---")
            
#             # Permission inheritance explanation
#             st.markdown("### How Permissions Work")
#             st.info("""
#             **Hierarchical Inheritance:**
#             • Higher roles inherit ALL permissions from lower roles
#             • Your role gets packages from your level + all lower levels
#             • Contact admin to add new packages to your role
#             """)
            
#             # Package categories
#             if user_packages:
#                 st.markdown("### Package Categories")
#                 common_categories = {
#                     'data': ['numpy', 'pandas', 'scipy'],
#                     'ml': ['tensorflow', 'pytorch', 'scikit-learn'],
#                     'web': ['flask', 'django', 'fastapi'],
#                     'devops': ['docker', 'kubernetes', 'ansible'],
#                     'cloud': ['aws-cli', 'azure-cli', 'gcp-cli']
#                 }
                
#                 user_package_list = list(user_packages)
#                 for category, packages in common_categories.items():
#                     available = [pkg for pkg in packages if pkg in user_package_list]
#                     if available:
#                         st.write(f"**{category.title()}:** {', '.join(available)}")
    
    # except Exception as e:
    #     st.error(f"Error loading permissions: {e}")
    #     logger.error(f"Permissions page error: {e}")

def main():
    """Main application function."""
    initialize_app()
    
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Authenticated user interface
    sidebar_config()
    
    # Main unified chat interface
    unified_chat_interface()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "Automated System Setup Tool | Powered by Groq LLM & LangGraph"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
