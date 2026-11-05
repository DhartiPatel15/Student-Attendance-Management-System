ATTENDEASE - STUDENT ATTENDANCE MANAGEMENT SYSTEM

RUN ON WINDOWS
1. Extract this ZIP file.
2. Open the extracted folder.
3. Double-click START.bat. The launcher checks and repairs pip automatically if the virtual environment is incomplete.
4. On first run, it creates a private Python environment and installs Flask. Internet is needed only for this first setup.
5. The browser opens at http://127.0.0.1:5000.

DEMO LOGIN
Username: admin
Password: admin123

FEATURES
- Admin login and logout
- Dashboard with student and daily attendance totals
- Add, view, search, edit and delete students
- Import students from CSV and export the student directory to CSV
- Mark Present/Absent attendance by date
- Date-range attendance reports with date validation
- Export report to CSV
- SQLite database created automatically as attendance.db

NOTES
- Keep the black START.bat window open while using the app. Close it to stop the server.
- Data is stored in attendance.db in this folder. Back it up.
- This is a local demo project. Demo credentials and secret key must be changed and production hosting/database configured before public deployment.
- Do not use real student personal information in a public demo.


STUDENT PORTAL
- Students can register and sign in with their email and password.
- Faculty can add student records first; students can then activate their account using the same roll number and email.
- Student accounts only see their own dashboard and attendance history.
