#!/usr/bin/env python3
"""
Script to create test users for Locust load testing.
This creates users both in the app's users.json file and in test_users.csv for Locust.
"""

import os
import json
import csv
import random
import string
from werkzeug.security import generate_password_hash
from pathlib import Path

def random_password(length=8):
    """Generate a random password of specified length"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def create_test_users(num_users=10, users_json_path='users.json', test_users_csv='test_users.csv'):
    """Create test users in both users.json and test_users.csv"""
    
    # Make sure the directory exists
    Path(os.path.dirname(users_json_path)).mkdir(parents=True, exist_ok=True)
    
    # Load existing users.json if it exists
    if os.path.exists(users_json_path):
        try:
            with open(users_json_path, 'r') as f:
                users = json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {users_json_path}, creating new file")
            users = {}
    else:
        users = {}
    
    # Test users to be added to CSV for Locust
    test_users = []
    
    # Generate test users
    for i in range(1, num_users + 1):
        username = f"test_user{i}@example.com"
        password = f"password{i}"  # Simple predictable password for tests
        name = f"Test User {i}"
        
        # Add to users dictionary for app
        users[username] = {
            "password": generate_password_hash(password),
            "name": name
        }
        
        # Add to test_users for Locust
        test_users.append({
            "username": username,
            "password": password
        })
    
    # Save to users.json (for the app)
    with open(users_json_path, 'w') as f:
        json.dump(users, f, indent=4)
    
    # Save to test_users.csv (for Locust)
    with open(test_users_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["username", "password"])
        writer.writeheader()
        writer.writerows(test_users)
    
    print(f"Created {num_users} test users")
    print(f"- App users saved to: {users_json_path}")
    print(f"- Locust test users saved to: {test_users_csv}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create test users for load testing")
    parser.add_argument("--num-users", type=int, default=10, help="Number of test users to create")
    parser.add_argument("--users-json", default="users.json", help="Path to users.json file")
    parser.add_argument("--test-users-csv", default="test_users.csv", help="Path to test_users.csv file")
    
    args = parser.parse_args()
    
    create_test_users(
        num_users=args.num_users,
        users_json_path=args.users_json,
        test_users_csv=args.test_users_csv
    )
