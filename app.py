from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, csv, io, os
from pathlib import Path
from datetime import date, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.endpoint != "static":
        response.headers.setdefault("Cache-Control", "no-store")
    return response

@app.before_request
def check_same_origin_for_writes():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("Origin")
        if origin:
            from urllib.parse import urlparse
            if urlparse(origin).netloc != request.host:
                return "Cross-origin request rejected.", 403
DB = Path(os.environ.get("DATABASE_PATH", str(Path(__file__).with_name("attendance.db"))))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DEMO_STUDENT_EMAIL = os.environ.get("DEMO_STUDENT_EMAIL", "student.demo@attendease.test").strip().lower()
DEMO_STUDENT_PASSWORD = os.environ.get("DEMO_STUDENT_PASSWORD", "StudentDemo123!")

def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS students(
      id INTEGER PRIMARY KEY AUTOINCREMENT, roll_no TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL, course TEXT NOT NULL, semester TEXT NOT NULL,
      email TEXT DEFAULT '', password_hash TEXT)""")
    # Upgrade databases created by earlier versions without deleting student data.
    columns = {r["name"] for r in c.execute("PRAGMA table_info(students)").fetchall()}
    if "password_hash" not in columns:
        c.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")
    c.execute("""CREATE TABLE IF NOT EXISTS attendance(
      id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
      attend_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
      UNIQUE(student_id,attend_date))""")
    # Keep one fictional student account available for public demonstrations.
    # The .test email domain is reserved and cannot receive real email.
    demo = c.execute("SELECT id, password_hash FROM students WHERE roll_no=?", ("DEMO-001",)).fetchone()
    if demo is None:
        email_owner = c.execute("SELECT id FROM students WHERE lower(email)=?", (DEMO_STUDENT_EMAIL,)).fetchone()
        if email_owner is None:
            c.execute(
                """INSERT INTO students(roll_no,name,course,semester,email,password_hash)
                   VALUES(?,?,?,?,?,?)""",
                ("DEMO-001", "Demo Student", "BCA", "5", DEMO_STUDENT_EMAIL,
                 generate_password_hash(DEMO_STUDENT_PASSWORD)),
            )
    elif not demo["password_hash"]:
        c.execute("UPDATE students SET email=?, password_hash=? WHERE id=?",
                  (DEMO_STUDENT_EMAIL, generate_password_hash(DEMO_STUDENT_PASSWORD), demo["id"]))
    c.commit()
    return c

def admin_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return inner

def student_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if session.get("role") != "student" or not session.get("student_id"):
            return redirect(url_for("student_login"))
        return fn(*args, **kwargs)
    return inner

@app.route("/")
def home():
    if session.get("role") == "admin":
        return redirect(url_for("dashboard"))
    if session.get("role") == "student":
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["role"] = "admin"
            session["admin"] = True  # backward-compatible navigation flag
            return redirect(url_for("dashboard"))
        flash("Admin username or password is incorrect.", "error")
    return render_template("login.html")

@app.route("/student/register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        semester = request.form.get("semester", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not all([roll_no, name, course, semester, email, password]):
            flash("Please fill in all required fields.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            c = connect()
            try:
                existing = c.execute("SELECT * FROM students WHERE roll_no=?", (roll_no,)).fetchone()
                if existing:
                    if existing["password_hash"]:
                        flash("This roll number already has an account. Please sign in.", "error")
                    elif not existing["email"] or existing["email"].strip().lower() != email:
                        flash("This roll number exists. Enter the email already recorded by faculty, or contact faculty to update it.", "error")
                    else:
                        c.execute("UPDATE students SET password_hash=? WHERE id=?",
                                  (generate_password_hash(password), existing["id"]))
                        c.commit()
                        student_id = existing["id"]
                        c.close()
                        session.clear()
                        session["role"] = "student"
                        session["student_id"] = student_id
                        flash("Your existing student record is now linked to your secure account.", "success")
                        return redirect(url_for("student_dashboard"))
                else:
                    c.execute("""INSERT INTO students(roll_no,name,course,semester,email,password_hash)
                        VALUES(?,?,?,?,?,?)""",
                        (roll_no, name, course, semester, email, generate_password_hash(password)))
                    c.commit()
                    student_id = c.execute("SELECT id FROM students WHERE roll_no=?", (roll_no,)).fetchone()["id"]
                    c.close()
                    session.clear()
                    session["role"] = "student"
                    session["student_id"] = student_id
                    flash("Your student account has been created.", "success")
                    return redirect(url_for("student_dashboard"))
            except sqlite3.IntegrityError:
                flash("This email is already in use. Please sign in or contact faculty.", "error")
            finally:
                c.close()
    return render_template("student_register.html")

@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        c = connect()
        student = c.execute("SELECT * FROM students WHERE lower(email)=? AND password_hash IS NOT NULL", (email,)).fetchone()
        c.close()
        if student and check_password_hash(student["password_hash"], password):
            session.clear()
            session["role"] = "student"
            session["student_id"] = student["id"]
            return redirect(url_for("student_dashboard"))
        flash("Email or password is incorrect. If you are new, create an account.", "error")
    return render_template("student_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@admin_required
def dashboard():
    c = connect()
    today = date.today().isoformat()
    total = c.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present = c.execute("SELECT COUNT(*) FROM attendance WHERE attend_date=? AND status='Present'", (today,)).fetchone()[0]
    absent = c.execute("SELECT COUNT(*) FROM attendance WHERE attend_date=? AND status='Absent'", (today,)).fetchone()[0]
    recent = c.execute("""SELECT a.attend_date,a.status,s.roll_no,s.name FROM attendance a
      JOIN students s ON s.id=a.student_id ORDER BY a.attend_date DESC,a.id DESC LIMIT 8""").fetchall()
    c.close()
    return render_template("dashboard.html", total=total, present=present, absent=absent, today=today, recent=recent)

@app.route("/students", methods=["GET", "POST"])
@admin_required
def students():
    c = connect()
    if request.method == "POST":
        vals = [request.form.get(k, "").strip() for k in ("roll_no", "name", "course", "semester", "email")]
        if not all(vals[:4]):
            flash("Fill in all required fields.", "error")
        else:
            try:
                c.execute("INSERT INTO students(roll_no,name,course,semester,email) VALUES(?,?,?,?,?)", vals)
                c.commit()
                flash("Student added successfully. The student can now register using this roll number and email.", "success")
            except sqlite3.IntegrityError:
                flash("Roll number already exists.", "error")
        c.close()
        return redirect(url_for("students"))
    q = request.args.get("q", "").strip()
    rows = c.execute("""SELECT id,roll_no,name,course,semester,email,
        CASE WHEN password_hash IS NULL THEN 'Not registered' ELSE 'Active' END AS account_status
        FROM students WHERE roll_no LIKE ? OR name LIKE ? OR course LIKE ? ORDER BY roll_no""",
        (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    c.close()
    return render_template("students.html", students=rows, q=q)

@app.route("/students/import", methods=["POST"])
@admin_required
def import_students():
    uploaded = request.files.get("student_file")
    if not uploaded or not uploaded.filename.lower().endswith(".csv"):
        flash("Please choose a CSV file.", "error")
        return redirect(url_for("students"))
    try:
        stream = io.StringIO(uploaded.stream.read().decode("utf-8-sig"), newline="")
        reader = csv.DictReader(stream)
        required = {"roll_no", "name", "course", "semester"}
        if not reader.fieldnames or not required.issubset({h.strip().lower() for h in reader.fieldnames}):
            flash("CSV headers must include: roll_no, name, course, semester (email is optional).", "error")
            return redirect(url_for("students"))
        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
        c = connect()
        added = skipped = 0
        for row in reader:
            values = [str(row.get(k, "") or "").strip() for k in ("roll_no", "name", "course", "semester", "email")]
            if not all(values[:4]):
                skipped += 1
                continue
            try:
                c.execute("INSERT INTO students(roll_no,name,course,semester,email) VALUES(?,?,?,?,?)", values)
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
        c.commit()
        c.close()
        flash(f"Import complete: {added} student(s) added, {skipped} skipped.", "success")
    except (UnicodeDecodeError, csv.Error):
        flash("Could not read this CSV. Save it as UTF-8 CSV and try again.", "error")
    return redirect(url_for("students"))

@app.route("/students/csv-template")
@admin_required
def student_csv_template():
    content = "roll_no,name,course,semester,email\n"
    return Response(content, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=students_template.csv"})

@app.route("/students/edit/<int:sid>", methods=["GET", "POST"])
@admin_required
def edit_student(sid):
    c = connect()
    student = c.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not student:
        c.close()
        flash("Student record was not found.", "error")
        return redirect(url_for("students"))
    if request.method == "POST":
        vals = [request.form.get(k, "").strip() for k in ("roll_no", "name", "course", "semester", "email")]
        if not all(vals[:4]):
            flash("Roll number, name, course and semester are required.", "error")
        else:
            try:
                c.execute("""UPDATE students SET roll_no=?,name=?,course=?,semester=?,email=?
                    WHERE id=?""", (*vals, sid))
                c.commit()
                c.close()
                flash("Student details updated successfully.", "success")
                return redirect(url_for("students"))
            except sqlite3.IntegrityError:
                flash("That roll number is already assigned to another student.", "error")
    c.close()
    return render_template("edit_student.html", student=student)


@app.route("/students/export")
@admin_required
def export_students():
    c = connect()
    rows = c.execute("""SELECT roll_no,name,course,semester,email FROM students
        ORDER BY roll_no""").fetchall()
    c.close()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Roll No", "Name", "Course", "Semester", "Email"])
    writer.writerows([tuple(row) for row in rows])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"})


@app.route("/students/delete/<int:sid>", methods=["POST"])
@admin_required
def delete_student(sid):
    c = connect()
    c.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
    c.execute("DELETE FROM students WHERE id=?", (sid,))
    c.commit()
    c.close()
    flash("Student deleted.", "success")
    return redirect(url_for("students"))

@app.route("/attendance", methods=["GET", "POST"])
@admin_required
def attendance():
    selected = request.values.get("attend_date", date.today().isoformat())
    try:
        parsed_date = date.fromisoformat(selected)
        if parsed_date > date.today():
            raise ValueError
    except (TypeError, ValueError):
        flash("Please choose a valid date that is not in the future.", "error")
        selected = date.today().isoformat()
    c = connect()
    if request.method == "POST":
        for s in c.execute("SELECT id FROM students").fetchall():
            status = request.form.get("status_" + str(s["id"]))
            if status in ("Present", "Absent"):
                c.execute("""INSERT INTO attendance(student_id,attend_date,status) VALUES(?,?,?)
                  ON CONFLICT(student_id,attend_date) DO UPDATE SET status=excluded.status""",
                  (s["id"], selected, status))
        c.commit()
        flash("Attendance saved for " + selected + ".", "success")
    rows = c.execute("""SELECT s.*,a.status FROM students s LEFT JOIN attendance a
      ON a.student_id=s.id AND a.attend_date=? ORDER BY s.roll_no""", (selected,)).fetchall()
    c.close()
    return render_template("attendance.html", students=rows, selected=selected)

@app.route("/reports")
@admin_required
def reports():
    start = request.args.get("start", date.today().replace(day=1).isoformat())
    end = request.args.get("end", date.today().isoformat())
    try:
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError
    except (TypeError, ValueError):
        flash("Please select a valid report date range (From must not be after To).", "error")
        start = date.today().replace(day=1).isoformat()
        end = date.today().isoformat()
    c = connect()
    rows = c.execute("""SELECT s.roll_no,s.name,s.course,a.attend_date,a.status FROM attendance a
      JOIN students s ON s.id=a.student_id WHERE a.attend_date BETWEEN ? AND ?
      ORDER BY a.attend_date DESC,s.roll_no""", (start, end)).fetchall()
    totals = c.execute("""SELECT SUM(status='Present') p,SUM(status='Absent') a FROM attendance
      WHERE attend_date BETWEEN ? AND ?""", (start, end)).fetchone()
    c.close()
    return render_template("reports.html", rows=rows, start=start, end=end, present=totals["p"] or 0, absent=totals["a"] or 0)

@app.route("/reports/export")
@admin_required
def export_report():
    start = request.args.get("start", date.today().replace(day=1).isoformat())
    end = request.args.get("end", date.today().isoformat())
    try:
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError
    except (TypeError, ValueError):
        flash("Please select a valid report date range before exporting.", "error")
        return redirect(url_for("reports"))
    c = connect()
    rows = c.execute("""SELECT s.roll_no,s.name,s.course,a.attend_date,a.status FROM attendance a
      JOIN students s ON s.id=a.student_id WHERE a.attend_date BETWEEN ? AND ? ORDER BY a.attend_date DESC""",
      (start, end)).fetchall()
    c.close()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Roll No", "Name", "Course", "Date", "Status"])
    writer.writerows([tuple(r) for r in rows])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
      headers={"Content-Disposition": "attachment; filename=attendance_report.csv"})

@app.route("/student/dashboard")
@student_required
def student_dashboard():
    c = connect()
    student = c.execute("SELECT id,roll_no,name,course,semester,email FROM students WHERE id=?", (session["student_id"],)).fetchone()
    if not student:
        c.close()
        session.clear()
        return redirect(url_for("student_login"))
    total = c.execute("SELECT COUNT(*) FROM attendance WHERE student_id=?", (student["id"],)).fetchone()[0]
    present = c.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (student["id"],)).fetchone()[0]
    absent = c.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Absent'", (student["id"],)).fetchone()[0]
    history = c.execute("SELECT attend_date,status FROM attendance WHERE student_id=? ORDER BY attend_date DESC LIMIT 30", (student["id"],)).fetchall()
    c.close()
    percentage = round((present / total) * 100, 1) if total else 0
    return render_template("student_dashboard.html", student=student, total=total, present=present, absent=absent, percentage=percentage, history=history)

@app.route("/student/attendance")
@student_required
def student_attendance():
    c = connect()
    rows = c.execute("SELECT attend_date,status FROM attendance WHERE student_id=? ORDER BY attend_date DESC", (session["student_id"],)).fetchall()
    c.close()
    return render_template("student_attendance.html", records=rows)

if __name__ == "__main__":
    connect().close()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
