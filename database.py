import sqlite3

def init_db():
    """Initializes the database and creates tables with the new schema."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        ''')
        
        # Updated tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                description TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                due_date TEXT,
                priority TEXT DEFAULT 'Medium',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

def add_user(user_id, username):
    """Adds a new user to the database if they don't already exist."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))

def add_task(user_id, description, priority='Medium', due_date=None):
    """Adds a new task for a specific user with optional details."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO tasks (user_id, description, priority, due_date) VALUES (?, ?, ?, ?)',
            (user_id, description, priority, due_date)
        )

def get_tasks(user_id, completed=0):
    """Retrieves tasks for a user."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT task_id, description, priority, due_date FROM tasks WHERE user_id = ? AND completed = ? ORDER BY task_id',
            (user_id, completed)
        )
        return cursor.fetchall()

def search_tasks(user_id, keyword):
    """Searches for tasks containing a keyword for a specific user."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT task_id, description, priority, due_date FROM tasks WHERE user_id = ? AND completed = 0 AND description LIKE ?",
            (user_id, f'%{keyword}%')
        )
        return cursor.fetchall()

def edit_task_description(task_id, new_description):
    """Updates the description of a specific task."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET description = ? WHERE task_id = ?', (new_description, task_id))
        return cursor.rowcount > 0

def delete_task(task_id):
    """Deletes a specific task from the database."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
        return cursor.rowcount > 0

def complete_task(task_id):
    """Marks a specific task as completed."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET completed = 1 WHERE task_id = ?', (task_id,))
        return cursor.rowcount > 0

# --- Admin Functions (This is the missing part) ---

def get_all_users():
    """Admin: Retrieves all users from the database."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username FROM users')
        return cursor.fetchall()

def delete_user_and_tasks(user_id):
    """Admin: Deletes a user and all of their associated tasks."""
    with sqlite3.connect('todo_bot.db') as conn:
        cursor = conn.cursor()
        # Delete user's tasks first
        cursor.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
        # Then delete the user
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        return cursor.rowcount > 0