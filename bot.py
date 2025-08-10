import logging
import re
import os # <-- ADDED: To read environment variables
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
)
import database as db

# --- CONFIGURATION (UPDATED FOR DEPLOYMENT) ---
# The bot now reads the token from the environment variable set on the server
BOT_TOKEN = os.getenv("BOT_TOKEN")

# It reads the admin ID from the environment variable and converts it to an integer.
# It defaults to 0 if the variable is not found (useful for local testing).
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Conversation States ---
(SELECT_TASK_TO_DELETE, CONFIRM_DELETE,
 SELECT_TASK_TO_EDIT, GET_NEW_DESCRIPTION) = range(4)

# --- Helper Functions ---
def is_admin(user_id: int) -> bool:
    """Check if a user is the admin."""
    return user_id == ADMIN_ID

def format_task_list(tasks):
    """Helper to format a list of tasks for display."""
    if not tasks:
        return "You have no active tasks! ✨"
    
    message = "Your To-Do List:\n"
    for i, (task_id, desc, prio, due) in enumerate(tasks):
        details = []
        if prio and prio.lower() != 'medium':
            details.append(f"P:{prio}")
        if due:
            details.append(f"Due:{due}")
        
        details_str = f" ({', '.join(details)})" if details else ""
        message += f"{i + 1}. {desc}{details_str}\n"
    return message

# --- Reminder Callback Function ---
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """The function that is called by the job queue to send the reminder."""
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"🔔 Reminder: {job.data['reminder_text']}")

# --- Regular Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username)
    await update.message.reply_text(f"Hello, {user.first_name}! I am your advanced To-Do List Bot. Use /help to see all commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_commands = (
        "--- User Commands ---\n"
        "/addtask <desc> [p:priority] [due:YYYY-MM-DD]\n"
        "/viewtasks - See your active tasks\n"
        "/donetask <task_num> - Mark a task as complete\n"
        "/edittask - Edit a task's description\n"
        "/deletetask - Delete a task\n"
        "/search <keyword> - Search your tasks\n"
        "/remind <time> <unit> <message> - Set a reminder\n"
        "/myid - Get your Telegram User ID"
    )
    admin_commands = (
        "\n\n--- Admin Commands ---\n"
        "/viewusers - See all users of the bot\n"
        "/deleteuser <user_id> - Delete a user and all their tasks"
    )
    message = user_commands
    if is_admin(update.effective_user.id):
        message += admin_commands
    await update.message.reply_text(message)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A command to help the user find their own ID for the ADMIN_ID variable."""
    await update.message.reply_text(f"Your Telegram User ID is: `{update.effective_user.id}`")

async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /addtask <description> [p:priority] [due:YYYY-MM-DD]")
        return
    
    full_text = " ".join(context.args)
    priority_match = re.search(r"p:(\w+)", full_text, re.IGNORECASE)
    due_date_match = re.search(r"due:(\d{4}-\d{2}-\d{2})", full_text, re.IGNORECASE)
    
    priority = priority_match.group(1) if priority_match else 'Medium'
    due_date = due_date_match.group(1) if due_date_match else None
    
    description = re.sub(r"p:\w+", "", full_text, flags=re.IGNORECASE).strip()
    description = re.sub(r"due:\d{4}-\d{2}-\d{2}", "", description, flags=re.IGNORECASE).strip()
    
    if not description:
        await update.message.reply_text("Error: Task description cannot be empty after parsing details.")
        return

    db.add_task(user_id, description, priority, due_date)
    await update.message.reply_text(f"✅ Task added: '{description}'")

async def view_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_tasks(update.effective_user.id)
    message = format_task_list(tasks)
    await update.message.reply_text(message)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /search <keyword>")
        return
    keyword = " ".join(context.args)
    tasks = db.search_tasks(update.effective_user.id, keyword)
    if not tasks:
        await update.message.reply_text(f"No tasks found containing '{keyword}'.")
        return
    message = f"Search results for '{keyword}':\n" + format_task_list(tasks)
    await update.message.reply_text(message)

async def done_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /donetask <task_number>"); return
    try:
        task_num = int(context.args[0])
        user_tasks = db.get_tasks(update.effective_user.id)
        if 0 < task_num <= len(user_tasks):
            task_id_to_complete = user_tasks[task_num - 1][0]
            if db.complete_task(task_id_to_complete):
                 await update.message.reply_text(f"🎉 Great job! Task {task_num} marked as complete.")
            else: await update.message.reply_text("Something went wrong.")
        else: await update.message.reply_text("Invalid task number.")
    except ValueError: await upda
