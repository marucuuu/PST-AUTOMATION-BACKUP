import os
import shutil
import smtplib
import ssl
import time
import subprocess
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# === Configuration and Paths ===

# Base user directory (typically C:\Users\<username>)
base_dir = os.path.join(os.environ.get('HOMEDRIVE', 'C:'), os.environ.get('HOMEPATH', '\\Users\\Default'))

# Source location of Outlook PST files
source_path = os.path.join(base_dir, "Documents", "Outlook Files")

# Backup destination folder
backup_path = os.path.join(base_dir, "Desktop", "PST", "Backup")

# Log file to track script activity
log_file = os.path.join(backup_path, "BackupLog.txt")

# Path to the script or executable that should be scheduled
script_path = os.path.join(base_dir, "Desktop", "pstbackup", "smartpst.exe")

# Task Scheduler name for the job
task_name = "PSTBackup"

# Maximum retry attempts on backup failure
max_retries = 3           # Total number of retry attempts
wait_seconds = 10         # Time to wait between retries (in seconds)

retry_count = 0
backup_success = False

# Email configuration for alerts
smtp_server = "acescredit.ph"
smtp_port = 587
smtp_user = "test@acescredit.ph"
smtp_password = "Test_1223!!!!"
email_to = "test@acescredit.ph"

# === Logging Function ===

def log(message):
    """Logs a message with a timestamp to the log file and prints to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"{timestamp} - {message}\n")
    print(message)

# === Email Notification Function ===

def send_email(subject, body):
    """Sends an email with the given subject and body."""
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email_to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        log("Email notification sent to IT department.")
    except Exception as e:
        log(f"ERROR: Failed to send email notification. {e}")

# === Task Scheduler Function ===

def schedule_task(run_date, run_time):
    """Schedules the backup script using Windows Task Scheduler."""
    try:
        # Delete existing task (if exists)
        subprocess.call(f'schtasks /delete /tn "{task_name}" /f', shell=True)

        # Create new scheduled task
        command = (
            f'schtasks /create /tn "{task_name}" /tr "{script_path}" '
            f'/sc once /st {run_time} /sd {run_date} /rl highest'
        )
        subprocess.call(command, shell=True)
    except Exception as e:
        log(f"ERROR: Failed to schedule task. {e}")
        send_email("ALERT: Task Scheduling Failed", f"An error occurred during scheduling: {e}")

# === File Locator ===

def find_pst_file(path):
    """Finds and returns the first PST file in the given directory."""
    try:
        for file in os.listdir(path):
            if file.endswith(".pst"):
                return os.path.join(path, file)
    except Exception as e:
        log(f"ERROR: Could not list PST files in {path}. {e}")
    return None

# === Backup Function ===

def backup():
    """Attempts to back up the PST file with retries and logs the result."""
    global retry_count, backup_success

    pst_file = find_pst_file(source_path)
    if not pst_file:
        log("No .pst file found in the source directory.")
        return

    # Ensure the backup directory exists
    os.makedirs(backup_path, exist_ok=True)

    while retry_count < max_retries:
        try:
            # Create a timestamped backup file
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            destination_file = os.path.join(backup_path, f"backup_{timestamp}.pst")

            # Copy the PST file to backup location
            shutil.copy2(pst_file, destination_file)
            log("SUCCESS: Backup completed.")
            backup_success = True
            break
        except Exception as e:
            retry_count += 1
            log(f"Backup failed. Retry {retry_count} of {max_retries}. Error: {e}")

            if retry_count >= max_retries:
                log("FAILED: Backup failed after maximum retries.")
                send_email(
                    "ALERT: PST Backup Failed",
                    f"The backup of the PST file failed after {max_retries} attempt(s) on {datetime.now()}.\n"
                    f"Please check the log at {log_file}."
                )
            else:
                log(f"Retrying in {wait_seconds} seconds...")
                time.sleep(wait_seconds)

# === Main Execution ===

if __name__ == "__main__":
    backup()

    # Set target time for next run (12:00 noon)
    now = datetime.now()
    scheduled_time = datetime.strptime("12:00", "%H:%M").time()

    if backup_success:
        # If backup succeeded, schedule next run in 30 days
        next_run = (now + timedelta(days=30)).replace(hour=scheduled_time.hour, minute=scheduled_time.minute, second=0, microsecond=0)
        msg = "TASK SCHEDULED: Next monthly run."
    else:
        # If failed, retry the next day
        next_run = (now + timedelta(days=1)).replace(hour=scheduled_time.hour, minute=scheduled_time.minute, second=0, microsecond=0)
        msg = "TASK SCHEDULED: Retry tomorrow due to failure."

    # Schedule the next run
    schedule_task(next_run.strftime("%m/%d/%Y"), next_run.strftime("%H:%M"))
    log(msg)
