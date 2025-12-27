#!/usr/bin/env python3
"""
Utility script to set a user as admin in the users.json file
"""
import json
import sys
import os

def load_users():
    """Load users from JSON file"""
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: users.json file not found.")
        return {}

def save_users(users):
    """Save users to JSON file"""
    try:
        with open('users.json', 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=4)
        print("Users file updated successfully.")
    except Exception as e:
        print(f"Error saving users: {str(e)}")

def set_admin(username, admin_status=True):
    """Set or remove admin status for a user"""
    users = load_users()
    
    if username not in users:
        print(f"Error: User '{username}' not found.")
        return False
    
    # Update the admin status
    users[username]['is_admin'] = admin_status
    
    # Save the updated users dictionary
    save_users(users)
    
    status = "admin" if admin_status else "regular user"
    print(f"User '{username}' is now set as {status}.")
    return True

def list_users():
    """List all users and their admin status"""
    users = load_users()
    
    if not users:
        print("No users found.")
        return
    
    print("\nUser List:")
    print("-" * 50)
    print(f"{'Username':<20} {'Name':<20} {'Admin Status'}")
    print("-" * 50)
    
    for username, data in users.items():
        name = data.get('name', 'N/A')
        is_admin = data.get('is_admin', False)
        admin_status = "Admin" if is_admin else "Regular User"
        print(f"{username:<20} {name:<20} {admin_status}")

def show_help():
    """Show usage instructions"""
    print("Usage:")
    print("  python set_admin.py list                   # List all users")
    print("  python set_admin.py set <username>         # Set user as admin")
    print("  python set_admin.py unset <username>       # Remove admin status")
    print("  python set_admin.py help                   # Show this help message")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
    else:
        command = sys.argv[1].lower()
        
        if command == "list":
            list_users()
        elif command == "set" and len(sys.argv) >= 3:
            set_admin(sys.argv[2], True)
        elif command == "unset" and len(sys.argv) >= 3:
            set_admin(sys.argv[2], False)
        elif command == "help":
            show_help()
        else:
            print("Invalid command or missing username.")
            show_help()
