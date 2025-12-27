# Student Online Code Test

A comprehensive online platform for conducting programming exams and assessments. This application supports Python coding questions, multiple-choice questions, and short-answer questions, with built-in monitoring features to ensure academic integrity.

## Table of Contents
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [User Management](#user-management)
- [Question Management](#question-management)

## System Requirements

- Python 3.9 or higher
- Flask and related dependencies (see requirements.txt)
- Modern web browser (Chrome, Firefox, Safari, or Edge)
- Network connectivity for multi-user access

## Installation

1. Clone or download this repository to your local machine

2. Create a virtual enviroment:
   ```bash
   python3 -m venv env
   ```

3. Activate the virtual enviroment:
   ```bash
   source env/bin/activate
   ```

4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Ensure the following directories exist (create them if they don't):
   - `questions/` - For storing exam questions
   - `submissions/` - For storing student submissions
   - `static/` - Contains CSS, JavaScript, and other static files
   - `templates/` - Contains HTML templates

6. Run the program:
   ```bash
   python app.py
   ```

## Configuration

### User Configuration

Users are stored in the `users.json` file. The default format is:

```json
{
    "username@domain.com": {
        "password": "hashed_password",
        "name": "User Name",
        "exam_duration": 120,
        "is_admin": false
    }
}
```

Admin users should have the `is_admin` field set to `true`.


## Running the Application

1. Start the application with default settings (120 minutes exam duration):
   ```bash
   python app.py
   ```

2. Start with a custom exam duration (e.g., 60 minutes):
   ```bash
   python app.py -t 60
   ```

4. Once started, the application will display available URLs for access. By default, it runs on port 5004.

## User Management

### Adding New Users

1. **Manual Method**: Edit the `users.json` file directly
2. **Sign-up Page**: Users can register at `/signup`
3. **Admin Interface**: Admins can manage users through the admin interface
4. **CSV Import**: Use the `add_users_from_csv.py` script to bulk import users

### User Roles

- **Student**: Regular users who take exams
- **Admin**: Users with administrative privileges who can monitor exams and manage settings

### Admin User Management

#### Adding Admin Users

There are several ways to grant admin privileges to users:

1. **Using the set_admin.py script** (Recommended):
   ```bash
   # Grant admin privileges to a user
   python set_admin.py set username@domain.com
   
   # List all users and their admin status
   python set_admin.py list
   ```

2. **Manual method** - Edit `users.json` directly:
   ```json
   {
       "username@domain.com": {
           "password": "hashed_password",
           "name": "User Name",
           "exam_duration": 120,
           "is_admin": true
       }
   }
   ```
   Set the `is_admin` field to `true` for admin users.

#### Removing Admin Users

1. **Using the set_admin.py script** (Recommended):
   ```bash
   # Remove admin privileges from a user
   python set_admin.py unset username@domain.com
   ```

2. **Manual method** - Edit `users.json` directly:
   Set the `is_admin` field to `false` or remove it entirely.

#### Admin Script Usage

The `set_admin.py` script provides the following commands:

```bash
python set_admin.py list                   # List all users and their admin status
python set_admin.py set <username>         # Grant admin privileges to user
python set_admin.py unset <username>       # Remove admin privileges from user
python set_admin.py help                   # Show help message
```

#### Bulk User Creation

For creating multiple users at once:

1. **From CSV file**: Use `add_users_from_csv.py`
   - Create a CSV file with format: `username,name,password`
   - Run: `python add_users_from_csv.py`

2. **Test users**: Use `create_test_users.py` for load testing
   - Run: `python create_test_users.py`

**Note**: Users created through CSV import or test user scripts will have regular user privileges by default. Use the `set_admin.py` script to grant admin privileges afterward.

## Question Management

### Adding New Questions

1. Create markdown files in the `questions/` directory following the naming convention: `Q1.md`, `Q2.md`, `Q3.md`, etc.

2. Each question file should include the following sections:

   - **Title** (H1): The title of the question
   - **Type** (H2): Question type (programming, multiple_choice, or short_answer)
   - **Description** (H2): A detailed description of the problem
   - **Examples** (H2): Example inputs and outputs
     - **Example 1** (H3): First example with code blocks
     - Additional examples as needed
   - **Initial Code** (H2): For programming questions, starter code in a code block
   - **Notes** (H2): Any constraints or additional information

3. For multiple-choice questions, include a **Choices** section with numbered options.

### Example Question Format

```markdown
# Print Hello World

## Type
programming

## Description
Write a Python function that prints "Hello, World!" to the console.

## Examples

### Example 1
```python
print_hello()
```
Output:
```
Hello, World!
```

## Initial Code
```python
def print_hello():
    # Your code here
    pass
```

## Notes
Do not modify the function name.
```

## Admin Features

### Exam Duration Management

Admins can adjust exam durations for individual students:

1. Navigate to `/admin/manage_durations`
2. Set custom durations for each student
3. Save changes

### Student Monitoring

The monitoring system tracks student activity during exams:

1. Navigate to `/admin/monitoring`
2. View real-time student activities
3. Monitor for suspicious behavior
4. Force-submit exams if necessary

Monitored activities include:
- Tab switching
- Window focus changes
- Copy/paste operations
- Extended absences

## Student Experience

### Taking an Exam

1. Log in with student credentials
2. Navigate through questions using the Next/Previous buttons
3. For programming questions:
   - Write code in the editor
   - Code is auto-saved periodically
4. For multiple-choice questions:
   - Select the appropriate option
5. For short-answer questions:
   - Type your answer in the text area
6. Submit the exam using the "Finish Exam" button

### Time Management

- A timer displays the remaining exam time
- When time expires, the exam is automatically submitted
- A warning appears when less than 5 minutes remain

## Security Features

- **Auto-submission**: Exams are automatically submitted when time expires
- **Activity Monitoring**: Suspicious activities are logged and can trigger warnings
- **Force Submission**: Repeated violations can cause automatic exam submission
- **Session Management**: Prevents unauthorized access to exam