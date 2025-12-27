# locustfile.py
import random
import csv
import os
import json
import time
from typing import List, Dict, Optional
from locust import HttpUser, task, between, events

class StudentUser(HttpUser):
    """
    Simulates a student interacting with the online code test website.
    """
    # Wait between 1 and 3 seconds between tasks
    wait_time = between(1, 3)
    host = "http://127.0.0.1:5004/"  # Replace with your app's actual host and port

    # Available question IDs your app uses - updated to match actual format
    available_question_ids = ["Q1", "Q2", "Q3", "Q4", "Q5"] # Uppercase Q format
    
    # Class variable to store users
    _test_users = []
    _current_user_index = 0
    
    @classmethod
    def load_test_users(cls):
        """
        Load test users from file or create them if the file doesn't exist
        """
        # Check if test users are already loaded
        if cls._test_users:
            return
            
        users_file = 'test_users.csv'
        
        # Try to load from CSV first
        if os.path.exists(users_file):
            try:
                with open(users_file, 'r') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        cls._test_users.append({
                            'username': row['username'],
                            'password': row['password']
                        })
                print(f"Loaded {len(cls._test_users)} test users from {users_file}")
                return
            except Exception as e:
                print(f"Error loading test users from CSV: {str(e)}")
        
        # If CSV doesn't exist, try to load from users.json (app's user database)
        try:
            # Attempt to load real users from app's users.json
            if os.path.exists('users.json'):
                with open('users.json', 'r') as file:
                    users_data = json.load(file)
                    # Extract usernames and passwords
                    for username, user_data in users_data.items():
                        # Skip if the password is hashed and we can't use it
                        # In a real setup, you'd have a separate file with test credentials
                        if username != "schen3@hamilton.edu":  # Skip default test user
                            cls._test_users.append({
                                'username': username,
                                'password': 'test123'  # Using default test password 
                            })
                print(f"Loaded {len(cls._test_users)} users from users.json")
        except Exception as e:
            print(f"Error loading from users.json: {str(e)}")
        
        # If we still don't have users, create some test users
        if not cls._test_users:
            # Generate 10 test users
            for i in range(1, 11):
                cls._test_users.append({
                    'username': f"test_user{i}@example.com",
                    'password': f"password{i}"
                })
            print(f"Generated {len(cls._test_users)} test users")
            
            # Optionally save these to CSV for future use
            try:
                with open(users_file, 'w', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=['username', 'password'])
                    writer.writeheader()
                    for user in cls._test_users:
                        writer.writerow(user)
                print(f"Saved test users to {users_file}")
            except Exception as e:
                print(f"Error saving test users to CSV: {str(e)}")
    
    @classmethod
    def get_next_user(cls) -> Dict[str, str]:
        """
        Get the next user in a round-robin fashion
        """
        # Load users if not already loaded
        if not cls._test_users:
            cls.load_test_users()
            
        # Ensure we have users
        if not cls._test_users:
            # Fallback to default test user if no other users are available
            return {
                'username': "schen3@hamilton.edu",
                'password': "test123"
            }
        
        # Get next user and increment counter
        user = cls._test_users[cls._current_user_index]
        cls._current_user_index = (cls._current_user_index + 1) % len(cls._test_users)
        return user

    def __init__(self, *args, **kwargs):
        # Initialize the parent class first
        super().__init__(*args, **kwargs)
        # Get unique test credentials for this simulated user
        user_credentials = self.get_next_user()
        self.test_username = user_credentials['username']
        self.test_password = user_credentials['password']
        print(f"Initialized test user: {self.test_username}")
    
    def on_start(self):
        """
        Called when a Locust user starts. Performs login.
        Updated to properly handle Flask's login system.
        """
        print(f"User starting: attempting login as {self.test_username}")
        try:
            # First, get the login page to collect any necessary cookies
            self.client.get("/", name="/")
            
            # Now attempt login
            response = self.client.post("/login", json={
                "username": self.test_username,
                "password": self.test_password
            }, name="/login")

            # Check if login was successful by examining the response
            if response.status_code == 200:
                # Parse JSON response
                json_data = response.json()
                if json_data.get("success"):
                    print(f"Login successful for {self.test_username}")
                else:
                    print(f"Login failed for {self.test_username}: {json_data.get('message', 'Unknown error')}")
                    # Don't call response.failure directly, it's causing errors
            else:
                print(f"Login failed for {self.test_username}: Status {response.status_code}")

        except Exception as e:
            print(f"Login request exception for {self.test_username}: {str(e)}")


    @task(3) # Higher weight = more frequent task
    def view_question(self):
        """
        Simulates viewing a random question.
        Updated to use '/api/question/<q_id>' endpoint.
        """
        if not self.available_question_ids:
            print(f"User {self.test_username}: No question IDs configured.")
            return # Skip if no questions defined

        q_id = random.choice(self.available_question_ids)
        url = f"/api/question/{q_id}" # Corrected API endpoint
        print(f"User {self.test_username}: Viewing question {q_id}")
        try:
            with self.client.get(url, name="/api/question/[id]", catch_response=True) as response:
                if response.status_code != 200:
                    print(f"User {self.test_username}: Failed to view question {q_id} with status {response.status_code}")
                else:
                    print(f"User {self.test_username}: Successfully viewed question {q_id}")
        except Exception as e:
            print(f"User {self.test_username}: Exception when viewing question {q_id}: {str(e)}")


    @task(1) # Lower weight = less frequent task
    def submit_code(self):
        """
        Simulates submitting code for a random programming question.
        Updated to use '/api/save' endpoint with correct payload structure.
        """
        if not self.available_question_ids:
            print(f"User {self.test_username}: No question IDs configured.")
            return

        # Simply pick a random question - all questions appear to use the same endpoint
        q_id = random.choice(self.available_question_ids)

        # Simple placeholder code
        sample_code = f"print('Hello from {self.test_username} for question {q_id} at {random.random()}')" # Add randomness

        print(f"User {self.test_username}: Submitting code for question {q_id}")
        try:
            # Updated to match the actual endpoint and payload structure in app.py
            with self.client.post("/api/save", json={
                "questionId": q_id,  # This is the correct parameter name based on app.py
                "code": sample_code
            }, name="/api/save", catch_response=True) as response:
                if response.status_code != 200:
                    print(f"User {self.test_username}: Failed to submit code for question {q_id} with status {response.status_code}")
                else:
                    print(f"User {self.test_username}: Successfully submitted code for question {q_id}")
        except Exception as e:
            print(f"User {self.test_username}: Exception when submitting code for question {q_id}: {str(e)}")

    @task(2)
    def view_homepage(self):
        """
        Simulates viewing the main page (e.g., dashboard after login).
        Updated to use '/exam' endpoint which is the main exam interface.
        """
        print(f"User {self.test_username}: Viewing exam page")
        try:
            with self.client.get("/exam", name="/exam", catch_response=True) as response:
                if response.status_code != 200:
                    print(f"User {self.test_username}: Failed to view exam page with status {response.status_code}")
                else:
                    print(f"User {self.test_username}: Successfully viewed exam page")
                    # Update normal activity after viewing exam page
                    self.update_normal_activity()
        except Exception as e:
            print(f"User {self.test_username}: Exception when viewing exam page: {str(e)}")

    # Simulating the exam_monitor.js client-side activity reporting
    def report_suspicious_activity(self, activity_type, details=None):
        """
        Simulate client-side JavaScript reporting SUSPICIOUS activity to the monitoring system.
        This should only be used for activities that are considered suspicious.
        """
        if details is None:
            details = {}
            
        activity_data = {
            "type": activity_type,
            "timestamp": int(time.time() * 1000),  # JavaScript-style timestamp in milliseconds
            "username": self.test_username,
            **details
        }
        
        try:
            response = self.client.post(
                "/report_activity",
                json=activity_data,
                name="/report_activity"
            )
            if response.status_code == 200:
                print(f"Reported suspicious activity {activity_type} for {self.test_username}")
            else:
                print(f"Failed to report suspicious activity {activity_type}: {response.status_code}")
        except Exception as e:
            print(f"Exception reporting suspicious activity: {str(e)}")
            
    def update_normal_activity(self):
        """
        Simulate normal student activity using the batch endpoint
        This matches how exam_monitor.js sends regular, non-suspicious activities
        """
        # Generate some random normal events
        events = [
            {
                "action": "window_focus",
                "timestamp": int(time.time() * 1000) - random.randint(100, 5000),
                "timeAway": 0
            },
            {
                "action": "tab_visible",
                "timestamp": int(time.time() * 1000) - random.randint(100, 4000),
                "timeAway": random.randint(0, 2000)
            }
        ]
        
        # Note: Normal activities shouldn't include suspiciousActivities
        payload = {
            "username": self.test_username,
            "events": events,
            "suspiciousActivities": []  # No suspicious activities in regular update
        }
        
        try:
            response = self.client.post("/report_activity_batch", json=payload, name="/report_activity_batch")
            if response.status_code == 200:
                print(f"Updated normal activity for {self.test_username}")
            else:
                print(f"Failed to update normal activity: {response.status_code}")
        except Exception as e:
            print(f"Exception updating normal activity: {str(e)}")
    
    @task(1)
    def simulate_monitoring_activity(self):
        """
        Simulate student activity that would be captured by the monitoring system
        """
        # Mostly send normal activity updates
        if random.random() < 0.7:  # 70% chance to just send normal activity
            self.update_normal_activity()
            return
            
        # Otherwise, simulate suspicious activities (30% chance)
        suspicious_activity_types = [
            "tab_switch",
            "focus_lost",
            "excessive_copy_paste",
            "print_attempt"
        ]
        
        # Choose a random suspicious activity to simulate
        activity_type = random.choice(suspicious_activity_types)
        
        if activity_type == "tab_switch":
            self.report_suspicious_activity(activity_type, {
                "description": "Student switched away from exam tab"
            })
        elif activity_type == "focus_lost":
            self.report_suspicious_activity(activity_type, {
                "description": "Student switched to another application"
            })
        elif activity_type == "excessive_copy_paste":
            self.report_suspicious_activity(activity_type, {
                "count": random.randint(3, 10),
                "description": "Student performed multiple copy-paste actions"
            })
        elif activity_type == "print_attempt":
            self.report_suspicious_activity(activity_type, {
                "description": "Student attempted to print the exam"
            })

# Note: You might need other tasks, like viewing results, logging out, etc.
# Add more @task methods to this class for other actions students might take.
