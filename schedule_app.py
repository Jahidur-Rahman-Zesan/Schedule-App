import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import matplotlib.pyplot as plt
import re


# CSV filenames for storing user, todo, and schedule data
USERS_FILE = "users.csv"
TODO_FILE = "todo_tasks.csv"
SCHEDULE_FILE = "schedule_tasks.csv"
VERIFICATION_CODE_FILE = "verification_codes.csv"

# Email configuration for the app's email
APP_EMAIL = "xyz@email.com"  # Use your app-specific email here
APP_PASSWORD = "xyz"  # Use your app-specific password here (App Password for Gmail)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Hash password for secure storage
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Ensure the necessary CSV files exist
def ensure_csv_exists(filename, columns):
    if not os.path.exists(filename):
        pd.DataFrame(columns=columns).to_csv(filename, index=False)

# Ensure the user accounts CSV file exists
def ensure_users_file():
    ensure_csv_exists(USERS_FILE, ["Email", "Password"])

# Ensure the verification codes CSV file exists
def ensure_verification_code_file():
    ensure_csv_exists(VERIFICATION_CODE_FILE, ["Email", "VerificationCode", "Timestamp"])

# Send verification code to email
def send_verification_code(email, code):
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your Verification Code"
        message["From"] = APP_EMAIL
        message["To"] = email

        text = f"Hi there,\n\nYour verification code is {code}. Please enter this code in the app to complete your registration. The code is valid for 5 minutes."
        part1 = MIMEText(text, "plain")
        message.attach(part1)

        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(APP_EMAIL, APP_PASSWORD)
            server.sendmail(APP_EMAIL, email, message.as_string())

        st.success(f"Verification code sent to {email}")
    except Exception as e:
        st.error(f"Error sending verification code: {e}")

# Register new user after verification
def register_user(email, password, code_entered):
    ensure_users_file()
    ensure_verification_code_file()

    users_df = pd.read_csv(USERS_FILE)
    codes_df = pd.read_csv(VERIFICATION_CODE_FILE)
    hashed_password = hash_password(password)

    # Check if email already exists in users
    if email in users_df["Email"].values:
        st.error("User already exists.")
        return False

    # Check if the verification code matches and is still valid (within 5 minutes)
    code_entry = codes_df[codes_df["Email"] == email]
    
    if not code_entry.empty:
        saved_code = str(code_entry["VerificationCode"].iloc[0]).strip()
        timestamp = pd.to_datetime(code_entry["Timestamp"].iloc[0])
        current_time = datetime.now()
        code_entered_cleaned = code_entered.strip()

        if saved_code == code_entered_cleaned and current_time <= timestamp + timedelta(minutes=5):
            # Add the user to the users CSV
            new_user = pd.DataFrame({"Email": [email], "Password": [hashed_password]})
            users_df = pd.concat([users_df, new_user], ignore_index=True)
            users_df.to_csv(USERS_FILE, index=False)

            # Remove the verification code after successful registration
            codes_df = codes_df[codes_df["Email"] != email]
            codes_df.to_csv(VERIFICATION_CODE_FILE, index=False)

            st.success("User account created!")
            return True
        else:
            if saved_code != code_entered_cleaned:
                st.error("The verification code you entered is incorrect.")
            elif current_time > timestamp + timedelta(minutes=5):
                st.error("The verification code has expired.")
            return False
    else:
        st.error("No verification code found for this email.")
        return False

# Registration Page with Email Verification
def registration_page():
    st.title("Register")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Send Verification Code"):
        if email and password:
            ensure_verification_code_file()
            codes_df = pd.read_csv(VERIFICATION_CODE_FILE)

            # Generate a verification code
            verification_code = str(random.randint(100000, 999999))
            send_verification_code(email, verification_code)

            # Check if the email already exists in the verification codes file
            existing_code = codes_df[codes_df["Email"] == email]
            if not existing_code.empty:
                # If the email already has a code, update it
                codes_df.loc[codes_df["Email"] == email, "VerificationCode"] = verification_code
                codes_df.loc[codes_df["Email"] == email, "Timestamp"] = datetime.now()
            else:
                # Otherwise, add a new entry
                new_entry = pd.DataFrame({"Email": [email], "VerificationCode": [verification_code], "Timestamp": [datetime.now()]})
                codes_df = pd.concat([codes_df, new_entry], ignore_index=True)

            codes_df.to_csv(VERIFICATION_CODE_FILE, index=False)
        else:
            st.error("Please enter your email and password.")

    verification_code_entered = st.text_input("Enter Verification Code")

    if st.button("Complete Registration"):
        if email and password and verification_code_entered:
            if register_user(email, password, verification_code_entered):
                st.success("Registration complete! Please log in.")
        else:
            st.error("Please fill out all fields.")

# To-Do List Functions
def load_todo_tasks():
    ensure_csv_exists(TODO_FILE, ["Email", "Task", "Deadline", "Status", "Time Needed", "Priority", "Reminder"])
    return pd.read_csv(TODO_FILE)

def save_todo_task(email, task, deadline, status, time_needed, priority, reminder):
    todo_df = load_todo_tasks()
    new_task = pd.DataFrame({"Email": [email], "Task": [task], "Deadline": [deadline], 
                             "Status": [status], "Time Needed": [time_needed], 
                             "Priority": [priority], "Reminder": [reminder]})
    todo_df = pd.concat([todo_df, new_task], ignore_index=True)
    todo_df.to_csv(TODO_FILE, index=False)

def update_task(email, task, new_status, new_time_needed=None):
    todo_df = load_todo_tasks()
    if new_time_needed is not None:
        todo_df.loc[(todo_df['Email'] == email) & (todo_df['Task'] == task), ['Status', 'Time Needed']] = [new_status, new_time_needed]
    else:
        todo_df.loc[(todo_df['Email'] == email) & (todo_df['Task'] == task), 'Status'] = new_status
    todo_df.to_csv(TODO_FILE, index=False)

def delete_todo_task(email, task):
    todo_df = load_todo_tasks()
    todo_df = todo_df[(todo_df['Email'] != email) | (todo_df['Task'] != task)]
    todo_df.to_csv(TODO_FILE, index=False)

# Send email reminders for tasks
def send_email_reminder(email, task, deadline):
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = f"Reminder: Task '{task}' deadline approaching"
        message["From"] = APP_EMAIL
        message["To"] = email

        text = f"Hi,\n\nThis is a reminder that your task '{task}' is due on {deadline}. Please complete it soon."
        part1 = MIMEText(text, "plain")
        message.attach(part1)

        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(APP_EMAIL, APP_PASSWORD)
            server.sendmail(APP_EMAIL, email, message.as_string())

        st.success(f"Reminder email sent to {email}")
    except Exception as e:
        st.error(f"Error sending reminder email: {e}")

# Schedule Functions
def load_schedule_tasks():
    ensure_csv_exists(SCHEDULE_FILE, ["Email", "Task", "Day", "Time From", "Time To"])
    return pd.read_csv(SCHEDULE_FILE)

# Check if a task overlaps with an existing task
def check_overlap(email, day, time_from, time_to):
    schedule_df = load_schedule_tasks()
    day_tasks = schedule_df[(schedule_df["Day"] == day) & (schedule_df["Email"] == email)]
    time_from_dt = datetime.strptime(time_from, "%I:%M %p")
    time_to_dt = datetime.strptime(time_to, "%I:%M %p")
    for _, task in day_tasks.iterrows():
        task_start = datetime.strptime(task["Time From"], "%I:%M %p")
        task_end = datetime.strptime(task["Time To"], "%I:%M %p")
        if not (time_to_dt <= task_start or time_from_dt >= task_end):
            return True
    return False

def save_schedule_task(email, task, day, time_from, time_to):
    if check_overlap(email, day, time_from, time_to):
        st.error(f"Task overlaps with another task on {day}. Please select a different time.")
    else:
        schedule_df = load_schedule_tasks()
        new_task = pd.DataFrame({"Email": [email], "Task": [task], "Day": [day], 
                                 "Time From": [time_from], "Time To": [time_to]})
        schedule_df = pd.concat([schedule_df, new_task], ignore_index=True)
        schedule_df.to_csv(SCHEDULE_FILE, index=False)

def delete_schedule_task(email, task, day):
    schedule_df = load_schedule_tasks()
    schedule_df = schedule_df[(schedule_df['Email'] != email) | (schedule_df['Task'] != task) | (schedule_df['Day'] != day)]
    schedule_df.to_csv(SCHEDULE_FILE, index=False)

# Suggested Schedule: Add To-Do List tasks to available time slots in daily schedule
def add_todo_tasks_to_schedule(email):
    todo_df = load_todo_tasks()
    schedule_df = load_schedule_tasks()
    user_tasks = todo_df[todo_df["Email"] == email]
    
    suggested_schedule = {}
    time_per_day_per_task = {}

    # Iterate through each task
    for index, row in user_tasks.iterrows():
        task = row["Task"]
        time_needed = row["Time Needed"]
        deadline = pd.to_datetime(row["Deadline"])
        days_until_deadline = (deadline - pd.Timestamp.now()).days
        
        # Divide time needed by (days until deadline - 2) for review
        if days_until_deadline > 2:
            time_per_day = time_needed // (days_until_deadline - 2)
        else:
            time_per_day = time_needed
        
        time_per_day_per_task[task] = time_per_day

        # Find free time slots for each day of the week (prioritize afternoon)
        available_slots = {}
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            afternoon_slots = find_free_time_slots(schedule_df, time_per_day, email, day, prefer_afternoon=True)
            if afternoon_slots:
                available_slots[day] = afternoon_slots
            else:
                morning_slots = find_free_time_slots(schedule_df, time_per_day, email, day, prefer_afternoon=False)
                available_slots[day] = morning_slots
        
        # Store the suggested schedule for each task
        suggested_schedule[task] = available_slots
    
    # Display the suggested schedule to the user with selectable boxes
    st.subheader("Suggested Schedule")
    selected_slots = {}
    used_time_slots = {}

    for task, day_slots in suggested_schedule.items():
        st.write(f"Task: {task}")
        selected_slots[task] = {}
        for day, slots in day_slots.items():
            if slots:
                # Create time options and avoid previously selected times
                available_slots = [f"{slot.strftime('%I:%M %p')} - {(slot + timedelta(minutes=time_per_day_per_task[task])).strftime('%I:%M %p')}" for slot in slots if slot not in used_time_slots]
                selected_slot = st.selectbox(f"Select time for {task} on {day}", available_slots, key=f"{task}_{day}")
                selected_slots[task][day] = selected_slot
                # Track the selected time slots to prevent overlap
                used_time_slots[selected_slot] = (task, day)

    # Button to add the selected tasks to the schedule
    if st.button("Add Selected Tasks to Daily Schedule"):
        for task, day_slots in selected_slots.items():
            for day, time in day_slots.items():
                time_from_str, time_to_str = time.split(" - ")
                time_from = datetime.strptime(time_from_str, '%I:%M %p')
                time_to = datetime.strptime(time_to_str, '%I:%M %p')
                save_schedule_task(email, task, day, time_from.strftime("%I:%M %p"), time_to.strftime("%I:%M %p"))
        st.success("Selected tasks have been added to your schedule!")

# Find free time slots in the schedule for a specific day, with an option to prioritize afternoon
def find_free_time_slots(schedule_df, time_needed, email, day, prefer_afternoon=True):
    day_tasks = schedule_df[(schedule_df["Day"] == day) & (schedule_df["Email"] == email)]
    
    # If no tasks are scheduled for this day, return a free slot starting from the desired time
    start_time = "12:00 PM" if prefer_afternoon else "09:00 AM"
    if day_tasks.empty:
        return [datetime.strptime(start_time, "%I:%M %p")]
    
    free_time_slots = []
    end_of_previous_task = datetime.strptime(start_time, "%I:%M %p")
    
    # Sort tasks by start time
    day_tasks = day_tasks.sort_values("Time From")
    
    for _, task in day_tasks.iterrows():
        start_of_next_task = datetime.strptime(task["Time From"], "%I:%M %p")
        free_time = (start_of_next_task - end_of_previous_task).total_seconds() / 60
        if free_time >= time_needed:
            free_time_slots.append(end_of_previous_task)
        end_of_previous_task = datetime.strptime(task["Time To"], "%I:%M %p")
    
    # Check if there is free time after the last task of the day
    end_of_day = datetime.strptime("06:00 PM", "%I:%M %p")
    free_time_after_last_task = (end_of_day - end_of_previous_task).total_seconds() / 60
    if free_time_after_last_task >= time_needed:
        free_time_slots.append(end_of_previous_task)
    
    return free_time_slots

# Convert minutes to hours and minutes for display
def format_time(minutes):
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m" if hours else f"{remaining_minutes}m"

# Parse time needed in human-readable format (hours, minutes)
def parse_time_needed(time_string):
    time_match = re.match(r"(?:(\d+)h)?\s*(?:(\d+)m)?", time_string)
    if time_match:
        hours = int(time_match.group(1)) if time_match.group(1) else 0
        minutes = int(time_match.group(2)) if time_match.group(2) else 0
        return hours * 60 + minutes  # Return the total time in minutes
    else:
        return 0  # Default to 0 if parsing fails

# Visualization functions
def visualize_status(tasks, title):
    st.subheader(f"{title} Task Status Distribution")
    if not tasks.empty:
        status_counts = tasks["Status"].value_counts()
        fig, ax = plt.subplots()
        ax.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')
        st.pyplot(fig)

# Visualization of working time per day of the week
def visualize_weekly_working_time(schedule_tasks):
    st.subheader("Weekly Working Time Overview")

    # Ensure the schedule is not empty
    if schedule_tasks.empty:
        st.write("No tasks scheduled for the week.")
        return

    # Convert "Time From" and "Time To" to datetime objects to calculate time duration
    schedule_tasks['Time From'] = pd.to_datetime(schedule_tasks['Time From'], format='%I:%M %p')
    schedule_tasks['Time To'] = pd.to_datetime(schedule_tasks['Time To'], format='%I:%M %p')

    # Calculate the duration of each task in hours
    schedule_tasks['Task Duration'] = (schedule_tasks['Time To'] - schedule_tasks['Time From']).dt.total_seconds() / 3600

    # Group by day of the week and sum the task durations to get total working time per day
    working_time_per_day = schedule_tasks.groupby('Day')['Task Duration'].sum()

    # Plot the working time for each day of the week
    fig, ax = plt.subplots()
    working_time_per_day.plot(kind="bar", color="blue", ax=ax)

    ax.set_xlabel("Days of the Week")
    ax.set_ylabel("Total Working Time (hours)")
    ax.set_title("Working Time on Each Day of the Week")
    
    st.pyplot(fig)
    
# To-Do List Page
def todo_page():
    email = st.session_state.get("email")
    if not email:
        st.error("You need to log in first!")
        return
    st.title("To-Do List")
    
    task = st.text_input("Task")
    deadline = st.date_input("Deadline")
    status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
    time_needed = st.number_input("Time Needed (in minutes)", min_value=15, step=15)
    priority = st.selectbox("Priority", ["High", "Medium", "Low"])
    reminder = st.checkbox("Set Email Reminder")

    if st.button("Add Task"):
        if task.strip() == "":
            st.error("Task name cannot be empty!")
        else:
            save_todo_task(email, task, deadline, status, time_needed, priority, reminder)
            st.success("Task Added")
            st.experimental_set_query_params(tasks_updated="true")
            
            # Schedule the reminder email if set
            if reminder:
                send_email_reminder(email, task, deadline)

    st.header("Current To-Do Tasks")
    todo_tasks = load_todo_tasks()

    user_tasks = todo_tasks[todo_tasks["Email"] == email].drop(columns=['Email'])
    
    if not user_tasks.empty:
        user_tasks["Time Needed"] = user_tasks["Time Needed"].apply(format_time)
        user_tasks.index = user_tasks.index + 1
        st.write(user_tasks)

        task_to_update = st.selectbox("Select Task to Update", user_tasks["Task"])
        
        # Ensure the selected task exists before updating or deleting it
        if not user_tasks[user_tasks["Task"] == task_to_update].empty:
            new_status = st.selectbox("New Status", ["Pending", "In Progress", "Completed"])
            current_time_needed = parse_time_needed(user_tasks[user_tasks["Task"] == task_to_update]["Time Needed"].iloc[0])
            additional_time_needed = st.number_input("New Time Needed (in minutes)", min_value=15, step=15, value=max(15, current_time_needed))
            if st.button("Update Task"):
                update_task(email, task_to_update, new_status, additional_time_needed)
                st.success(f"Task '{task_to_update}' updated.")
                st.experimental_set_query_params(tasks_updated="true")
        
        task_to_delete = st.selectbox("Select Task to Delete", user_tasks["Task"], key="delete_task")
        if st.button("Delete Task"):
            delete_todo_task(email, task_to_delete)
            st.success(f"Task '{task_to_delete}' Deleted.")
            st.experimental_set_query_params(tasks_updated="true")

# Schedule Page
def schedule_page():
    email = st.session_state.get("email")
    if not email:
        st.error("You need to log in first!")
        return
    st.title("Daily Schedule")
    
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    for day in days_of_week:
        st.subheader(f"Schedule for {day}")
        
        schedule_tasks = load_schedule_tasks()
        user_schedule = schedule_tasks[(schedule_tasks["Email"] == email) & (schedule_tasks["Day"] == day)]
        
        # Sort the tasks by 'Time From' in ascending order (handling times in AM/PM format)
        if not user_schedule.empty:
            user_schedule['Time From'] = pd.to_datetime(user_schedule['Time From'], format="%I:%M %p")
            user_schedule = user_schedule.sort_values(by="Time From")
            
            # Reset index starting from 1
            user_schedule.index = range(1, len(user_schedule) + 1)
            
            # Convert 'Time From' back to 12-hour AM/PM format for display
            user_schedule['Time From'] = user_schedule['Time From'].dt.strftime("%I:%M %p")
            
            # Remove the 'Email' column before displaying
            user_schedule = user_schedule.drop(columns=['Email'])
            st.write(user_schedule)
        
        # Input fields for adding tasks
        task = st.text_input(f"Task for {day}", key=f"task_{day}")
        time_from = st.time_input(f"Start Time for {day} (AM/PM)", key=f"time_from_{day}")
        time_to = st.time_input(f"End Time for {day} (AM/PM)", key=f"time_to_{day}")
        
        if task and time_from and time_to:
            if st.button(f"Add Task for {day}", key=f"add_{day}"):
                save_schedule_task(email, task, day, time_from.strftime("%I:%M %p"), time_to.strftime("%I:%M %p"))
                st.success(f"Task added for {day}.")
                st.experimental_set_query_params(schedule_updated="true")
        else:
            st.warning("Please provide both task name and time frame.")
        
        # Task deletion
        task_to_delete = st.selectbox(f"Select Task to Delete for {day}", user_schedule["Task"], key=f"delete_task_{day}")
        if st.button(f"Delete Task for {day}", key=f"delete_{day}"):
            delete_schedule_task(email, task_to_delete, day)
            st.success(f"Task '{task_to_delete}' deleted for {day}.")
            st.experimental_set_query_params(schedule_updated="true")

    # Suggested schedule to add tasks
    st.header("Suggested Schedule")
    if st.button("Suggest and Add To-Do List Tasks to Free Time"):
        add_todo_tasks_to_schedule(email)
        st.experimental_set_query_params(schedule_updated="true")

# Visualization Page
def visualization_page():
    email = st.session_state.get("email")
    if not email:
        st.error("You need to log in first!")
        return
    st.title("Task Progress Visualizations")
    
    todo_tasks = load_todo_tasks()
    
    user_tasks = todo_tasks[todo_tasks["Email"] == email].drop(columns=['Email'])
    if not user_tasks.empty:
        visualize_status(user_tasks, "To-Do")

    schedule_tasks = load_schedule_tasks()
    user_schedule = schedule_tasks[schedule_tasks["Email"] == email].drop(columns=['Email'])
    if not user_schedule.empty:
        visualize_weekly_working_time(user_schedule)

# Login Page
def login_page():
    st.title("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if validate_user(email, password):
            st.session_state["email"] = email
            st.success(f"Logged in as {email}")
            st.experimental_set_query_params(logged_in="true")
        else:
            st.error("Invalid email or password.")

# Validate user credentials during login
def validate_user(email, password):
    ensure_users_file()
    users_df = pd.read_csv(USERS_FILE)
    hashed_password = hash_password(password)

    # Check if the user exists
    user = users_df[(users_df["Email"] == email) & (users_df["Password"] == hashed_password)]
    if not user.empty:
        return True
    return False

# Main app navigation
def main():
    if "email" not in st.session_state:
        login_or_register = st.sidebar.selectbox("Login or Register", ["Login", "Register"])
        if login_or_register == "Login":
            login_page()
        else:
            registration_page()
    else:
        st.sidebar.title("Navigation")
        page = st.sidebar.selectbox("Go to", ["To-Do List", "Daily Schedule", "Visualizations"])
        if page == "To-Do List":
            todo_page()
        elif page == "Daily Schedule":
            schedule_page()
        elif page == "Visualizations":
            visualization_page()

if __name__ == "__main__":
    main()

