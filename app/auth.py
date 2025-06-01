"""
Authentication Module
Handles user authentication and session management
"""
import json
import os
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    """User model for Flask-Login"""
    
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(username, password):
        """Create a new user with hashed password"""
        password_hash = generate_password_hash(password)
        return User(username, username, password_hash)


class UserManager:
    """Manages user storage and retrieval"""
    
    def __init__(self, users_file='users.json'):
        self.users_file = users_file
        self.users = self._load_users()

    def _load_users(self):
        """Load users from JSON file"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    users_data = json.load(f)
                    users = {}
                    for username, data in users_data.items():
                        users[username] = User(data['id'], data['username'], data['password_hash'])
                    return users
            else:
                # Create default admin user if no users file exists
                return self._create_default_users()
                
        except Exception as e:
            print(f"Error loading users: {e}")
            return self._create_default_users()

    def _create_default_users(self):
        """Create default admin user"""
        default_users = {
            'admin': User('1', 'admin', generate_password_hash('admin123'))
        }
        self._save_users(default_users)
        return default_users

    def _save_users(self, users=None):
        """Save users to JSON file"""
        if users is None:
            users = self.users
            
        try:
            users_data = {}
            for username, user in users.items():
                users_data[username] = {
                    'id': user.id,
                    'username': user.username,
                    'password_hash': user.password_hash
                }
                
            with open(self.users_file, 'w') as f:
                json.dump(users_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving users: {e}")

    def get_user(self, username):
        """Get user by username"""
        return self.users.get(username)

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        for user in self.users.values():
            if user.id == user_id:
                return user
        return None

    def authenticate_user(self, username, password):
        """Authenticate a user with username and password"""
        user = self.get_user(username)
        if user and user.check_password(password):
            return user
        return None

    def add_user(self, username, password):
        """Add a new user"""
        if username in self.users:
            raise ValueError(f"User {username} already exists")
            
        user_id = str(len(self.users) + 1)
        password_hash = generate_password_hash(password)
        user = User(user_id, username, password_hash)
        
        self.users[username] = user
        self._save_users()
        return user

    def update_user_password(self, username, new_password):
        """Update user password"""
        user = self.get_user(username)
        if not user:
            raise ValueError(f"User {username} not found")
            
        user.password_hash = generate_password_hash(new_password)
        self._save_users()
        return user

    def delete_user(self, username):
        """Delete a user"""
        if username not in self.users:
            raise ValueError(f"User {username} not found")
            
        del self.users[username]
        self._save_users()

    def list_users(self):
        """Get list of all usernames"""
        return list(self.users.keys())


# Global user manager instance
user_manager = UserManager()