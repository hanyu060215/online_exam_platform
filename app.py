from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os
import json
import markdown
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
import time
import pytz
import csv
from pyngrok import ngrok


app = Flask(__name__)
app.secret_key = 'secret-key'
login_manager = LoginManager()
login_manager.init_app(app)

# Global data store for monitoring student activities
monitoring_data = {}

def cleanup_monitoring_data():
    """
    Remove stale user data and limit the number of stored activities.
    Preserves users who are currently logged in.
    """
    current_time = datetime.now()
    stale_threshold = 60 * 60  # Increase to 60 minutes in seconds
    
    # Get list of currently active user IDs
    active_session_users = get_logged_in_users()
    
    # Find users to remove (inactive for more than the threshold and not currently logged in)
    users_to_remove = []
    for username, data in monitoring_data.items():
        # Skip users who are currently logged in - they are active by definition
        if username in active_session_users:
            print(f"Preserving active logged-in user: {username}")
            # Update their last_active time to ensure they don't get removed
            monitoring_data[username]['last_active'] = current_time.isoformat()
            continue
            
        try:
            if 'last_active' not in data:
                users_to_remove.append(username)
                continue
                
            last_active_str = data['last_active']
            last_active = datetime.fromisoformat(last_active_str)
            time_diff = (current_time - last_active).total_seconds()
            
            if time_diff > stale_threshold:
                print(f"User {username} inactive for {time_diff/60:.1f} minutes, marking for removal")
                users_to_remove.append(username)
        except (ValueError, TypeError) as e:
            print(f"Error processing user {username} timestamp: {e}")
            users_to_remove.append(username)
    
    # Remove stale users
    for username in users_to_remove:
        try:
            del monitoring_data[username]
            print(f"Removed stale user: {username}")
        except KeyError:
            pass
            
# Helper function to get currently logged in users
def get_logged_in_users():
    """Get a list of currently logged in users"""
    # This is a simplified approach - real implementations might vary based on session handling
    active_users = []
    if current_user and hasattr(current_user, 'id') and current_user.is_authenticated:
        active_users.append(current_user.id)
    return active_users
            
    # Limit activities for remaining users
    max_activities = 20
    for username, data in monitoring_data.items():
        if 'activities' in data and len(data['activities']) > max_activities:
            data['activities'] = sorted(
                data['activities'], 
                key=lambda x: x.get('timestamp', 0),
                reverse=True
            )[:max_activities]


# Set up command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--exam-duration', '-t', type=int, default=120,
                    help='exam duration in minutes', required=False)
parser.add_argument('--use-ngrok', action='store_true',
                    help='Use ngrok to make the app accessible from the internet')
args = parser.parse_args()
EXAM_DURATION_MINUTES: int = args.exam_duration


# Load users from JSON file
def load_users():
    """
    Load users from JSON file
    :return: None
    """
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Global exam configuration functions
def load_exam_config():
    """Load global exam configuration"""
    try:
        with open('exam_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Default configuration
        return {
            "global_exam_start_time": None,
            "global_exam_duration": 120,
            "exam_end_time": None,
            "timezone": "US/Eastern"
        }

def save_exam_config(config):
    """Save global exam configuration"""
    with open('exam_config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def get_student_allowed_start_time(student_duration, global_start_time, global_duration):
    """Calculate when a student can start based on their duration and global schedule"""
    if not global_start_time:
        return None
    
    # Parse global start time
    global_start_dt = datetime.fromisoformat(global_start_time)
    
    # Calculate how early they can start
    extra_minutes = student_duration - global_duration
    if extra_minutes > 0:
        # Student can start early
        allowed_start = global_start_dt - timedelta(minutes=extra_minutes)
    else:
        # Student starts at global time
        allowed_start = global_start_dt
    
    return allowed_start

def can_student_login_now(student_duration):
    """Check if a student can log in now based on global schedule"""
    config = load_exam_config()
    
    if not config.get('global_exam_start_time'):
        # No global schedule set, allow login
        return True, "No global exam schedule set"
    
    global_start_time = config['global_exam_start_time']
    global_duration = config['global_exam_duration']
    
    # Get student's allowed start time
    allowed_start = get_student_allowed_start_time(student_duration, global_start_time, global_duration)
    
    if not allowed_start:
        return True, "No restrictions"
    
    # Get current time in the same timezone
    tz = pytz.timezone(config.get('timezone', 'US/Eastern'))
    current_time = datetime.now(tz)
    
    # Make allowed_start timezone-aware if it isn't already
    if allowed_start.tzinfo is None:
        allowed_start = tz.localize(allowed_start)
    
    # Calculate exam end time
    global_start_dt = datetime.fromisoformat(global_start_time)
    if global_start_dt.tzinfo is None:
        global_start_dt = tz.localize(global_start_dt)
    exam_end_time = global_start_dt + timedelta(minutes=global_duration)
    
    if current_time < allowed_start:
        return False, f"You can start at {allowed_start.strftime('%Y-%m-%d %H:%M:%S')}"
    elif current_time > exam_end_time:
        return False, "Exam has ended"
    else:
        return True, "You can log in now"

# Load question from markdown file
def load_question(question_id: str):
    try:
        question_path = Path(f'questions/{question_id}.md')
        print(f"Attempting to load question from: {question_path}")  # Debug log
        
        if not question_path.exists():
            print(f"Question file not found: {question_path}")  # Debug log
            return None

        with open(question_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the markdown content to extract different sections
        sections = content.split('\n## ')
        if not sections:
            print(f"No sections found in {question_id}")
            return None

        # Get the title (first section)
        title = sections[0].strip('# \n')
        
        # Initialize variables
        question_type = 'programming'  # Default type
        description = ''
        initial_code = ''
        choices = []
        
        # Process each section
        for section in sections[1:]:  # Skip the title section
            section_content = section.strip()
            if not section_content:
                continue
                
            # Split section into header and content
            section_parts = section_content.split('\n', 1)
            if len(section_parts) < 2:
                continue
            
            header, content = section_parts
            header = header.strip()
            content = content.strip()
            print(f"[load_question - {question_id}] Processing section header: '{header}'") # DEBUG

            if header == 'Type':
                question_type = content.strip().lower()
            elif header == 'Description':
                description = content
            elif header == 'Initial Code':
                # Extract code between ```python and ``` markers
                # Improved parsing to be more flexible with the code block format
                try:
                    if '```python' in content:
                        code_parts = content.split('```python', 1)[1].split('```', 1)
                        initial_code = code_parts[0].strip()
                    elif '```' in content:  # Try generic code block if python-specific not found
                        code_parts = content.split('```', 1)[1].split('```', 1)
                        initial_code = code_parts[0].strip()
                    else:
                        # Fallback - take content as is if no code block markers found
                        initial_code = content.strip()
                except Exception as e:
                    print(f"[load_question - {question_id}] Error parsing Initial Code section: {str(e)}") # DEBUG
                    initial_code = ''
            elif header == 'Choices':
                # Make this work regardless of question type setting
                question_type = 'multiple_choice'  # Override type based on presence of choices
                choices = [line.strip()[2:].strip() for line in content.split('\n') 
                          if line.strip().startswith('-')]

        # Convert description to HTML
        description_html = markdown.markdown(
            description,
            extensions=['fenced_code', 'tables', 'codehilite']
        )

        result = {
            'title': title,
            'description': description_html,
            'type': question_type,
            'initial_code': initial_code if question_type == 'programming' else '',
            'choices': choices if question_type == 'multiple_choice' else []
        }
        
        print(f"[load_question - {question_id}] Successfully loaded question. Title: '{title}', Type: '{question_type}', Initial Code (first 20 chars): '{initial_code[:20]}...' ") # DEBUG
        return result
        
    except Exception as e:
        print(f"Error loading question {question_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_total_questions() -> int:
    questions_dir = Path('questions')
    if not questions_dir.exists():
        return 0
    return len(list(questions_dir.glob('Q*.md')))

class User(UserMixin):
    def __init__(self, username, user_data):
        self.id = username
        self.name = user_data.get('name', '')
        # Use the user-specific exam duration if available, otherwise use the default
        self.exam_duration = user_data.get('exam_duration', EXAM_DURATION_MINUTES)
        # Admin flag - default is False
        self.is_admin = user_data.get('is_admin', False)

@login_manager.user_loader
def load_user(username: str):
    users = load_users()
    if username in users:
        return User(username, users[username])

def verify_credentials(username: str, password: str) -> bool:
    users = load_users()
    if username in users:
        stored_password = users[username]['password']
        return check_password_hash(stored_password, password)
    return False

# Decorator for admin-required routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        elif not current_user.is_admin:
            return render_template('error.html', message="Access denied. Admin privileges required."), 403
        return f(*args, **kwargs)
    return decorated_function

# Decorator for student-only routes
def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        elif current_user.is_admin:
            return render_template('error.html', message="This page is for students only. Please use admin pages."), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')
        is_admin_login = data.get('is_admin_login', False)
        
        if verify_credentials(username, password):
            user_data = load_users().get(username, {})
            user = User(username, user_data)
            
            # Check if login type matches user type
            if is_admin_login != user.is_admin:
                message = 'This account does not have admin privileges.' if is_admin_login else 'Admin accounts must use the admin login.'
                return jsonify({
                    'success': False,
                    'message': message
                })
            
            login_user(user)
            
            # For students, check global timing restrictions
            if not user.is_admin:
                # Check if student can log in now based on global schedule
                can_login, message = can_student_login_now(user.exam_duration)
                
                if not can_login:
                    return jsonify({
                        'success': False,
                        'message': f'Login not allowed: {message}'
                    })
                
                # Set exam start time for global timing
                session['exam_start_time'] = int(time.time())
                session['student_id'] = username  # Store student ID for tracking
                
                # Log the exam start for this specific student
                print(f"Student {username} started exam at {datetime.fromtimestamp(session['exam_start_time'])}")
                print(f"Student {username} has {user.exam_duration} minutes for the exam")
                
                # Get global config for timing calculations
                config = load_exam_config()
                if config.get('global_exam_start_time'):
                    global_start_dt = datetime.fromisoformat(config['global_exam_start_time'])
                    global_duration = config['global_exam_duration']
                    exam_end_time = global_start_dt + timedelta(minutes=global_duration)
                    print(f"Global exam ends at: {exam_end_time}")
                
            return jsonify({
                'success': True,
                'is_admin': user.is_admin  # Return admin status to client
            })
        return jsonify({'success': False, 'message': 'Invalid username or password'})
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '')
        name = data.get('name', '')
        password = data.get('password', '')
        
        # Basic validation
        if not username or not name or not password:
            return jsonify({
                'success': False, 
                'message': 'All fields are required'
            })
        
        # Check if user already exists
        users = load_users()
        if username in users:
            return jsonify({
                'success': False, 
                'message': 'Username already exists'
            })
        
        # Add user to users.json
        hashed_password = generate_password_hash(password)
        users[username] = {
            'password': hashed_password,
            'name': name
        }
        
        try:
            # Save to users.json
            with open('users.json', 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=4)
                
            # Also add to new_users.csv for record keeping
            new_user_added = add_to_csv('new_users.csv', username, name, password)
            
            if not new_user_added:
                # If we couldn't add to CSV, still return success since the user is in users.json
                print(f"Warning: User {username} added to users.json but not to new_users.csv")
                
            return jsonify({
                'success': True, 
                'message': 'Account created successfully!'
            })
            
        except Exception as e:
            print(f"Error during signup: {str(e)}")
            return jsonify({
                'success': False, 
                'message': f'Error creating account: {str(e)}'
            })
    
    # GET request - render signup form
    return render_template('signup.html')

def add_to_csv(csv_path, username, name, password):
    """Add a new user to the CSV file"""
    try:
        # Check if file exists and has headers
        file_exists = os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0
        
        with open(csv_path, 'a', newline='') as csvfile:
            fieldnames = ['username', 'name', 'password']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header if file is new
            if not file_exists:
                writer.writeheader()
            
            # Write user data
            writer.writerow({
                'username': username,
                'name': name,
                'password': password  # Store plain password in CSV for admin reference
            })
        return True
    except Exception as e:
        print(f"Error adding user to CSV: {str(e)}")
        return False

@app.route('/exam')
@student_required
def exam():
    # No need to set exam start time here as it's set during login
    return render_template('exam.html')

@app.route('/api/question/<q_id>')
@student_required
def get_question(q_id):
    question = load_question(q_id)
    if question is None:
        print(f"Failed to load question {q_id}")  # Debug log
        return jsonify({'error': 'Question not found'}), 404

    response_data = {
        'question': question,
        'total_questions': get_total_questions()
    }

    # Determine question type to load appropriate saved answer
    q_type = question.get('type', 'programming') # Default to programming if type not found

    user_submission_dir = Path('submissions') / current_user.id
    
    if q_type == 'programming':
        saved_code = load_saved_code(current_user.id, q_id)
        response_data['saved_code'] = saved_code
    elif q_type == 'multiple_choice':
        answer_file = user_submission_dir / f"{q_id}.txt"
        if answer_file.exists():
            with open(answer_file, 'r', encoding='utf-8') as f:
                response_data['saved_choice'] = f.read().strip()
        else:
            response_data['saved_choice'] = None
    elif q_type == 'short_answer':
        answer_file = user_submission_dir / f"{q_id}.md"
        if answer_file.exists():
            with open(answer_file, 'r', encoding='utf-8') as f:
                response_data['saved_short_answer'] = f.read().strip()
        else:
            response_data['saved_short_answer'] = None

    print(f"Returning question data for {q_id}")  # Debug log
    return jsonify(response_data)

@app.route('/api/save', methods=['POST'])
@student_required
def save_answer():
    data = request.get_json()
    q_id = data.get('questionId')
    code = data.get('code')

    if not q_id or code is None:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    try:
        save_code_to_file(current_user.id, q_id, code)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/save_choice', methods=['POST'])
@student_required
def save_choice():
    data = request.get_json()
    q_id = data.get('questionId')
    selected_choice_letter = data.get('choice') # Client sends the selected letter, e.g., 'A'

    if not all([q_id, selected_choice_letter]):
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    try:
        # Create user's submission directory
        user_dir = os.path.join('submissions', current_user.id)
        os.makedirs(user_dir, exist_ok=True)
        
        # Save multiple choice answer to txt file
        answer_file = os.path.join(user_dir, f'{q_id}.txt')
        with open(answer_file, 'w', encoding='utf-8') as f:
            f.write(selected_choice_letter) # Save only the selected choice letter
            
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/save_short_answer', methods=['POST'])
@student_required
def save_short_answer():
    data = request.get_json()
    q_id = data.get('questionId')
    answer_text = data.get('answer') # Client sends 'answer'

    if not all([q_id, answer_text is not None]):
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    try:
        # Create user's submission directory
        user_dir = os.path.join('submissions', current_user.id)
        os.makedirs(user_dir, exist_ok=True)
        
        # Save short answer to md file (markdown format)
        answer_file = os.path.join(user_dir, f'{q_id}.md')
        with open(answer_file, 'w', encoding='utf-8') as f:
            f.write(answer_text)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/total_questions')
@login_required
def total_questions():
    return jsonify({'total': get_total_questions()})

@app.route('/api/session_state')
@login_required
def get_session_state():
    username = current_user.id
    user_dir = f'submissions/{username}'
    total_questions = get_total_questions()
    saved_answers = {}
    last_question = 'Q1'

    # Check each question for saved answers
    for i in range(1, total_questions + 1):
        q_id = f'Q{i}'
        
        # Check if question is saved
        file_path = os.path.join(user_dir, f'{q_id}.py')
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                saved_answers[q_id] = f.read()
            last_question = q_id  # Update last question to the latest one found

    # If no saved answers found, return default state
    if not saved_answers:
        return jsonify({
            'status': 'success',
            'username': username,
            'hasExistingSession': False,
            'lastQuestion': 'Q1',
            'savedAnswers': {}
        })

    return jsonify({
        'status': 'success',
        'username': username,
        'hasExistingSession': True,
        'lastQuestion': last_question,
        'savedAnswers': saved_answers
    })

@app.route('/api/exam_config')
@login_required
def get_exam_config():
    return jsonify({
        'status': 'success',
        'exam_duration': EXAM_DURATION_MINUTES, # Renamed from duration_minutes
        'exam_start_time': session.get('exam_start_time', None)
    })

@app.route('/api/check_time')
@login_required
def check_time():
    # Record exam start time if not already set (fallback)
    if 'exam_start_time' not in session:
        session['exam_start_time'] = int(time.time())
        session['student_id'] = current_user.id
        print(f"WARNING: Exam start time not set for {current_user.id}, setting now")
    
    config = load_exam_config()
    student_id = session.get('student_id', current_user.id)
    student_duration = current_user.exam_duration
    
    # Check if global timing is enabled
    if config.get('global_exam_start_time'):
        # Global timing mode: all students end at the same time
        global_start_dt = datetime.fromisoformat(config['global_exam_start_time'])
        global_duration = config['global_exam_duration']
        
        # Calculate global exam end time
        tz = pytz.timezone(config.get('timezone', 'US/Eastern'))
        if global_start_dt.tzinfo is None:
            global_start_dt = tz.localize(global_start_dt)
        
        global_end_time = global_start_dt + timedelta(minutes=global_duration)
        current_time_dt = datetime.now(tz)
        
        # Calculate remaining time until global end
        remaining_timedelta = global_end_time - current_time_dt
        remaining_time = int(remaining_timedelta.total_seconds())
        
        print(f"Global timing - Student {student_id}: {remaining_time//60}m {remaining_time%60}s until global end")
        
        if remaining_time <= 0:
            print(f"Global exam finished for student {student_id}")
            return jsonify({
                'remainingSeconds': 0,
                'examFinished': True,
                'examDuration': student_duration,
                'studentId': student_id,
                'globalTiming': True,
                'globalEndTime': global_end_time.isoformat()
            })
        
        return jsonify({
            'remainingSeconds': remaining_time,
            'examFinished': False,
            'examDuration': student_duration,
            'studentId': student_id,
            'globalTiming': True,
            'globalEndTime': global_end_time.isoformat()
        })
    
    else:
        # Individual timing mode (fallback)
        current_time = int(time.time())
        start_time = session.get('exam_start_time', current_time)
        elapsed_time = current_time - start_time
        
        remaining_time = student_duration * 60 - elapsed_time
        
        print(f"Individual timing - Student {student_id}: {remaining_time//60}m {remaining_time%60}s remaining")
        
        if remaining_time <= 0:
            print(f"Individual exam finished for student {student_id}")
            return jsonify({
                'remainingSeconds': 0,
                'examFinished': True,
                'examDuration': student_duration,
                'studentId': student_id,
                'globalTiming': False
            })
        
        return jsonify({
            'remainingSeconds': remaining_time,
            'examFinished': False,
            'examDuration': student_duration,
            'studentId': student_id,
            'globalTiming': False
        })

def save_code_to_file(username, q_id, code):
    """
    Save user's code to a file in their submission folder
    :param username: student's username
    :param q_id: question ID
    :param code: code to save
    """
    question = load_question(q_id)
    question_type = question['type'] if question else 'programming'
    
    # Create user directory with username as folder name
    user_dir = os.path.join('submissions', username)
    os.makedirs(user_dir, exist_ok=True)

    # Use appropriate extension based on question type
    if question_type == 'multiple_choice':
        file_path = os.path.join(user_dir, f'{q_id}.txt')
    elif question_type == 'short_answer':
        file_path = os.path.join(user_dir, f'{q_id}.md')
    else:
        file_path = os.path.join(user_dir, f'{q_id}.py')
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)

def load_saved_code(username, q_id):
    """
    Load user's saved code from their submission folder
    :param username: student's username
    :param q_id: question ID
    :return: saved code or initial code if no saved code exists
    """
    question = load_question(q_id)
    question_type = question['type'] if question else 'programming'
    
    # Create user directory if it doesn't exist
    user_dir = os.path.join('submissions', username)
    os.makedirs(user_dir, exist_ok=True)
    
    # Use appropriate extension based on question type
    if question_type == 'multiple_choice':
        file_path = os.path.join(user_dir, f'{q_id}.txt')
    elif question_type == 'short_answer':
        file_path = os.path.join(user_dir, f'{q_id}.md')
    else:
        file_path = os.path.join(user_dir, f'{q_id}.py')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # Return initial code for programming questions
        # For multiple choice and short answer, return empty string
        if question_type == 'programming':
            return question['initial_code'] if question else ''
        return ''

def saved_question(username):
    """
    Save student's code and multiple choice answers to submission folder when exam is submitted
    :param username: student's username
    """
    try:
        # Get timestamp for folder name
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Prepare submission info
        total_q = get_total_questions()
        submission_info = {
            'timestamp': timestamp,
            'username': username,
            'total_questions': total_q,
            'questions': {}
        }
        
        # Check if there are any answers to save
        has_answers = False
        
        # Create user directory in submissions folder
        user_dir = os.path.join('submissions', username)
        os.makedirs(user_dir, exist_ok=True)
        
        for q_id in range(1, total_q + 1):
            # Get question type and content
            question = load_question(f'Q{q_id}')
            if not question:
                continue
                
            try:
                if question['type'] == 'programming':
                    # Read programming answer
                    code_file = os.path.join(user_dir, f'Q{q_id}.py')
                    if os.path.exists(code_file):
                        with open(code_file, 'r') as f:
                            code = f.read().strip()
                        if code and code != question.get('initial_code', ''):
                            # We have a valid answer
                            has_answers = True
                            submission_info['questions'][f'q{q_id}'] = {
                                'type': 'programming',
                                'code': code
                            }
                
                elif question['type'] == 'multiple_choice':
                    # Read multiple choice answer
                    choice_file = os.path.join(user_dir, f'Q{q_id}.txt')
                    if os.path.exists(choice_file):
                        with open(choice_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if len(lines) >= 1:
                                choice_index = int(lines[0].strip())
                                choice_text = lines[1].strip() if len(lines) > 1 else ""
                                # We have a valid answer
                                has_answers = True
                                submission_info['questions'][f'q{q_id}'] = {
                                    'type': 'multiple_choice',
                                    'selected_index': choice_index,
                                    'selected_answer': choice_text
                                }
                
                elif question['type'] == 'short_answer':
                    # Read short answer
                    answer_file = os.path.join(user_dir, f'Q{q_id}.md')
                    if os.path.exists(answer_file):
                        with open(answer_file, 'r', encoding='utf-8') as f:
                            answer_text = f.read().strip()
                            if answer_text:
                                # We have a valid answer
                                has_answers = True
                                submission_info['questions'][f'q{q_id}'] = {
                                    'type': 'short_answer',
                                    'answer': answer_text
                                }
            
            except (FileNotFoundError, ValueError) as e:
                print(f"Error processing question {q_id}: {str(e)}")
                continue
        
        # Only save submission info if we have answers
        if has_answers:
            # Save submission info to JSON file
            info_file = os.path.join(user_dir, 'submission_info.json')
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(submission_info, f, indent=4)
        
        return True
    except Exception as e:
        print(f"Error saving questions: {str(e)}")
        return False

# Activity monitoring routes

@app.route('/report_activity', methods=['POST'])
@login_required
def report_activity():
    """Record a single suspicious activity"""
    if not current_user.is_authenticated:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 403
        
    try:
        activity_data = request.json
        if not activity_data or not isinstance(activity_data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid activity data'}), 400
            
        username = current_user.id
        
        # Initialize user data if not exists
        if username not in monitoring_data:
            monitoring_data[username] = {
                'activities': [],
                'last_active': datetime.now().isoformat(),
                'events_count': 0
            }
        
        # Validate required fields
        if 'type' not in activity_data or not activity_data['type']:
            activity_data['type'] = 'unknown'
            
        # Add timestamp if not provided or convert millisecond JS timestamp to ISO format
        current_time = datetime.now()
        if 'timestamp' not in activity_data:
            activity_data['timestamp'] = current_time.isoformat()
        else:
            timestamp = activity_data['timestamp']
            if isinstance(timestamp, (int, float)):
                # Convert milliseconds to datetime
                try:
                    if timestamp > 1000000000000:  # Looks like a JS timestamp (milliseconds)
                        dt = datetime.fromtimestamp(timestamp / 1000)
                        activity_data['timestamp'] = dt.isoformat()
                except (ValueError, TypeError, OverflowError):
                    activity_data['timestamp'] = current_time.isoformat()
                    
        # Ensure description exists
        if 'description' not in activity_data or not activity_data['description']:
            activity_data['description'] = f"{activity_data['type']} activity detected"
            
        # Add activity to user's record
        monitoring_data[username]['activities'].append(activity_data)
        monitoring_data[username]['events_count'] += 1
        monitoring_data[username]['last_active'] = current_time.isoformat()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error recording activity: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/report_activity_batch', methods=['POST'])
@login_required
def report_activity_batch():
    """Record multiple activities in a batch"""
    if not current_user.is_authenticated:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 403
        
    try:
        batch_data = request.json
        if not batch_data or not isinstance(batch_data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid batch data'}), 400
            
        username = current_user.id
        current_time = datetime.now()
        
        # Initialize user data if not exists
        if username not in monitoring_data:
            monitoring_data[username] = {
                'activities': [],
                'last_active': current_time.isoformat(),
                'events_count': 0
            }
        
        # Update last active time
        monitoring_data[username]['last_active'] = current_time.isoformat()
        
        # Process normal events (just count them)
        events = batch_data.get('events', [])
        if isinstance(events, list):
            event_count = len(events)
            if event_count > 0:
                monitoring_data[username]['events_count'] += event_count
        
        # Process suspicious activities if present
        suspicious_activities = batch_data.get('suspiciousActivities', [])
        if isinstance(suspicious_activities, list) and suspicious_activities:
            for activity in suspicious_activities:
                if not isinstance(activity, dict):
                    continue
                    
                # Validate required fields
                if 'type' not in activity or not activity['type']:
                    activity['type'] = 'unknown'
                    
                # Process timestamp
                if 'timestamp' not in activity:
                    activity['timestamp'] = current_time.isoformat()
                else:
                    timestamp = activity['timestamp']
                    if isinstance(timestamp, (int, float)):
                        # Convert milliseconds to datetime
                        try:
                            if timestamp > 1000000000000:  # Looks like a JS timestamp
                                dt = datetime.fromtimestamp(timestamp / 1000)
                                activity['timestamp'] = dt.isoformat()
                        except (ValueError, TypeError, OverflowError):
                            activity['timestamp'] = current_time.isoformat()
                            
                # Ensure description exists
                if 'description' not in activity or not activity['description']:
                    activity['description'] = f"{activity['type']} activity detected"
                    
                # Add to user's record
                monitoring_data[username]['activities'].append(activity)
        
        # Run cleanup periodically
        if random.random() < 0.1:  # 10% chance to run cleanup with each batch
            cleanup_monitoring_data()
            
        return jsonify({'status': 'success', 'recorded': True})
    except Exception as e:
        print(f"Error recording activity batch: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Admin routes
@app.route('/admin/add_user', methods=['POST'])
@admin_required
def add_user():
    data = request.get_json()
    if not data or not all(k in data for k in ('username', 'password', 'name')):
        return jsonify({'status': 'error', 'message': 'Missing required fields'})
    
    username = data['username']
    password = data['password']
    name = data['name']
    
    users = load_users()
    
    if username in users:
        return jsonify({'status': 'error', 'message': 'Username already exists'})
    
    # Hash the password
    hashed_password = generate_password_hash(password)
    
    # Add user to users dictionary
    users[username] = {
        'password': hashed_password,
        'name': name
    }
    
    # Save to file
    try:
        with open('users.json', 'w') as f:
            json.dump(users, f, indent=4)
        return jsonify({'status': 'success', 'message': 'User added successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/manage_durations', methods=['GET', 'POST'])
@admin_required
def manage_durations():
    
    users = load_users()
    
    if request.method == 'POST':
        try:
            data = request.form
            
            # Update duration for each user (excluding admin accounts)
            for username in users.keys():
                # Skip admin accounts - they don't take exams
                if users[username].get('is_admin', False):
                    continue
                    
                duration_key = f"duration_{username}"
                if duration_key in data and data[duration_key].strip():
                    try:
                        # Convert to integer and ensure it's positive
                        duration = int(data[duration_key])
                        if duration > 0:
                            if 'exam_duration' not in users[username]:
                                users[username]['exam_duration'] = duration
                            else:
                                users[username]['exam_duration'] = duration
                    except ValueError:
                        pass  # Skip invalid entries
            
            # Save updated users to file
            with open('users.json', 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=4)
                
            return render_template('admin_durations.html', users=users, message="Student exam durations updated successfully!", EXAM_DURATION_MINUTES=EXAM_DURATION_MINUTES)
        except Exception as e:
            return render_template('admin_durations.html', users=users, error=str(e), EXAM_DURATION_MINUTES=EXAM_DURATION_MINUTES)
    
    # GET request - display the form
    return render_template('admin_durations.html', users=users, EXAM_DURATION_MINUTES=EXAM_DURATION_MINUTES)

@app.route('/admin/exam_status')
@admin_required
def exam_status():
    """Show current exam timing status for all students"""
    users = load_users()
    student_status = []
    
    # Get current active sessions and their timing info
    for username, user_data in users.items():
        if not user_data.get('is_admin', False):
            status = {
                'username': username,
                'name': user_data.get('name', username),
                'exam_duration': user_data.get('exam_duration', EXAM_DURATION_MINUTES),
                'is_active': False,
                'exam_start_time': None,
                'remaining_time': None,
                'exam_finished': False
            }
            
            # Check if student is currently logged in (this is a simplified check)
            # In a real implementation, you might want to track active sessions more precisely
            student_status.append(status)
    
    return render_template('admin_exam_status.html', 
                         students=student_status, 
                         EXAM_DURATION_MINUTES=EXAM_DURATION_MINUTES)

@app.route('/admin/global_timing', methods=['GET', 'POST'])
@admin_required
def global_timing():
    """Manage global exam timing settings"""
    config = load_exam_config()
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        try:
            # Parse the datetime input
            exam_date = data.get('exam_date')
            exam_time = data.get('exam_time')
            exam_duration = int(data.get('exam_duration', 120))
            
            if exam_date and exam_time:
                # Combine date and time
                exam_datetime_str = f"{exam_date} {exam_time}"
                exam_datetime = datetime.strptime(exam_datetime_str, '%Y-%m-%d %H:%M')
                
                # Make it timezone-aware
                tz = pytz.timezone(config.get('timezone', 'US/Eastern'))
                exam_datetime = tz.localize(exam_datetime)
                
                # Calculate exam end time
                exam_end_time = exam_datetime + timedelta(minutes=exam_duration)
                
                # Update configuration
                config['global_exam_start_time'] = exam_datetime.isoformat()
                config['global_exam_duration'] = exam_duration
                config['exam_end_time'] = exam_end_time.isoformat()
                
                save_exam_config(config)
                
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'message': 'Global exam timing updated successfully',
                        'exam_start': exam_datetime.isoformat(),
                        'exam_end': exam_end_time.isoformat()
                    })
                else:
                    return render_template('admin_global_timing.html', 
                                         config=config, 
                                         success="Global exam timing updated successfully")
            else:
                # Clear global timing
                config['global_exam_start_time'] = None
                config['exam_end_time'] = None
                save_exam_config(config)
                
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'message': 'Global exam timing cleared'
                    })
                else:
                    return render_template('admin_global_timing.html', 
                                         config=config, 
                                         success="Global exam timing cleared")
                
        except ValueError as e:
            error_msg = f"Invalid date/time format: {str(e)}"
            if request.is_json:
                return jsonify({'success': False, 'message': error_msg})
            else:
                return render_template('admin_global_timing.html', 
                                     config=config, 
                                     error=error_msg)
    
    # GET request - show the form
    return render_template('admin_global_timing.html', config=config)

@app.route('/admin/monitoring', methods=['GET'])
@admin_required
def admin_monitoring():
    """Admin dashboard to monitor student activity during exams"""
    return render_template('admin_monitoring.html', monitoring_data=monitoring_data)

def get_name_from_email(email):
    """Get user's name from new_users.csv, or extract from email if not found"""
    import csv
    import os
    
    if not email or '@' not in email:
        return email
        
    # First try to find the actual name in new_users.csv
    try:
        if os.path.exists('new_users.csv'):
            with open('new_users.csv', 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get('username') == email and row.get('name'):
                        return row['name']
    except Exception:
        # If any error occurs reading the CSV, fall back to email extraction
        pass
        
    # Fall back to extracting name from email
    username = email.split('@')[0]
    
    if '.' in username:
        name_parts = username.split('.')
        name = ' '.join(part.capitalize() for part in name_parts)
    else:
        # Try to find name patterns in the username
        import re
        name_parts = re.findall('[A-Z][^A-Z]*', username.capitalize())
        if len(name_parts) > 1:
            name = ' '.join(name_parts)
        else:
            name = username.capitalize()
    
    return name

@app.route('/admin/monitoring/data', methods=['GET'])
@admin_required
def admin_monitoring_data():
    """API endpoint to get real-time monitoring data"""
    # Clean up stale data first
    cleanup_monitoring_data()
    
    # Format data for easy consumption by the dashboard
    formatted_data = []
    current_time = datetime.now()
    
    for username, data in monitoring_data.items():
        # Skip users with invalid data structure
        if not isinstance(data, dict):
            continue
            
        # Extract name from email for display
        display_name = get_name_from_email(username)
            
        user_data = {
            'username': username,
            'displayName': display_name,
            'lastActive': data.get('last_active', ''),
            'eventsCount': data.get('events_count', 0),
            'activities': []
        }
        
        # Get suspicious activities
        valid_activities = []
        for activity in data.get('activities', []):
            # Verify we have a valid activity object
            if not isinstance(activity, dict):
                continue
                
            # Convert JS timestamp (milliseconds) to ISO format if needed
            timestamp = activity.get('timestamp', '')
            try:
                if isinstance(timestamp, (int, float)) and timestamp > 1000000000000:  # Looks like a JS timestamp
                    timestamp_dt = datetime.fromtimestamp(timestamp / 1000)
                    timestamp = timestamp_dt.isoformat()
            except (ValueError, TypeError, OverflowError):
                # If conversion fails, just use the original value
                pass
                
            # Make sure we have a valid activity type
            activity_type = activity.get('type', 'unknown')
            if not activity_type or not isinstance(activity_type, str):
                activity_type = 'unknown'
                
            valid_activities.append({
                'type': activity_type,
                'timestamp': timestamp,
                'description': activity.get('description', 'No description')
            })
            
        # Sort by timestamp with newest first
        user_data['activities'] = sorted(
            valid_activities,
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )
        
        formatted_data.append(user_data)
    
    return jsonify(formatted_data)

# Admin cleanup route removed - no longer needed

@app.route('/exam/summary')
@login_required
def exam_summary():
    username = current_user.id
    user_dir = f'submissions/{username}'
    total_questions_ = get_total_questions()
    questions = []
    unsaved_questions = []

    # Create questions list
    for i in range(1, total_questions_ + 1):
        question_id = f'Q{i}'
        questions.append({'id': question_id, 'number': i})
        
        # Get question type
        question = load_question(question_id)
        question_type = question['type'] if question else 'programming'
        
        # Check if question is saved based on its type
        if question_type == 'multiple_choice':
            file_path = os.path.join(user_dir, f'{question_id}.txt')
        elif question_type == 'short_answer':
            file_path = os.path.join(user_dir, f'{question_id}.md')
        else:
            file_path = os.path.join(user_dir, f'{question_id}.py')
            
        if not os.path.exists(file_path):
            unsaved_questions.append(question_id)

    return render_template('summary.html', questions=questions, unsaved_questions=unsaved_questions)

@app.route('/finish_exam', methods=['POST'])
@student_required
def finish_exam():
    try:
        if not current_user.is_authenticated:
            return jsonify({
                'status': 'error',
                'message': 'Please log in to submit your exam.'
            })
        
        # 保存所有答案
        if saved_question(current_user.id):
            session['exam_submitted'] = True
            session['exam_force_submitted'] = False  # Regular submission
            
            # Check if this is an AJAX request (from JavaScript)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'success',
                    'message': 'Exam submitted successfully!'
                })
            else:
                # For form submissions, render the congratulations page
                return render_template('congrats.html')
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save your answers. Please try again.'
            })
    except Exception as e:
        print(f"ERROR in finish_exam: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'An error occurred while submitting your exam: {str(e)}'
        })

@app.route('/force_submit_exam', methods=['POST'])
@student_required
def force_submit_exam():
    try:
        # Parse request data
        data = request.get_json()
        username = data.get('username', '')
        violations_count = data.get('violations', 0)

        
        # Validate username (required)
        if not username:
            return jsonify({
                'status': 'error',
                'message': 'Username is required'
            }), 400
        
        # Log the forced submission event
        app.logger.warning(f"Forced exam submission for {username} due to {violations_count} violations")
        
        # Record the violation in monitoring data
        if username in monitoring_data:
            if 'violations' not in monitoring_data[username]:
                monitoring_data[username]['violations'] = 0
            monitoring_data[username]['violations'] = violations_count
        
        # Save the student's answers as they currently are
        if saved_question(username):
            # Set session variables if it's the current user
            if current_user.is_authenticated and current_user.id == username:
                session['exam_submitted'] = True
                session['exam_force_submitted'] = True
            
            return jsonify({
                'status': 'success',
                'message': 'Exam force-submitted successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save exam answers during force submission'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error during force submit: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }), 500

@app.route('/exam_force_submitted')
def exam_force_submitted():
    """Display a page indicating the exam was force-submitted due to violations"""
    # Set the exam as submitted in session if not already done
    if not session.get('exam_submitted', False):
        session['exam_submitted'] = True
        session['exam_force_submitted'] = True
        
    return render_template('force_submitted.html')

@app.route('/exam_completed')
@login_required
def exam_completed():
    """Display the congratulations page after exam completion"""
    # Ensure the exam is marked as submitted in the session
    if not session.get('exam_submitted', False):
        session['exam_submitted'] = True
        
    return render_template('congrats.html')

if __name__ == '__main__':
    # When running locally this will be used
    # On PythonAnywhere, the WSGI file will use the 'app' object directly
    
    # Set up the port for the Flask app
    port = 5004
    
    # Run the Flask app on network interface
    print("\n=======================================")
    print("Flask app running on your network:")
    print("=======================================")
    import socket
    
    # Get all available IP addresses
    def get_ip_addresses():
        ip_addresses = []
        try:
            # Get all network interfaces
            interfaces = socket.getaddrinfo(socket.gethostname(), None)
            for interface in interfaces:
                ip = interface[4][0]
                # Filter out IPv6 and loopback addresses
                if not ip.startswith('127.') and ':' not in ip:
                    ip_addresses.append(ip)
            # If we didn't find any, try another method
            if not ip_addresses:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    # Doesn't actually connect
                    s.connect(('8.8.8.8', 1))
                    ip = s.getsockname()[0]
                    if ip and not ip.startswith('127.'):
                        ip_addresses.append(ip)
                except:
                    pass
                finally:
                    s.close()
        except:
            pass
        return ip_addresses
    
    # Display all possible URLs students can use
    ip_addresses = get_ip_addresses()
    if ip_addresses:
        print(" * Access URLs for students:")
        for ip in ip_addresses:
            print(f" * http://{ip}:{port}")
    else:
        print(" * Could not determine network IP. Try accessing with IP shown below.")
    print("=======================================\n")
    
    # Run the Flask app
    app.run(debug=True, port=port, host='0.0.0.0')
