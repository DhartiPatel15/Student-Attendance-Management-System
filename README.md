# Student Attendance Management System

A responsive Flask web application for managing student records and daily attendance. The project includes separate Faculty/Admin and Student portals.

**Live demo:** https://student-attendance-management-system-6y21.onrender.com  
**Source code:** https://github.com/DhartiPatel15/Student-Attendance-Management-System

## Features

### Faculty / Admin portal
- Admin sign-in and sign-out
- Dashboard with student totals and today's attendance summary
- Add, search, edit and delete student records
- Download a CSV template, import students from CSV, and export the student directory
- Mark or update Present/Absent attendance for a selected date
- Date-range attendance reports with CSV export

### Student portal
- Student account registration and sign-in
- A personal dashboard with attendance percentage and Present/Absent totals
- Personal attendance history only; students cannot access faculty pages or other students' records
- Existing faculty-created student records can be activated using the registered roll number and matching email

## Technology stack

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, Jinja templates
- **Data import/export:** CSV
- **Deployment:** Render with Gunicorn

## Run locally on Windows

1. Install Python 3.10 or newer.
2. Download or clone this repository.
3. Open the project folder.
4. Double-click `START.bat`.
5. Open http://127.0.0.1:5000 in your browser.

The launcher creates a virtual environment and installs the required packages on first run. The SQLite database is created automatically.

Alternatively, run the commands below from the project folder:

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

## Demo faculty login

- **Username:** `admin`
- **Password:** `admin123`

This is a demonstration account, not a production credential. Do not use the demo credentials or public demo with real student information.

## CSV format

The student import CSV must contain these column headers:

```csv
roll_no,name,course,semester,email
```

The email column is optional. Each row must include roll number, name, course and semester. Duplicate roll numbers and incomplete rows are skipped during import.

## Database and deployment notes

- The app creates `attendance.db` automatically.
- The local database file is excluded from Git using `.gitignore`.
- On hosting platforms, a local SQLite file may be temporary and may be reset when the service is redeployed or its instance is replaced. For reliable long-term hosted data, configure persistent storage or migrate to a managed database.
- Set a strong `SECRET_KEY` and replace the demo admin credentials through environment variables before any real-world use.
- Use fictional sample student records in the public demo. Do not upload real student personal information.

## Project structure

```text
Student-Attendance-Management-System/
├── app.py
├── requirements.txt
├── Procfile
├── START.bat
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── students.html
│   ├── edit_student.html
│   ├── attendance.html
│   ├── reports.html
│   ├── student_login.html
│   ├── student_register.html
│   ├── student_dashboard.html
│   └── student_attendance.html
└── static/
    └── dark-theme-v3.css
```

## Author

Dharti Patel
