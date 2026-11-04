from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import sqlite3, csv, io
from pathlib import Path
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = "demo-secret-change-before-deployment"
DB = Path(__file__).with_name("attendance.db")

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS students(
      id INTEGER PRIMARY KEY AUTOINCREMENT, roll_no TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL, course TEXT NOT NULL, semester TEXT NOT NULL, email TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS attendance(
      id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
      attend_date TEXT NOT NULL, status TEXT NOT NULL,
      UNIQUE(student_id,attend_date))""")
    c.commit()
    return c

def auth(fn):
    @wraps(fn)
    def inner(*a, **kw):
        if not session.get("admin"): return redirect(url_for("login"))
        return fn(*a, **kw)
    return inner

@app.route("/")
def home(): return redirect(url_for("dashboard") if session.get("admin") else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == "admin" and request.form.get("password") == "admin123":
            session["admin"] = True
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/dashboard")
@auth
def dashboard():
    c=connect(); today=date.today().isoformat()
    total=c.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present=c.execute("SELECT COUNT(*) FROM attendance WHERE attend_date=? AND status='Present'",(today,)).fetchone()[0]
    absent=c.execute("SELECT COUNT(*) FROM attendance WHERE attend_date=? AND status='Absent'",(today,)).fetchone()[0]
    recent=c.execute("""SELECT a.attend_date,a.status,s.roll_no,s.name FROM attendance a
      JOIN students s ON s.id=a.student_id ORDER BY a.attend_date DESC,a.id DESC LIMIT 8""").fetchall()
    c.close()
    return render_template("dashboard.html",total=total,present=present,absent=absent,today=today,recent=recent)

@app.route("/students",methods=["GET","POST"])
@auth
def students():
    c=connect()
    if request.method=="POST":
        vals=[request.form.get(k,"").strip() for k in ("roll_no","name","course","semester","email")]
        if not all(vals[:4]): flash("Fill in all required fields.","error")
        else:
            try:
                c.execute("INSERT INTO students(roll_no,name,course,semester,email) VALUES(?,?,?,?,?)",vals)
                c.commit(); flash("Student added successfully.","success")
            except sqlite3.IntegrityError: flash("Roll number already exists.","error")
        c.close(); return redirect(url_for("students"))
    q=request.args.get("q","").strip()
    rows=c.execute("SELECT * FROM students WHERE roll_no LIKE ? OR name LIKE ? OR course LIKE ? ORDER BY roll_no",
      (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    c.close(); return render_template("students.html",students=rows,q=q)

@app.route("/students/delete/<int:sid>",methods=["POST"])
@auth
def delete_student(sid):
    c=connect(); c.execute("DELETE FROM attendance WHERE student_id=?",(sid,))
    c.execute("DELETE FROM students WHERE id=?",(sid,)); c.commit(); c.close()
    flash("Student deleted.","success"); return redirect(url_for("students"))

@app.route("/attendance",methods=["GET","POST"])
@auth
def attendance():
    selected=request.values.get("attend_date",date.today().isoformat()); c=connect()
    if request.method=="POST":
        for s in c.execute("SELECT id FROM students").fetchall():
            status=request.form.get("status_"+str(s["id"]))
            if status in ("Present","Absent"):
                c.execute("""INSERT INTO attendance(student_id,attend_date,status) VALUES(?,?,?)
                  ON CONFLICT(student_id,attend_date) DO UPDATE SET status=excluded.status""",(s["id"],selected,status))
        c.commit(); flash("Attendance saved for "+selected+".","success")
    rows=c.execute("""SELECT s.*,a.status FROM students s LEFT JOIN attendance a
      ON a.student_id=s.id AND a.attend_date=? ORDER BY s.roll_no""",(selected,)).fetchall()
    c.close(); return render_template("attendance.html",students=rows,selected=selected)

@app.route("/reports")
@auth
def reports():
    start=request.args.get("start",date.today().replace(day=1).isoformat()); end=request.args.get("end",date.today().isoformat())
    c=connect()
    rows=c.execute("""SELECT s.roll_no,s.name,s.course,a.attend_date,a.status FROM attendance a
      JOIN students s ON s.id=a.student_id WHERE a.attend_date BETWEEN ? AND ?
      ORDER BY a.attend_date DESC,s.roll_no""",(start,end)).fetchall()
    t=c.execute("""SELECT SUM(status='Present') p,SUM(status='Absent') a FROM attendance
      WHERE attend_date BETWEEN ? AND ?""",(start,end)).fetchone()
    c.close(); return render_template("reports.html",rows=rows,start=start,end=end,present=t["p"] or 0,absent=t["a"] or 0)

@app.route("/reports/export")
@auth
def export_report():
    start=request.args.get("start",""); end=request.args.get("end","")
    c=connect(); rows=c.execute("""SELECT s.roll_no,s.name,s.course,a.attend_date,a.status FROM attendance a
      JOIN students s ON s.id=a.student_id WHERE a.attend_date BETWEEN ? AND ? ORDER BY a.attend_date DESC""",(start,end)).fetchall(); c.close()
    out=io.StringIO(); w=csv.writer(out); w.writerow(["Roll No","Name","Course","Date","Status"])
    w.writerows([tuple(r) for r in rows])
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=attendance_report.csv"})

if __name__=="__main__":
    connect().close()
    app.run(host="127.0.0.1",port=5000,debug=False)
