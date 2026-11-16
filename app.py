
from db import get_db_connection
from flask import Flask, render_template, request, redirect, url_for, session
from db import get_db_connection
from werkzeug.security import check_password_hash
from functools import wraps
from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

import os
app.secret_key = os.environ.get("SECRET_KEY", "temporary-local-key")


# Login protection
def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# Login page
@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        if session.get("user_type") == "Student":
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user_type = request.form["user_type"]

        connection = get_db_connection()
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user and check_password_hash(user["password"], password):
            if user["user_type"] == user_type:

                session["user_id"] = user["user_id"]
                session["user_name"] = user["name"]
                session["user_type"] = user["user_type"]
                session["user_email"] = user["email"]

                if user_type == "Student":
                    return redirect(url_for("student_dashboard"))

                return redirect(url_for("dashboard"))

        return "Invalid email, password or user type!"

    return render_template("login.html")



# Admin / Faculty Dashboard
@app.route("/dashboard")
@login_required
def dashboard():

    if session.get("user_type") == "Student":
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    # Total Students
    cursor.execute("SELECT COUNT(*) AS total_students FROM students")
    total_students = cursor.fetchone()["total_students"]

    # Total Attendance Records
    cursor.execute("SELECT COUNT(*) AS total_attendance FROM attendance")
    total_attendance = cursor.fetchone()["total_attendance"]

    # Total Exams
    cursor.execute("SELECT COUNT(*) AS total_exams FROM performance")
    total_exams = cursor.fetchone()["total_exams"]

    # Attendance Percentage
    cursor.execute("""
        SELECT
            CASE
                WHEN COUNT(*) = 0 THEN 0
                ELSE ROUND(
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END)
                    * 100.0 / COUNT(*), 2
                )
            END AS average_attendance
        FROM attendance
    """)

    average_attendance = cursor.fetchone()["average_attendance"]

    # Attendance Chart Data
    cursor.execute("""
        SELECT status, COUNT(*) AS total
        FROM attendance
        GROUP BY status
    """)

    attendance_chart = cursor.fetchall()

    # Performance Chart Data
    cursor.execute("""
        SELECT
            subject,
            ROUND(AVG(marks_obtained * 100.0 / total_marks), 2)
            AS average_percentage
        FROM performance
        WHERE total_marks > 0
        GROUP BY subject
        ORDER BY subject
    """)

    performance_chart = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        total_attendance=total_attendance,
        total_exams=total_exams,
        average_attendance=average_attendance,
        attendance_chart=attendance_chart,
        performance_chart=performance_chart
    )

    # Total Students
    cursor.execute("SELECT COUNT(*) AS total_students FROM students")
    total_students = cursor.fetchone()["total_students"]

    # Total Attendance Records
    cursor.execute("SELECT COUNT(*) AS total_attendance FROM attendance")
    total_attendance = cursor.fetchone()["total_attendance"]

    # Total Exams
    cursor.execute("SELECT COUNT(*) AS total_exams FROM performance")
    total_exams = cursor.fetchone()["total_exams"]

    # Average Attendance Percentage
    cursor.execute("""
        SELECT
            CASE
                WHEN COUNT(*) = 0 THEN 0
                ELSE ROUND(
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END)
                    * 100.0 / COUNT(*), 2
                )
            END AS average_attendance
        FROM attendance
    """)

    average_attendance = cursor.fetchone()["average_attendance"]

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        total_attendance=total_attendance,
        total_exams=total_exams,
        average_attendance=average_attendance
    )


# Logout
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))



# Student Dashboard with Attendance and Performance Summary
@app.route("/student_dashboard")
@login_required
def student_dashboard():

    if session.get("user_type") != "Student":
        return redirect(url_for("dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    # Get Student Details
    cursor.execute(
        "SELECT * FROM students WHERE email = %s",
        (session["user_email"],)
    )

    student = cursor.fetchone()

    if not student:
        cursor.close()
        connection.close()
        return "Student record not found. Please contact the Admin."

    # Attendance Summary
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_days,
            SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) AS late_days
        FROM attendance
        WHERE student_id = %s
        """,
        (student["student_id"],)
    )

    summary = cursor.fetchone()

    total_days = summary["total_days"] or 0
    present_days = summary["present_days"] or 0
    absent_days = summary["absent_days"] or 0
    late_days = summary["late_days"] or 0

    attendance_percentage = (
        round((present_days / total_days) * 100, 2)
        if total_days > 0 else 0
    )

    # Performance Summary
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_exams,
            COALESCE(SUM(marks_obtained), 0) AS total_marks,
            COALESCE(SUM(total_marks), 0) AS maximum_marks
        FROM performance
        WHERE student_id = %s
        """,
        (student["student_id"],)
    )

    performance_summary = cursor.fetchone()

    total_exams = performance_summary["total_exams"]
    total_marks = performance_summary["total_marks"]
    maximum_marks = performance_summary["maximum_marks"]

    average_percentage = (
        round((total_marks / maximum_marks) * 100, 2)
        if maximum_marks > 0 else 0
    )

    # Close Database Connection
    cursor.close()
    connection.close()

    # Display Student Dashboard
    return render_template(
        "student_dashboard.html",
        student=student,
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        late_days=late_days,
        attendance_percentage=attendance_percentage,
        total_exams=total_exams,
        total_marks=total_marks,
        maximum_marks=maximum_marks,
        average_percentage=average_percentage
    )

# Student My Attendance
@app.route("/my_attendance")
@login_required
def my_attendance():

    if session.get("user_type") != "Student":
        return redirect(url_for("dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute(
        "SELECT student_id FROM students WHERE email = %s",
        (session["user_email"],)
    )

    student = cursor.fetchone()

    if not student:
        cursor.close()
        connection.close()
        return "Student record not found."

    cursor.execute(
        """
        SELECT attendance_date, status
        FROM attendance
        WHERE student_id = %s
        ORDER BY attendance_date DESC
        """,
        (student["student_id"],)
    )

    attendance_records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "my_attendance.html",
        attendance_records=attendance_records
    )
# Student My Performance
@app.route("/my_performance")
@login_required
def my_performance():

    if session.get("user_type") != "Student":
        return redirect(url_for("dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute(
        "SELECT student_id FROM students WHERE email = %s",
        (session["user_email"],)
    )

    student = cursor.fetchone()

    if not student:
        cursor.close()
        connection.close()
        return "Student record not found."

    cursor.execute(
        """
        SELECT subject, exam_name, marks_obtained,
               total_marks, exam_date
        FROM performance
        WHERE student_id = %s
        ORDER BY exam_date DESC
        """,
        (student["student_id"],)
    )

    performance_records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "my_performance.html",
        performance_records=performance_records
    )


# Add Student
@app.route("/students", methods=["GET", "POST"])
@login_required
def students():

    error = None

    if request.method == "POST":
        name = request.form["student_name"].strip()
        reg_no = request.form["register_number"].strip()
        department = request.form["department"]
        year = request.form["study_year"]
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO students
                (student_name, register_number, department, study_year, email, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, reg_no, department, year, email, phone))

            connection.commit()

            cursor.close()
            connection.close()

            return redirect(url_for("students"))

        except IntegrityError:
            connection.rollback()
            error = "This Register Number is already registered."

        cursor.close()
        connection.close()

    return render_template("students.html", error=error)


# View Students
@app.route("/view_students")
@login_required
def view_students():

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM students ORDER BY student_id")
    students = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("view_students.html", students=students)


# Edit Student
@app.route("/edit_student/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        student_name = request.form["student_name"]
        register_number = request.form["register_number"]
        department = request.form["department"]
        study_year = request.form["study_year"]
        email = request.form["email"]
        phone = request.form["phone"]

        cursor.execute("""
            UPDATE students
            SET student_name=%s,
                register_number=%s,
                department=%s,
                study_year=%s,
                email=%s,
                phone=%s
            WHERE student_id=%s
        """, (
            student_name, register_number, department,
            study_year, email, phone, student_id
        ))

        connection.commit()
        cursor.close()
        connection.close()

        return redirect(url_for("view_students"))

    cursor.execute(
        "SELECT * FROM students WHERE student_id=%s",
        (student_id,)
    )

    student = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template("edit_student.html", student=student)


# Delete Student
@app.route("/delete_student/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM attendance WHERE student_id=%s",
        (student_id,)
    )

    cursor.execute(
        "DELETE FROM performance WHERE student_id=%s",
        (student_id,)
    )

    cursor.execute(
        "DELETE FROM students WHERE student_id=%s",
        (student_id,)
    )

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("view_students"))


# Mark Attendance
@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    error = None

    if request.method == "POST":
        student_id = request.form["student_id"]
        attendance_date = request.form["attendance_date"]
        status = request.form["status"]

        if status not in ["Present", "Absent", "Late"]:
            error = "Please select a valid attendance status."

        else:
            try:
                cursor.execute("""
                    INSERT INTO attendance
                    (student_id, attendance_date, status)
                    VALUES (%s, %s, %s)
                """, (student_id, attendance_date, status))

                connection.commit()

            except IntegrityError:
                connection.rollback()
                error = "Attendance is already marked for this student on this date."

    cursor.execute("SELECT * FROM students ORDER BY student_name")
    students = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "attendance.html",
        students=students,
        error=error
    )


# View Attendance
@app.route("/view_attendance")
@login_required
def view_attendance():

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            attendance.attendance_id,
            students.student_name,
            students.register_number,
            attendance.attendance_date,
            attendance.status
        FROM attendance
        JOIN students
        ON attendance.student_id = students.student_id
        ORDER BY attendance.attendance_date DESC
    """)

    records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("view_attendance.html", records=records)


# Add Performance
@app.route("/performance", methods=["GET", "POST"])
@login_required
def performance():

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    error = None

    if request.method == "POST":
        student_id = request.form["student_id"]
        subject = request.form["subject"].strip()
        exam_name = request.form["exam_name"].strip()
        exam_date = request.form["exam_date"]

        try:
            marks = float(request.form["marks_obtained"])
            total = float(request.form["total_marks"])

            if marks < 0:
                error = "Marks obtained cannot be negative."

            elif total <= 0:
                error = "Total marks must be greater than zero."

            elif marks > total:
                error = "Marks obtained cannot be greater than total marks."

            else:
                cursor.execute("""
                    INSERT INTO performance
                    (student_id, subject, exam_name, marks_obtained,
                     total_marks, exam_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (student_id, subject, exam_name, marks, total, exam_date))

                connection.commit()

                cursor.close()
                connection.close()

                return redirect(url_for("view_performance"))

        except ValueError:
            error = "Please enter valid marks."

    cursor.execute("SELECT * FROM students ORDER BY student_name")
    students = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "performance.html",
        students=students,
        error=error
    )


# View Performance
@app.route("/view_performance")
@login_required
def view_performance():

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            performance.performance_id,
            students.student_name,
            students.register_number,
            performance.subject,
            performance.exam_name,
            performance.marks_obtained,
            performance.total_marks,
            performance.exam_date
        FROM performance
        JOIN students
        ON performance.student_id = students.student_id
        ORDER BY performance.exam_date DESC
    """)

    records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("view_performance.html", records=records)


# Reports
@app.route("/reports")
@login_required
def reports():

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    # Total students
    cursor.execute("SELECT COUNT(*) AS total_students FROM students")
    student_count = cursor.fetchone()

    # Attendance Summary
    cursor.execute("""
        SELECT
            COUNT(*) AS total_records,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
            SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) AS late_count
        FROM attendance
    """)

    attendance_summary = cursor.fetchone()

    # Attendance Report
    cursor.execute("""
        SELECT
            students.student_name,
            students.register_number,
            COUNT(attendance.attendance_id) AS total_days,
            SUM(CASE WHEN attendance.status = 'Present' THEN 1 ELSE 0 END) AS present_days,
            ROUND(
                SUM(CASE WHEN attendance.status = 'Present' THEN 1 ELSE 0 END)
                * 100.0 / NULLIF(COUNT(attendance.attendance_id), 0), 2
            ) AS attendance_percentage
        FROM students
        LEFT JOIN attendance
        ON students.student_id = attendance.student_id
        GROUP BY students.student_id,
                 students.student_name,
                 students.register_number
        ORDER BY students.student_name
    """)

    attendance_records = cursor.fetchall()

    # Performance Report
    cursor.execute("""
        SELECT
            students.student_name,
            performance.subject,
            performance.exam_name,
            performance.marks_obtained,
            performance.total_marks,
            ROUND(
                performance.marks_obtained * 100.0 /
                NULLIF(performance.total_marks, 0), 2
            ) AS percentage
        FROM performance
        JOIN students
        ON performance.student_id = students.student_id
        ORDER BY students.student_name
    """)

    performance_records = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "reports.html",
        student_count=student_count,
        attendance_summary=attendance_summary,
        attendance_records=attendance_records,
        performance_records=performance_records
    )


if __name__ == "__main__":
    app.run(debug=True)
