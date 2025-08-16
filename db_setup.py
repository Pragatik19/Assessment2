"""
Database setup module for the Automated System Setup Tool.
Creates SQLite database with users and requests tables, and seeds test data.
"""

import sqlite3
import hashlib
import logging
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "system_setup.db"

def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_database() -> None:
    """Create the SQLite database and tables."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                package_name TEXT NOT NULL,
                version TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                complete_time TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        conn.commit()
        logger.info("Database and tables created successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Error creating database: {e}")
        raise
    finally:
        conn.close()

def seed_test_users() -> None:
    """Seed the database with test users."""
    test_users = [
        ("John Doe", "EMP001", "Associate Software Engineer", "password123"),
        ("Jane Smith", "EMP002", "Senior Software Engineer", "password456"),
        ("Mike Johnson", "EMP003", "Lead Software Engineer", "password789"),
        ("Sarah Williams", "EMP004", "Principal Software Engineer", "passwordabc"),
        ("David Brown", "EMP005", "Associate Software Engineer", "passworddef"),
    ]
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if users already exist
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        
        if count == 0:
            for name, emp_id, role, password in test_users:
                hashed_password = hash_password(password)
                cursor.execute("""
                    INSERT INTO users (name, employee_id, role, password)
                    VALUES (?, ?, ?, ?)
                """, (name, emp_id, role, hashed_password))
            
            conn.commit()
            logger.info("Test users seeded successfully")
        else:
            logger.info("Users already exist, skipping seeding")
            
    except sqlite3.Error as e:
        logger.error(f"Error seeding users: {e}")
        raise
    finally:
        conn.close()

def get_user_by_employee_id(employee_id: str) -> Optional[dict]:
    """Get user by employee ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, employee_id, role, password
            FROM users
            WHERE employee_id = ?
        """, (employee_id,))
        
        user = cursor.fetchone()
        if user:
            return {
                'id': user[0],
                'name': user[1],
                'employee_id': user[2],
                'role': user[3],
                'password': user[4]
            }
        return None
        
    except sqlite3.Error as e:
        logger.error(f"Error fetching user: {e}")
        return None
    finally:
        conn.close()

def authenticate_user(employee_id: str, password: str) -> Optional[dict]:
    """Authenticate user with employee ID and password."""
    user = get_user_by_employee_id(employee_id)
    if user and user['password'] == hash_password(password):
        # Remove password from returned user data
        del user['password']
        return user
    return None

def log_request(user_id: int, package_name: str, version: str = None) -> int:
    """Log a new installation request and return the request ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO requests (user_id, package_name, version, status)
            VALUES (?, ?, ?, 'pending')
        """, (user_id, package_name, version))
        
        request_id = cursor.lastrowid
        conn.commit()
        logger.info(f"Request logged: {package_name} for user {user_id}")
        return request_id
        
    except sqlite3.Error as e:
        logger.error(f"Error logging request: {e}")
        raise
    finally:
        conn.close()

def update_request_status(request_id: int, status: str, version: str = None, error_message: str = None) -> None:
    """Update request status and completion details."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if status == 'completed':
            cursor.execute("""
                UPDATE requests
                SET status = ?, version = ?, complete_time = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, version, request_id))
        else:
            cursor.execute("""
                UPDATE requests
                SET status = ?, error_message = ?, complete_time = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, error_message, request_id))
        
        conn.commit()
        logger.info(f"Request {request_id} status updated to {status}")
        
    except sqlite3.Error as e:
        logger.error(f"Error updating request status: {e}")
        raise
    finally:
        conn.close()

def get_user_requests(user_id: int, limit: int = 10) -> list:
    """Get recent requests for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, package_name, version, status, request_time, complete_time, error_message
            FROM requests
            WHERE user_id = ?
            ORDER BY request_time DESC
            LIMIT ?
        """, (user_id, limit))
        
        requests = cursor.fetchall()
        return [
            {
                'id': req[0],
                'package_name': req[1],
                'version': req[2],
                'status': req[3],
                'request_time': req[4],
                'complete_time': req[5],
                'error_message': req[6]
            }
            for req in requests
        ]
        
    except sqlite3.Error as e:
        logger.error(f"Error fetching user requests: {e}")
        return []
    finally:
        conn.close()

def initialize_database() -> None:
    """Initialize the complete database setup."""
    logger.info("Initializing database...")
    create_database()
    seed_test_users()
    logger.info("Database initialization complete")

if __name__ == "__main__":
    initialize_database()
    
    # Test authentication
    print("\nTesting authentication:")
    user = authenticate_user("EMP001", "password123")
    if user:
        print(f"Authentication successful: {user['name']} ({user['role']})")
    else:
        print("Authentication failed")
