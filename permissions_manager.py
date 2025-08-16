"""
Permission management module for role-based package installation access.
Handles Excel-based permission hierarchy with inheritance.
"""

import pandas as pd
import logging
from typing import List, Dict, Set
import os

logger = logging.getLogger(__name__)

class PermissionManager:
    """Manages role-based permissions with hierarchical inheritance."""
    
    def __init__(self, excel_path: str = "permissions.xlsx"):
        self.excel_path = excel_path
        self.permissions_df = None
        self.role_hierarchy = {
            "Associate Software Engineer": 1,
            "Senior Software Engineer": 2,
            "Lead Software Engineer": 3,
            "Principal Software Engineer": 4,
            "Staff Software Engineer": 5,
            "Senior Staff Software Engineer": 6
        }
        self._load_permissions()
    
    def _load_permissions(self) -> None:
        """Load permissions from Excel file."""
        try:
            if os.path.exists(self.excel_path):
                self.permissions_df = pd.read_excel(self.excel_path)
                logger.info(f"Permissions loaded from {self.excel_path}")
            else:
                logger.warning(f"Permissions file {self.excel_path} not found. Creating default permissions.")
                self._create_default_permissions()
        except Exception as e:
            logger.error(f"Error loading permissions: {e}")
            self._create_default_permissions()
    
    def _create_default_permissions(self) -> None:
        """Create default permissions structure and save to Excel."""
        default_permissions = {
            "Role": [
                "Associate Software Engineer",
                "Senior Software Engineer", 
                "Lead Software Engineer",
                "Principal Software Engineer"
            ],
            "Allowed_Packages": [
                "numpy,pandas,requests,matplotlib,seaborn,scikit-learn",
                "tensorflow,pytorch,flask,django,fastapi,docker-compose",
                "kubernetes,helm,terraform,ansible,jenkins",
                "aws-cli,azure-cli,gcp-cli,prometheus,grafana,elasticsearch"
            ],
            "Description": [
                "Basic data science and web packages",
                "ML frameworks and web development tools", 
                "DevOps and infrastructure tools",
                "Cloud platforms and monitoring tools"
            ]
        }
        
        self.permissions_df = pd.DataFrame(default_permissions)
        
        try:
            self.permissions_df.to_excel(self.excel_path, index=False)
            logger.info(f"Default permissions created and saved to {self.excel_path}")
        except Exception as e:
            logger.error(f"Error creating default permissions file: {e}")
    
    def get_allowed_packages(self, user_role: str) -> Set[str]:
        """
        Get all allowed packages for a user role, including inherited permissions.
        Higher roles inherit all permissions from lower roles.
        """
        if self.permissions_df is None:
            logger.error("Permissions not loaded")
            return set()
        
        user_level = self.role_hierarchy.get(user_role, 0)
        if user_level == 0:
            logger.warning(f"Unknown role: {user_role}")
            return set()
        
        allowed_packages = set()
        
        # Get packages for all roles at or below the user's level
        for role, level in self.role_hierarchy.items():
            if level <= user_level:
                role_packages = self._get_packages_for_role(role)
                allowed_packages.update(role_packages)
        
        return allowed_packages
    
    def _get_packages_for_role(self, role: str) -> Set[str]:
        """Get packages specifically defined for a role."""
        try:
            role_row = self.permissions_df[self.permissions_df['Role'] == role]
            if not role_row.empty:
                packages_str = role_row['Allowed_Packages'].iloc[0]
                if pd.notna(packages_str):
                    # Split by comma and clean whitespace
                    packages = [pkg.strip() for pkg in packages_str.split(',')]
                    return set(packages)
        except Exception as e:
            logger.error(f"Error getting packages for role {role}: {e}")
        
        return set()
    
    def is_package_allowed(self, user_role: str, package_name: str) -> bool:
        """Check if a specific package is allowed for a user role."""
        allowed_packages = self.get_allowed_packages(user_role)
        
        # Check exact match and partial matches (for packages with versions)
        package_base = package_name.split('==')[0].split('>=')[0].split('<=')[0]
        
        return (package_name.lower() in [p.lower() for p in allowed_packages] or 
                package_base.lower() in [p.lower() for p in allowed_packages])
    
    def get_role_hierarchy_info(self) -> Dict[str, Dict]:
        """Get complete role hierarchy with their permissions."""
        hierarchy_info = {}
        
        for role, level in self.role_hierarchy.items():
            allowed_packages = self.get_allowed_packages(role)
            hierarchy_info[role] = {
                'level': level,
                'allowed_packages': sorted(list(allowed_packages)),
                'total_packages': len(allowed_packages)
            }
        
        return hierarchy_info
    
    def add_package_to_role(self, role: str, package_name: str) -> bool:
        """Add a new package permission to a specific role."""
        try:
            if self.permissions_df is None:
                return False
            
            role_idx = self.permissions_df[self.permissions_df['Role'] == role].index
            if len(role_idx) == 0:
                logger.error(f"Role {role} not found")
                return False
            
            idx = role_idx[0]
            current_packages = self.permissions_df.loc[idx, 'Allowed_Packages']
            
            if pd.isna(current_packages):
                new_packages = package_name
            else:
                packages_list = [p.strip() for p in current_packages.split(',')]
                if package_name not in packages_list:
                    packages_list.append(package_name)
                    new_packages = ','.join(packages_list)
                else:
                    logger.info(f"Package {package_name} already exists for role {role}")
                    return True
            
            self.permissions_df.loc[idx, 'Allowed_Packages'] = new_packages
            self.permissions_df.to_excel(self.excel_path, index=False)
            
            logger.info(f"Added package {package_name} to role {role}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding package to role: {e}")
            return False

def create_permissions_excel():
    """Standalone function to create the permissions Excel file."""
    pm = PermissionManager()
    print("Permissions Excel file created successfully!")
    
    # Display the hierarchy
    hierarchy = pm.get_role_hierarchy_info()
    print("\nRole Hierarchy:")
    for role, info in hierarchy.items():
        print(f"  {role} (Level {info['level']}): {info['total_packages']} packages")
        print(f"    Packages: {', '.join(info['allowed_packages'][:5])}{'...' if len(info['allowed_packages']) > 5 else ''}")

if __name__ == "__main__":
    create_permissions_excel()
