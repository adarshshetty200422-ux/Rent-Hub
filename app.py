from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from functools import wraps
import sqlite3
import random
import string
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_mail import Mail, Message
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
import hmac
import hashlib
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadData

import razorpay
import razorpay.errors
from typing import Any

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set! Create a .env file."
    )

s = URLSafeTimedSerializer(app.secret_key)

# Session cookie security
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# (Session cookie settings already applied above via app.config.update)

# CSRF Protection
csrf = CSRFProtect(app)

# Email Configuration using Flask-Mail
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_SENDER", "your_email@gmail.com")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "your_app_password")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]
mail = Mail(app)

MAIL_SENDER = app.config["MAIL_USERNAME"]
MAIL_PASSWORD = app.config["MAIL_PASSWORD"]


def send_email_notification(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = MAIL_SENDER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(MAIL_SENDER, MAIL_PASSWORD)
        server.sendmail(MAIL_SENDER, to_email, msg.as_string())
        server.quit()
        return True
    except smtplib.SMTPException as e:
        print(f"Email could not be sent: {e}")
        return False


def send_employee_credentials(email, username, password):
    try:
        subject = "Rent Hub Employee Account Approved"
        login_link = url_for("employee", _external=True)

        body = f"""Hello,
Your employee application has been approved by Rent Hub.

Username: {username}
Password: {password}

You can now log in to the employee portal and start using the platform.
Login Link: {login_link}

Thank you,
Rent Hub Team"""

        msg = Message(subject, recipients=[email], body=body)
        mail.send(msg)
        return True
    except smtplib.SMTPException as e:
        print(f"Employee credentials email could not be sent: {e}")
        return False


DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Login required decorator to protect dashboard routes
def login_required(role_required=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("index"))

            if role_required and session.get("role") != role_required:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("index"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("auth_user") or request.form.get("username")
    password = request.form.get("auth_pass") or request.form.get("password")

    if not username or not password:
        flash("Missing credentials.", "error")
        return redirect(url_for("index"))

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND account_status = 'approved'",
            (username,),
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            conn.execute("UPDATE users SET is_online = 1 WHERE id = ?", (user["id"],))
            conn.commit()
            session.clear()
            session.permanent = False
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Login successful!", "success")

            if user["role"] == "admin":
                return redirect(url_for("dashboard_admin"))
            elif user["role"] == "employee":
                return redirect(url_for("dashboard_employee"))
            else:
                return redirect(url_for("dashboard_user"))
        else:
            flash("Invalid credentials or account not approved.", "error")
            return redirect(url_for("index"))


def process_login(request, expected_role, template, success_redirect):
    if request.method == "POST":
        username = (
            request.form.get("username")
            or request.form.get("adm_user")
            or request.form.get("usr_user")
            or request.form.get("emp_user")
        )
        password = (
            request.form.get("password")
            or request.form.get("adm_pass")
            or request.form.get("usr_pass")
            or request.form.get("emp_pass")
        )

        if not username or not password:
            flash("Missing credentials.", "error")
            return render_template(template)

        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ? AND role = ? AND account_status = 'approved'",
                (username, expected_role),
            ).fetchone()

            if user and check_password_hash(user["password"], password):
                conn.execute(
                    "UPDATE users SET is_online = 1 WHERE id = ?", (user["id"],)
                )
                conn.commit()
                session.clear()
                session.permanent = False
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                flash("Login successful!", "success")
                return redirect(url_for(success_redirect))
            else:
                flash("Invalid credentials or role.", "error")

    return render_template(template)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    return process_login(request, "admin", "admin_login.html", "dashboard_admin")


@app.route("/user", methods=["GET", "POST"])
def user():
    return process_login(request, "user", "user_login.html", "dashboard_user")


@app.route("/register_user", methods=["POST"])
def register_user():
    username = request.form.get("username") or request.form.get("usr_user")
    password = request.form.get("password") or request.form.get("usr_pass")
    gmail = request.form.get("gmail")
    if gmail:
        gmail = gmail.strip().lower()

    if not username or not password or not gmail:
        flash("Please fill all fields.", "error")
        return redirect(url_for("user"))

    try:
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT * FROM users WHERE (username = ? AND role = 'user') OR gmail = ?",
                (username, gmail),
            ).fetchone()

            if existing:
                if existing["username"] == username and existing["role"] == "user":
                    flash(
                        f'Username "{username}" is already taken by another user.',
                        "error",
                    )
                else:
                    flash(f'Gmail ID "{gmail}" is already registered.', "error")
                return redirect(url_for("user"))

            hashed_pw = generate_password_hash(password)
            cursor = conn.execute(
                "INSERT INTO users (username, password, role, gmail, account_status) VALUES (?, ?, ?, ?, ?)",
                (username, hashed_pw, "user", gmail, "approved"),
            )
            user_id = cursor.lastrowid

            conn.execute("UPDATE users SET is_online = 1 WHERE id = ?", (user_id,))
            conn.commit()

            session.clear()
            session["user_id"] = user_id
            session["username"] = username
            session["role"] = "user"

            flash("Registered and logged in successfully!", "success")
            return redirect(url_for("dashboard_user"))
    except sqlite3.Error as e:
        print(f"Registration error: {e}")
        flash("An error occurred during registration.", "error")
        return redirect(url_for("user"))


@app.route("/register_employee", methods=["POST"])
def register_employee():
    username = request.form.get("username") or request.form.get("emp_user")
    gmail = request.form.get("gmail")
    if gmail:
        gmail = gmail.strip().lower()
    work_details_list = request.form.getlist("work_details")
    work_details = ", ".join(work_details_list) if work_details_list else ""
    employee_type = request.form.get("employee_type") or "Registered Professional"

    if not username or not gmail or not work_details:
        flash("Please fill all fields.", "error")
        return redirect(url_for("employee"))

    try:
        with get_db_connection() as conn:
            # For employee registration, we check if there's an existing employee with this username
            # or ANY existing user with this gmail ID.
            existing = conn.execute(
                "SELECT * FROM users WHERE (username = ? AND role = 'employee') OR gmail = ?",
                (username, gmail),
            ).fetchone()
            if existing:
                if existing["username"] == username and existing["role"] == "employee":
                    flash(
                        f'Username "{username}" is already taken by another employee.',
                        "error",
                    )
                else:
                    flash(f'Gmail ID "{gmail}" is already registered.', "error")
                return redirect(url_for("employee"))

            conn.execute(
                "INSERT INTO users (username, password, role, gmail, work_details, employee_type, account_status, availability) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    username,
                    "pending_setup",
                    "employee",
                    gmail,
                    work_details,
                    employee_type,
                    "pending",
                    "AVAILABLE",
                ),
            )

            conn.commit()

            flash("Registration successful! Please wait for approval.", "success")
            return redirect(url_for("index"))
    except sqlite3.Error:
        flash("An error occurred during registration.", "error")
        return redirect(url_for("employee"))


@app.route("/employee", methods=["GET", "POST"])
def employee():
    return process_login(
        request, "employee", "employee_login.html", "dashboard_employee"
    )


@app.route("/logout", methods=["GET", "POST"])
def logout():
    user_id = session.get("user_id")
    if user_id:
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET is_online = 0 WHERE id = ?", (user_id,))
            conn.commit()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard_admin")
@login_required("admin")
def dashboard_admin():
    admin_id = session.get("user_id")
    with get_db_connection() as conn:
        admin_info = conn.execute(
            "SELECT * FROM users WHERE id = ?", (admin_id,)
        ).fetchone()
        users = conn.execute(
            "SELECT id, username, password, account_status, is_online FROM users WHERE role = 'user'"
        ).fetchall()
        employees = conn.execute("""
            SELECT u.id, u.username, u.password, u.account_status, u.availability, u.is_online, u.rating, u.employee_type,
            (SELECT COUNT(*) FROM service_requests sr WHERE sr.employee_id = u.id AND sr.status = 'Completed') as total_work
            FROM users u
            WHERE u.role = 'employee' AND u.account_status IN ('approved', 'blocked')
            ORDER BY u.rating DESC
        """).fetchall()
        pending_employees = conn.execute(
            "SELECT * FROM users WHERE role = 'employee' AND account_status = 'pending'"
        ).fetchall()

    return render_template(
        "dashboard_admin.html",
        admin_info=admin_info,
        users=users,
        employees=employees,
        pending_employees=pending_employees,
    )


@app.route("/view_service/<path:service_name>")
@login_required("user")
def view_service(service_name):
    with get_db_connection() as conn:
        providers = conn.execute(
            "SELECT * FROM users WHERE role = 'employee' AND account_status = 'approved' AND work_details LIKE ? ORDER BY rating DESC",
            (f"%{service_name}%",),
        ).fetchall()

    return render_template(
        "service_providers.html", service_name=service_name, providers=providers
    )


@app.route("/user_employee_details/<int:emp_id>")
@login_required("user")
def user_employee_details(emp_id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)
        ).fetchone()
        if not employee:
            flash("Professional not found.", "error")
            return redirect(url_for("dashboard_user"))
    return render_template("user_employee_details.html", employee=employee)


@app.route("/rate_profile/<int:emp_id>", methods=["POST"])
@login_required("user")
def rate_profile(emp_id):
    data = request.get_json()
    if not data or "rating" not in data:
        return jsonify({"error": "No rating provided"}), 400

    try:
        rating_val = int(data["rating"])
        if rating_val < 1 or rating_val > 5:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Invalid rating value"}), 400

    with get_db_connection() as conn:
        emp = conn.execute(
            "SELECT rating, rating_count FROM users WHERE id = ? AND role = 'employee'",
            (emp_id,),
        ).fetchone()
        if not emp:
            return jsonify({"error": "Professional not found"}), 404

        curr_rating = emp["rating"] or 0.0
        curr_count = emp["rating_count"] or 0

        new_count = curr_count + 1
        new_rating = ((curr_rating * curr_count) + rating_val) / new_count

        conn.execute(
            "UPDATE users SET rating = ?, rating_count = ? WHERE id = ?",
            (new_rating, new_count, emp_id),
        )
        conn.commit()

    return jsonify({"message": "Rating saved", "average": new_rating})


@app.route("/user_add_deposit", methods=["POST"])
@login_required("user")
def user_add_deposit():
    amount_str = request.form.get("amount")
    try:
        amount = float(amount_str or 0)
        if amount <= 0:
            flash("Deposit amount must be greater than zero.", "error")
            return redirect(url_for("dashboard_user"))

        try:
            key_id = os.environ.get("RAZORPAY_KEY_ID")
            key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
            client = razorpay.Client(auth=(key_id, key_secret))
            order = client.order.create(  # type: ignore # pylint: disable=no-member
                {
                    "amount": int(amount * 100),  # converting to paise
                    "currency": "INR",
                    "payment_capture": 1,
                }
            )
            return render_template(
                "payment.html",
                key_id=key_id,
                order_id=order["id"],
                amount=amount,
                role="user",
            )

        except (razorpay.errors.BadRequestError, razorpay.errors.GatewayError, razorpay.errors.ServerError) as e:
            flash(f"Payment gateway error: {e}", "error")
            return redirect(url_for("dashboard_user"))

    except (ValueError, TypeError):
        flash("Invalid deposit amount.", "error")
        return redirect(url_for("dashboard_user"))


@app.route("/dashboard_user")
@login_required("user")
def dashboard_user():
    user_id = session.get("user_id")
    with get_db_connection() as conn:
        user_info = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        user_messages = conn.execute(
            "SELECT * FROM user_messages WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()

        total_bookings = conn.execute(
            "SELECT COUNT(*) FROM service_requests WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        active_rentals = conn.execute(
            "SELECT COUNT(*) FROM service_requests WHERE user_id = ? AND status IN ('Pending', 'Accepted')",
            (user_id,),
        ).fetchone()[0]

    return render_template(
        "dashboard_user.html",
        user_info=user_info,
        user_messages=user_messages,
        total_bookings=total_bookings,
        active_rentals=active_rentals,
    )


@app.route("/dashboard_employee")
@login_required("employee")
def dashboard_employee():
    user_id = session.get("user_id")
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        emp_messages = []
        service_requests = []
        if employee:
            emp_messages = conn.execute(
                "SELECT * FROM employee_messages WHERE gmail = ? ORDER BY id DESC",
                (employee["gmail"],),
            ).fetchall()

            service_requests = conn.execute(
                """
                SELECT sr.id, sr.status, sr.rating, u.username as user_name, u.gmail as user_gmail
                FROM service_requests sr
                JOIN users u ON sr.user_id = u.id
                WHERE sr.employee_id = ?
                ORDER BY sr.id DESC
                """,
                (user_id,),
            ).fetchall()

    return render_template(
        "dashboard_employee.html",
        employee=employee,
        service_requests=service_requests,
        emp_messages=emp_messages,
    )


@app.route("/api/employee_messages")
@login_required("employee")
def get_employee_messages():
    user_id = session.get("user_id")
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT gmail FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if employee and employee["gmail"]:
            messages = conn.execute(
                "SELECT id, message FROM employee_messages WHERE gmail = ? ORDER BY id ASC",
                (employee["gmail"],),
            ).fetchall()
            return jsonify([{"id": m["id"], "message": m["message"]} for m in messages])
    return jsonify([])


@app.route("/update_employee", methods=["POST"])
@login_required("employee")
def update_employee():
    user_id = session.get("user_id")
    new_username = request.form.get("username")
    new_password = request.form.get("password")
    new_phone = request.form.get("gmail")
    if new_phone:
        new_phone = new_phone.strip().lower()
    new_work_list = request.form.getlist("work_details")
    new_work = ", ".join(new_work_list) if new_work_list else ""
    new_type = request.form.get("employee_type")

    if not new_username or not new_phone:
        flash("Please fill out all required fields.", "error")
        return redirect(url_for("dashboard_employee"))

    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE ((username = ? AND role = 'employee') OR gmail = ?) AND id != ?",
            (new_username, new_phone, user_id),
        ).fetchone()
        if existing:
            if existing["username"] == new_username and existing["role"] == "employee":
                flash(
                    f'Username "{new_username}" is already taken by another employee.',
                    "error",
                )
            else:
                flash(
                    f'Gmail ID "{new_phone}" is already registered to another user.',
                    "error",
                )
            return redirect(url_for("dashboard_employee"))

        updates = ["username = ?", "gmail = ?", "work_details = ?"]
        params: list[Any] = [new_username, new_phone, new_work]

        if new_type:
            updates.append("employee_type = ?")
            params.append(new_type)

        if new_password:
            updates.append("password = ?")
            params.append(generate_password_hash(new_password))

        params.append(user_id)
        conn.execute(f"UPDATE users SET {
                ', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        session["username"] = new_username
        flash("Your details have been updated successfully.", "success")

    return redirect(url_for("dashboard_employee"))


@app.route("/update_employee_availability", methods=["POST"])
@login_required("employee")
def update_employee_availability():
    user_id = session.get("user_id")
    new_timing = request.form.get("availability")

    VALID_AVAILABILITY = ("AVAILABLE", "NOT AVAILABLE", "BOOKED")
    if new_timing and new_timing in VALID_AVAILABILITY:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE users SET availability = ? WHERE id = ?
            """,
                (new_timing, user_id),
            )
            conn.commit()
            flash("Availability updated successfully.", "success")
    elif new_timing:
        flash("Invalid availability value.", "error")

    return redirect(url_for("dashboard_employee"))


@app.route("/update_admin", methods=["POST"])
@login_required("admin")
def update_admin():
    user_id = session.get("user_id")
    new_username = request.form.get("username")
    new_password = request.form.get("password")
    new_phone = request.form.get("gmail")
    if new_phone:
        new_phone = new_phone.strip().lower()
    new_work_list = request.form.getlist("work_details")
    new_work = ", ".join(new_work_list) if new_work_list else ""

    if not new_username:
        flash("Username is required.", "error")
        return redirect(url_for("dashboard_admin"))

    with get_db_connection() as conn:

        updates = ["username = ?"]
        params: list[Any] = [new_username]

        if new_password:
            updates.append("password = ?")
            params.append(generate_password_hash(new_password))
        if new_phone:
            updates.append("gmail = ?")
            params.append(new_phone)
        if new_work:
            updates.append("work_details = ?")
            params.append(new_work)

        params.append(user_id)
        conn.execute(f"UPDATE users SET {
                ', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        session["username"] = new_username
        flash("Your details have been updated successfully.", "success")

    return redirect(url_for("dashboard_admin"))


@app.route("/update_user", methods=["POST"])
@login_required("user")
def update_user():
    user_id = session.get("user_id")
    new_username = request.form.get("username")
    new_password = request.form.get("password")
    new_phone = request.form.get("gmail")
    if new_phone:
        new_phone = new_phone.strip().lower()

    if not new_username:
        flash("Username is required.", "error")
        return redirect(url_for("dashboard_user"))

    with get_db_connection() as conn:
        # Check for existing user/gmail
        if new_phone:
            existing = conn.execute(
                "SELECT * FROM users WHERE ((username = ? AND role = 'user') OR gmail = ?) AND id != ?",
                (new_username, new_phone, user_id),
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT * FROM users WHERE (username = ? AND role = 'user') AND id != ?",
                (new_username, user_id),
            ).fetchone()

        if existing:
            if existing["username"] == new_username and existing["role"] == "user":
                flash(
                    f'Username "{new_username}" is already taken by another user.',
                    "error",
                )
            else:
                flash(
                    f'Gmail ID "{new_phone}" is already registered to another user.',
                    "error",
                )
            return redirect(url_for("dashboard_user"))

        updates = ["username = ?", "gmail = ?"]
        params: list[Any] = [new_username, new_phone]

        if new_password:
            updates.append("password = ?")
            params.append(generate_password_hash(new_password))

        params.append(user_id)
        conn.execute(f"UPDATE users SET {
                ', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        session["username"] = new_username
        flash("Your details have been updated successfully.", "success")

    return redirect(url_for("dashboard_user"))


@app.route("/remove_user_accept_employee")
def remove_user_accept_employee():
    return redirect(url_for("dashboard_user"))


@app.route("/admin_accept_employee/<int:emp_id>", methods=["POST"])
@login_required("admin")
def admin_accept_employee(emp_id):
    password = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    with get_db_connection() as conn:
        emp = conn.execute("SELECT * FROM users WHERE id = ?", (emp_id,)).fetchone()
        if emp and emp["account_status"] == "pending":
            hashed_password = generate_password_hash(password)
            conn.execute(
                "UPDATE users SET password = ?, account_status = 'approved' WHERE id = ?",
                (hashed_password, emp_id),
            )
            message = f"Your employee application for Rent Hub has been approved.\n\nYour login details are as follows:\nUsername: {
                emp['username']}\nPassword: {password}\n\nPlease keep these details secure."
            conn.execute(
                "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                (emp["gmail"], message),
            )
            conn.commit()

            # Send actual email
            send_employee_credentials(emp["gmail"], emp["username"], password)

            flash(
                f"Employee {
                    emp['username']} accepted. Login details sent to their email.",
                "success",
            )
    return redirect(url_for("dashboard_admin"))


@app.route("/admin_reject_employee/<int:emp_id>", methods=["POST"])
@login_required("admin")
def admin_reject_employee(emp_id):
    with get_db_connection() as conn:
        emp = conn.execute("SELECT * FROM users WHERE id = ?", (emp_id,)).fetchone()
        if emp and emp["account_status"] == "pending":
            conn.execute(
                "UPDATE users SET account_status = 'rejected' WHERE id = ?", (emp_id,)
            )
            conn.execute(
                "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                (emp["gmail"], "Your employee application has been rejected."),
            )
            conn.commit()
            flash(f"Employee {emp['username']} rejected.", "success")
    return redirect(url_for("dashboard_admin"))


@app.route("/admin_toggle_block/<int:user_id>", methods=["POST"])
@login_required("admin")
def admin_toggle_block(user_id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            new_status = (
                "blocked" if user["account_status"] != "blocked" else "approved"
            )
            conn.execute(
                "UPDATE users SET account_status = ? WHERE id = ?",
                (new_status, user_id),
            )

            if user["role"] == "employee" and user["gmail"]:
                msg = f"Your account has been {new_status} by the administrator."
                conn.execute(
                    "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                    (user["gmail"], msg),
                )
            elif user["role"] == "user":
                msg = f"Your account has been {new_status} by the administrator."
                conn.execute(
                    "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                    (user_id, msg),
                )

            conn.commit()
            flash(f"Account {
                    user['username']} is now {new_status}.", "success")
    return redirect(request.referrer or url_for("dashboard_admin"))


@app.route("/admin_user_details/<int:user_id>")
@login_required("admin")
def admin_user_details(user_id):
    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'user'", (user_id,)
        ).fetchone()
        if not user:
            flash("User not found.", "error")
            return redirect(url_for("dashboard_admin"))
    return render_template("admin_user_details.html", user=user)


@app.route("/admin_warn_user/<int:user_id>", methods=["POST"])
@login_required("admin")
def admin_warn_user(user_id):
    warning_text = request.form.get("warning_message")
    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'user'", (user_id,)
        ).fetchone()
        if user and warning_text:
            msg = f"WARNING from Admin: {warning_text}"
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (user_id, msg),
            )
            conn.commit()
            flash(f"Warning sent to {user['username']}.", "success")
        else:
            flash("Failed to send warning.", "error")
    return redirect(url_for("admin_user_details", user_id=user_id))


@app.route("/admin_employee_details/<int:emp_id>")
@login_required("admin")
def admin_employee_details(emp_id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)
        ).fetchone()
        if not employee:
            flash("Employee not found.", "error")
            return redirect(url_for("dashboard_admin"))

        import datetime

        current_month = datetime.datetime.now().strftime("%Y-%m")
        work_done_row = conn.execute(
            "SELECT COUNT(*) as count FROM service_requests WHERE employee_id = ? AND status = 'Completed' AND strftime('%Y-%m', created_at) = ?",
            (emp_id, current_month),
        ).fetchone()
        work_done_month = work_done_row["count"] if work_done_row else 0

        requests_accepted_row = conn.execute(
            "SELECT COUNT(*) as count FROM service_requests WHERE employee_id = ? AND status IN ('Accepted', 'Completed') AND strftime('%Y-%m', created_at) = ?",
            (emp_id, current_month),
        ).fetchone()
        requests_accepted_month = (
            requests_accepted_row["count"] if requests_accepted_row else 0
        )

        total_work_done_row = conn.execute(
            "SELECT COUNT(*) as count FROM service_requests WHERE employee_id = ? AND status = 'Completed'",
            (emp_id,),
        ).fetchone()
        total_work_done = total_work_done_row["count"] if total_work_done_row else 0

        # Fetch work history
        work_history = conn.execute(
            """
            SELECT sr.id, sr.status, sr.rating, sr.review, sr.created_at, u.username as user_name
            FROM service_requests sr
            JOIN users u ON sr.user_id = u.id
            WHERE sr.employee_id = ?
            ORDER BY sr.id DESC
        """,
            (emp_id,),
        ).fetchall()

    return render_template(
        "admin_employee_details.html",
        employee=employee,
        work_done_month=work_done_month,
        requests_accepted_month=requests_accepted_month,
        total_work_done=total_work_done,
        work_history=work_history,
    )


@app.route("/admin_warn_employee/<int:emp_id>", methods=["POST"])
@login_required("admin")
def admin_warn_employee(emp_id):
    warning_text = request.form.get("warning_message")
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)
        ).fetchone()
        if employee and warning_text:
            msg = f"WARNING from Admin: {warning_text}"
            conn.execute(
                "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                (employee["gmail"], msg),
            )
            conn.commit()
            flash(f"Warning sent to {employee['username']}.", "success")
        else:
            flash("Failed to send warning.", "error")
    return redirect(url_for("admin_employee_details", emp_id=emp_id))


@app.route("/admin_update_rating/<int:emp_id>", methods=["POST"])
@login_required("admin")
def admin_update_rating(emp_id):
    new_rating_str = request.form.get("new_rating")
    try:
        new_rating = float(new_rating_str or 0)
        if new_rating < 1 or new_rating > 5:
            flash("Rating must be between 1 and 5.", "error")
            return redirect(url_for("admin_employee_details", emp_id=emp_id))
    except (ValueError, TypeError):
        flash("Invalid rating value.", "error")
        return redirect(url_for("admin_employee_details", emp_id=emp_id))

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET rating = ? WHERE id = ? AND role = 'employee'",
            (new_rating, emp_id),
        )
        conn.commit()
        flash("Employee rating updated successfully.", "success")
    return redirect(url_for("admin_employee_details", emp_id=emp_id))


@app.route("/admin_update_request/<int:req_id>/<action>", methods=["POST"])
@login_required("admin")
def admin_update_request(req_id, action):
    if action not in ("accept", "reject"):
        flash("Invalid action.", "error")
        return redirect(url_for("dashboard_admin"))

    new_status = "Approved" if action == "accept" else "Rejected"

    with get_db_connection() as conn:
        req = conn.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
        if req:
            conn.execute(
                "UPDATE requests SET status = ? WHERE id = ?", (new_status, req_id)
            )
            conn.commit()
            flash(f"Request '{
                    req['item_name']}' has been {
                    new_status.lower()}.", "success")
        else:
            flash("Request not found.", "error")

    return redirect(url_for("dashboard_admin"))


@app.route("/book_service/<int:emp_id>", methods=["POST"])
@login_required("user")
def book_service(emp_id):
    user_id = session.get("user_id")
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)
        ).fetchone()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        if employee and user:
            emp_availability = (employee["availability"] or "AVAILABLE").strip().upper()
            if emp_availability == "BOOKED":
                flash(f"Professional '{
                        employee['username']}' is currently booked.", "error")
                return redirect(request.referrer or url_for("dashboard_user"))

            if emp_availability == "NOT AVAILABLE":
                flash(f"Professional '{
                        employee['username']}' is not available.", "error")
                return redirect(request.referrer or url_for("dashboard_user"))

            if (user["deposit_balance"] or 0.0) < 500.0:
                flash(
                    "You cannot book this service because your advance deposit balance is below ₹500.",
                    "error",
                )
                return redirect(request.referrer or url_for("dashboard_user"))

            if (employee["deposit_balance"] or 0.0) < 2000.0:
                flash(
                    f"Professional '{
                        employee['username']}' is currently not accepting requests (advance deposit below ₹2000).",
                    "error",
                )
                return redirect(request.referrer or url_for("dashboard_user"))

            existing = conn.execute(
                "SELECT * FROM service_requests WHERE user_id = ? AND employee_id = ? AND status = 'Pending'",
                (user_id, emp_id),
            ).fetchone()
            if existing:
                flash(f"You already have a pending request for {
                        employee['username']}.", "error")
            else:
                conn.execute(
                    "INSERT INTO service_requests (user_id, employee_id, status) VALUES (?, ?, 'Pending')",
                    (user_id, emp_id),
                )

                # Send a notification message to the user
                user_msg = f"Your booking request has been sent to '{
                    employee['username']}'. Please wait for their acceptance."
                conn.execute(
                    "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                    (user_id, user_msg),
                )

                # Send a notification message to the employee
                deposit_balance = employee["deposit_balance"] or 0.0
                emp_msg = f"You received a new service request from {
                    user['username']}. Your current Advance Deposit balance is ₹{deposit_balance}."
                conn.execute(
                    "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                    (employee["gmail"], emp_msg),
                )

                conn.commit()
                flash(f"Booking request sent successfully to {
                        employee['username']}!", "success")
        else:
            flash("Failed to send booking request. Employee not found.", "error")

    return redirect(request.referrer or url_for("dashboard_user"))


@app.route("/employee_handle_request/<int:req_id>/<action>", methods=["POST"])
@login_required("employee")
def employee_handle_request(req_id, action):
    employee_id = session.get("user_id")
    if action not in ("accept", "reject"):
        flash("Invalid action.", "error")
        return redirect(url_for("dashboard_employee"))

    new_status = "Accepted" if action == "accept" else "Rejected"

    with get_db_connection() as conn:
        if action == "accept":
            emp_data = conn.execute(
                "SELECT deposit_balance FROM users WHERE id = ?", (employee_id,)
            ).fetchone()
            if not emp_data or (emp_data["deposit_balance"] or 0.0) < 2000.0:
                flash(
                    "You must maintain a minimum advance deposit of ₹2000 to accept new requests.",
                    "error",
                )
                return redirect(url_for("dashboard_employee"))

        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND employee_id = ?",
            (req_id, employee_id),
        ).fetchone()

        if req:
            conn.execute(
                "UPDATE service_requests SET status = ? WHERE id = ?",
                (new_status, req_id),
            )

            if new_status == "Accepted":
                conn.execute(
                    "UPDATE users SET availability = 'BOOKED' WHERE id = ?",
                    (employee_id,),
                )

            # Send a message to the user
            employee = conn.execute(
                "SELECT username FROM users WHERE id = ?", (employee_id,)
            ).fetchone()
            msg = f"Your service booking request with professional '{
                employee['username']}' has been {
                new_status.lower()}."
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (req["user_id"], msg),
            )

            conn.commit()
            flash(f"Service request has been {new_status.lower()}.", "success")
        else:
            flash("Service request not found or not authorized.", "error")

    return redirect(url_for("dashboard_employee"))


@app.route("/submit_rating/<int:req_id>", methods=["POST"])
@login_required("user")
def submit_rating(req_id):
    user_id = session.get("user_id")
    rating = request.form.get("rating")
    review = request.form.get("review", "")

    if not rating:
        flash("Please select a rating.", "error")
        return redirect(url_for("dashboard_user"))

    try:
        rating_val = int(rating)
        if rating_val < 1 or rating_val > 5:
            raise ValueError
    except ValueError:
        flash("Invalid rating value.", "error")
        return redirect(url_for("dashboard_user"))

    with get_db_connection() as conn:
        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND user_id = ? AND status = 'Completed'",
            (req_id, user_id),
        ).fetchone()

        if req:
            if req["rating"] is not None:
                flash("You have already rated this service.", "error")
                return redirect(url_for("dashboard_user"))

            conn.execute(
                "UPDATE service_requests SET rating = ?, review = ? WHERE id = ?",
                (rating_val, review, req_id),
            )

            # Update employee average rating
            emp_id = req["employee_id"]
            emp_stats = conn.execute(
                "SELECT rating, rating_count FROM users WHERE id = ?", (emp_id,)
            ).fetchone()

            curr_rating = emp_stats["rating"] or 0.0
            curr_count = emp_stats["rating_count"] or 0

            new_count = curr_count + 1
            new_rating = ((curr_rating * curr_count) + rating_val) / new_count

            conn.execute(
                "UPDATE users SET rating = ?, rating_count = ? WHERE id = ?",
                (new_rating, new_count, emp_id),
            )

            conn.commit()
            flash("Thank you for your feedback!", "success")
        else:
            flash("Service request not found or not eligible for rating.", "error")

    return redirect(url_for("dashboard_user"))


@app.route("/accept_service/<int:req_id>", methods=["POST"])
@login_required("employee")
def accept_service(req_id):
    employee_id = session.get("user_id")
    with get_db_connection() as conn:
        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND employee_id = ? AND status = 'Pending'",
            (req_id, employee_id),
        ).fetchone()

        if req:
            conn.execute(
                "UPDATE service_requests SET status = 'Accepted' WHERE id = ?",
                (req_id,),
            )
            conn.execute(
                "UPDATE users SET availability = 'BOOKED' WHERE id = ?", (employee_id,)
            )

            # Notify user
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (
                    req["user_id"],
                    "Your service request has been accepted. The professional will contact you soon.",
                ),
            )
            conn.commit()
            flash("Service request accepted.", "success")
        else:
            flash("Service request not found or not pending.", "error")

    return redirect(url_for("dashboard_employee"))


@app.route("/reject_service/<int:req_id>", methods=["POST"])
@login_required("employee")
def reject_service(req_id):
    employee_id = session.get("user_id")
    with get_db_connection() as conn:
        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND employee_id = ? AND status = 'Pending'",
            (req_id, employee_id),
        ).fetchone()

        if req:
            conn.execute(
                "UPDATE service_requests SET status = 'Rejected' WHERE id = ?",
                (req_id,),
            )

            # Notify user
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (
                    req["user_id"],
                    "Your service request has been declined. Please try booking another professional.",
                ),
            )
            conn.commit()
            flash("Service request declined.", "success")
        else:
            flash("Service request not found or not pending.", "error")

    return redirect(url_for("dashboard_employee"))


@app.route("/complete_service/<int:req_id>", methods=["POST"])
@login_required("employee")
def complete_service(req_id):
    employee_id = session.get("user_id")
    with get_db_connection() as conn:
        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND employee_id = ? AND status = 'Accepted'",
            (req_id, employee_id),
        ).fetchone()

        if req:
            conn.execute(
                "UPDATE service_requests SET status = 'Completed' WHERE id = ?",
                (req_id,),
            )
            conn.execute(
                "UPDATE users SET availability = 'AVAILABLE' WHERE id = ?",
                (employee_id,),
            )

            # Message to user
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (
                    req["user_id"],
                    "Your service has been marked as completed. Please rate the professional in your dashboard.",
                ),
            )

            conn.commit()
            flash("Service marked as completed.", "success")
        else:
            flash("Service request not found or not in progress.", "error")

    return redirect(url_for("dashboard_employee"))


@app.route("/add_deposit", methods=["POST"])
@login_required("employee")
def add_deposit():
    amount_str = request.form.get("amount")
    try:
        amount = float(amount_str or 0)
        if amount <= 0:
            flash("Deposit amount must be greater than zero.", "error")
            return redirect(url_for("dashboard_employee"))

        try:
            key_id = os.environ.get("RAZORPAY_KEY_ID")
            key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
            client = razorpay.Client(auth=(key_id, key_secret))
            order = client.order.create(  # type: ignore # pylint: disable=no-member
                {
                    "amount": int(amount * 100),  # converting to paise
                    "currency": "INR",
                    "payment_capture": 1,
                }
            )
            return render_template(
                "payment.html",
                key_id=key_id,
                order_id=order["id"],
                amount=amount,
                role="employee",
            )
        except (razorpay.errors.BadRequestError, razorpay.errors.GatewayError, razorpay.errors.ServerError) as e:
            flash(f"Payment gateway error: {e}", "error")
            return redirect(url_for("dashboard_employee"))

    except (ValueError, TypeError):
        flash("Invalid deposit amount.", "error")
        return redirect(url_for("dashboard_employee"))


@app.route("/complete_deposit", methods=["POST"])
@csrf.exempt
def complete_deposit():
    user_id = session.get("user_id")
    role = request.form.get("role")
    amount_str = request.form.get("amount")
    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")

    if not user_id or not amount_str or not payment_id:
        flash("Payment verification failed.", "error")
        return redirect(url_for("index"))

    try:
        # Verify Razorpay payment signature
        key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
        if order_id and signature and key_secret:
            generated_signature = hmac.new(
                key_secret.encode("utf-8"),
                f"{order_id}|{payment_id}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()  # hmac.new is Python 3 compatible here
            if not hmac.compare_digest(generated_signature, signature):
                flash("Payment verification failed. Invalid signature.", "error")
                if role == "employee":
                    return redirect(url_for("dashboard_employee"))
                return redirect(url_for("dashboard_user"))

        amount = float(amount_str)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET deposit_balance = COALESCE(deposit_balance, 0) + ? WHERE id = ?",
                (amount, user_id),
            )
            conn.commit()
        flash(
            f"Payment successful! Successfully added ₹{amount} to your deposit balance.",
            "success",
        )
    except sqlite3.Error:
        flash("An error occurred while updating the balance.", "error")

    if role == "employee":
        return redirect(url_for("dashboard_employee"))
    else:
        return redirect(url_for("dashboard_user"))


def send_reset_email(to_email, link):
    subject = "Rent Hub - Password Reset Request"
    body = f"Click the link to reset your password: {link}"
    send_email_notification(to_email, subject, body)


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("gmail") or request.form.get("email")
        if email:
            email = email.strip().lower()
        if not email:
            flash("Please enter your email.", "error")
            return render_template("forgot_password.html")

        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE gmail = ?", (email,)
            ).fetchone()
            if user:
                token = s.dumps(email, salt="password-reset-salt")
                link = url_for("reset_password", token=token, _external=True)
                send_reset_email(email, link)
                flash("Password reset link sent to your email", "success")
            else:
                flash("Email not found", "error")

    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=3600)
    except BadData:
        flash("Link expired or invalid", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not new_password or new_password != confirm_password:
            flash("Passwords do not match or are empty.", "error")
            return render_template("reset_password.html", token=token)

        hashed_password = generate_password_hash(new_password)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET password = ? WHERE gmail = ?",
                (hashed_password, email),
            )
            conn.commit()

        flash("Password updated successfully. You can now login.", "success")
        return redirect(url_for("index"))

    return render_template("reset_password.html", token=token)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true")
