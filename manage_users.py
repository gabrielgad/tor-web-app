#!/usr/bin/env python3
# manage_users.py - User management script for Torrent Web App

import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
import getpass

USERS_FILE = 'users.json'

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def add_user():
    """Add a new user"""
    users = load_users()
    
    username = input("Enter username: ").strip()
    if not username:
        print("Username cannot be empty")
        return
    
    if username in users:
        print(f"User '{username}' already exists")
        return
    
    while True:
        password = getpass.getpass("Enter password: ")
        if len(password) < 6:
            print("Password must be at least 6 characters long")
            continue
        
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("Passwords do not match")
            continue
        break
    
    users[username] = {
        'id': str(len(users) + 1),
        'username': username,
        'password_hash': generate_password_hash(password)
    }
    
    save_users(users)
    print(f"User '{username}' added successfully")

def remove_user():
    """Remove a user"""
    users = load_users()
    
    if not users:
        print("No users found")
        return
    
    print("Existing users:")
    for username in users.keys():
        print(f"  - {username}")
    
    username = input("Enter username to remove: ").strip()
    if username not in users:
        print(f"User '{username}' not found")
        return
    
    if username == 'admin':
        confirm = input("Are you sure you want to remove the admin user? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Operation cancelled")
            return
    
    del users[username]
    save_users(users)
    print(f"User '{username}' removed successfully")

def list_users():
    """List all users"""
    users = load_users()
    
    if not users:
        print("No users found")
        return
    
    print("Users:")
    for username, user_data in users.items():
        print(f"  - {username} (ID: {user_data['id']})")

def change_password():
    """Change user password"""
    users = load_users()
    
    if not users:
        print("No users found")
        return
    
    print("Existing users:")
    for username in users.keys():
        print(f"  - {username}")
    
    username = input("Enter username: ").strip()
    if username not in users:
        print(f"User '{username}' not found")
        return
    
    while True:
        password = getpass.getpass("Enter new password: ")
        if len(password) < 6:
            print("Password must be at least 6 characters long")
            continue
        
        confirm_password = getpass.getpass("Confirm new password: ")
        if password != confirm_password:
            print("Passwords do not match")
            continue
        break
    
    users[username]['password_hash'] = generate_password_hash(password)
    save_users(users)
    print(f"Password for '{username}' changed successfully")

def setup_default_admin():
    """Set up default admin user"""
    users = load_users()
    
    if 'admin' in users:
        print("Admin user already exists")
        return
    
    print("Setting up default admin user...")
    while True:
        password = getpass.getpass("Enter admin password: ")
        if len(password) < 6:
            print("Password must be at least 6 characters long")
            continue
        
        confirm_password = getpass.getpass("Confirm admin password: ")
        if password != confirm_password:
            print("Passwords do not match")
            continue
        break
    
    users['admin'] = {
        'id': '1',
        'username': 'admin',
        'password_hash': generate_password_hash(password)
    }
    
    save_users(users)
    print("Admin user created successfully")

def main():
    """Main menu"""
    while True:
        print("\n" + "="*50)
        print("Torrent Web App - User Management")
        print("="*50)
        print("1. Add user")
        print("2. Remove user")
        print("3. List users")
        print("4. Change password")
        print("5. Setup default admin")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            add_user()
        elif choice == '2':
            remove_user()
        elif choice == '3':
            list_users()
        elif choice == '4':
            change_password()
        elif choice == '5':
            setup_default_admin()
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == '__main__':
    main()
