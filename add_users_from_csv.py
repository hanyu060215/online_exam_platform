#!/usr/bin/env python3
"""
Script to add users from a CSV file to the users.json file.
Format of CSV: username,name,password
"""

import json
import csv
import os
from werkzeug.security import generate_password_hash
from pathlib import Path

def add_users_from_csv(csv_path='new_users.csv', users_json_path='users.json'):
    """Add users from CSV file to users.json"""
    
    # Make sure users.json exists
    if os.path.exists(users_json_path):
        try:
            with open(users_json_path, 'r') as f:
                users = json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {users_json_path}, creating new file")
            users = {}
    else:
        users = {}
    
    # Read users from CSV
    added_users = []
    skipped_users = []
    
    with open(csv_path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Check if we have all required fields
            if not all(k in row for k in ('username', 'name', 'password')):
                print(f"Skipping row: {row} - missing required fields")
                continue
                
            username = row['username']
            name = row['name']
            password = row['password']
            
            # Check if user already exists
            if username in users:
                print(f"User {username} already exists, skipping")
                skipped_users.append(username)
                continue
            
            # Add user
            users[username] = {
                "password": generate_password_hash(password),
                "name": name
            }
            added_users.append(username)
    
    # Save to users.json
    with open(users_json_path, 'w') as f:
        json.dump(users, f, indent=4)
    
    # Print summary
    if added_users:
        print(f"Added {len(added_users)} users: {', '.join(added_users)}")
    if skipped_users:
        print(f"Skipped {len(skipped_users)} existing users: {', '.join(skipped_users)}")
    
    return added_users, skipped_users

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add users from CSV to users.json")
    parser.add_argument("--csv", default="new_users.csv", help="Path to CSV file with users")
    parser.add_argument("--users-json", default="users.json", help="Path to users.json file")
    
    args = parser.parse_args()
    
    add_users_from_csv(
        csv_path=args.csv,
        users_json_path=args.users_json
    )
