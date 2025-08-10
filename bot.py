import logging
import re
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
)
import database as db

# --- CONFIGURATION ---
# Replace with your actual token from BotFather
BOT_TOKEN = "8101778705:AAHq_DrlSxspU4p2vXJPma0eweVsQtQenN4"

# IMPORTANT: Get your user ID by sending /myid to the bot and replace 0 with your ID
ADMIN_ID = 1214705672 

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
        # Only show priority if it's not the default 'Medium'
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
    except ValueError: await update.message.reply_text("Please enter a valid number."); return

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_message.chat_id
    try:
        time_value = int(context.args[0])
        time_unit = context.args[1].lower()
        reminder_text = " ".join(context.args[2:])

        if time_value <= 0:
            await update.effective_message.reply_text("Time must be a positive number."); return
        if not reminder_text:
            await update.effective_message.reply_text("You must provide a reminder message."); return

        if time_unit in ("s", "sec", "second", "seconds"): delay_seconds = time_value
        elif time_unit in ("m", "min", "minute", "minutes"): delay_seconds = time_value * 60
        elif time_unit in ("h", "hr", "hour", "hours"): delay_seconds = time_value * 3600
        else: await update.effective_message.reply_text("Invalid time unit. Use seconds, minutes, or hours."); return

        context.job_queue.run_once(send_reminder, delay_seconds, chat_id=chat_id, name=str(chat_id), data={'reminder_text': reminder_text})
        await update.effective_message.reply_text(f"OK! I will remind you in {time_value} {time_unit}.")
    except (IndexError, ValueError):
        await update.effective_message.reply_text("Usage: /remind <time> <unit> <message>\nExample: /remind 10 minutes My meeting is starting")

# --- Conversation Handlers ---
async def delete_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_tasks(update.effective_user.id)
    if not tasks: await update.message.reply_text("You have no tasks to delete."); return ConversationHandler.END
    context.user_data['tasks_for_action'] = tasks
    message = "Which task do you want to delete?\n" + format_task_list(tasks)
    await update.message.reply_text(message + "\nPlease send the task number.")
    return SELECT_TASK_TO_DELETE

async def select_task_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_num = int(update.message.text)
        tasks = context.user_data['tasks_for_action']
        if 0 < task_num <= len(tasks):
            task_to_delete = tasks[task_num - 1]
            context.user_data['task_to_delete'] = task_to_delete
            await update.message.reply_text(f"Are you sure you want to delete '{task_to_delete[1]}'? (yes/no)")
            return CONFIRM_DELETE
        else: await update.message.reply_text("Invalid number. Please try again or type /cancel."); return SELECT_TASK_TO_DELETE
    except ValueError: await update.message.reply_text("That's not a number. Please send a number or type /cancel."); return SELECT_TASK_TO_DELETE

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() == 'yes':
        task_id = context.user_data['task_to_delete'][0]
        if db.delete_task(task_id): await update.message.reply_text("Task deleted successfully.")
        else: await update.message.reply_text("Could not delete the task.")
    else: await update.message.reply_text("Deletion cancelled.")
    context.user_data.clear(); return ConversationHandler.END

async def edit_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_tasks(update.effective_user.id)
    if not tasks: await update.message.reply_text("You have no tasks to edit."); return ConversationHandler.END
    context.user_data['tasks_for_action'] = tasks
    message = "Which task do you want to edit?\n" + format_task_list(tasks)
    await update.message.reply_text(message + "\nPlease send the task number.")
    return SELECT_TASK_TO_EDIT

async def select_task_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_num = int(update.message.text)
        tasks = context.user_data['tasks_for_action']
        if 0 < task_num <= len(tasks):
            task_to_edit = tasks[task_num - 1]
            context.user_data['task_to_edit'] = task_to_edit
            await update.message.reply_text(f"Editing task: '{task_to_edit[1]}'.\nPlease send the new description.")
            return GET_NEW_DESCRIPTION
        else: await update.message.reply_text("Invalid number. Please try again or type /cancel."); return SELECT_TASK_TO_EDIT
    except ValueError: await update.message.reply_text("That's not a number. Please send a number or type /cancel."); return SELECT_TASK_TO_EDIT

async def get_new_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_description = update.message.text; task_id = context.user_data['task_to_edit'][0]
    if db.edit_task_description(task_id, new_description): await update.message.reply_text("Task updated successfully!")
    else: await update.message.reply_text("Failed to update task.")
    context.user_data.clear(); return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear(); await update.message.reply_text("Action cancelled."); return ConversationHandler.END

# --- Admin Command Handlers ---
async def view_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command."); return
    users = db.get_all_users()
    if not users: await update.message.reply_text("No users found."); return
    
    message = "Bot Users:\n"
    for user_id, username in users:
        safe_username = (username or "N/A").replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
        message += f"\\- {safe_username} \\(ID: `{user_id}`\\)\n"
        
    await update.message.reply_text(message, parse_mode='MarkdownV2')

async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command."); return
    if not context.args:
        await update.message.reply_text("Usage: /deleteuser <user_id>"); return
    try:
        user_id_to_delete = int(context.args[0])
        if user_id_to_delete == ADMIN_ID:
            await update.message.reply_text("You cannot delete yourself."); return
        if db.delete_user_and_tasks(user_id_to_delete):
            await update.message.reply_text(f"Successfully deleted user {user_id_to_delete} and all their tasks.")
        else: await update.message.reply_text(f"User {user_id_to_delete} not found.")
    except ValueError:
        await update.message.reply_text("Please provide a valid numeric User ID.")

def main():
    if ADMIN_ID == 0:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! WARNING: ADMIN_ID is not set in bot.py.               !!!")
        print("!!! You will not be able to use admin commands.           !!!")
        print("!!! Run the bot, send /myid to it, and set the ADMIN_ID.  !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    
    db.init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    delete_conv_handler = ConversationHandler(entry_points=[CommandHandler("deletetask", delete_task_start)], states={SELECT_TASK_TO_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_task_to_delete)], CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete)],}, fallbacks=[CommandHandler("cancel", cancel)],)
    edit_conv_handler = ConversationHandler(entry_points=[CommandHandler("edittask", edit_task_start)], states={SELECT_TASK_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_task_to_edit)], GET_NEW_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_description)],}, fallbacks=[CommandHandler("cancel", cancel)],)
    
    application.add_handler(delete_conv_handler)
    application.add_handler(edit_conv_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("addtask", add_task_command))
    application.add_handler(CommandHandler("viewtasks", view_tasks_command))
    application.add_handler(CommandHandler("donetask", done_task_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("remind", remind_command))
    
    # Admin command handlers with aliases
    application.add_handler(CommandHandler("viewusers", view_users_command))
    application.add_handler(CommandHandler("viewuser", view_users_command)) # Alias
    application.add_handler(CommandHandler("deleteuser", delete_user_command))

    print("Bot is polling...")
    application.run_polling()

if __name__ == "__main__":
    main()