from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
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
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
import hmac
import hashlib
from itsdangerous import URLSafeTimedSerializer

import razorpay

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError('SECRET_KEY environment variable is not set! Create a .env file.')

s = URLSafeTimedSerializer(app.secret_key)

# Session cookie security
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)




# (Session cookie settings already applied above via app.config.update)

# CSRF Protection
csrf = CSRFProtect(app)

# Email Configuration using Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_SENDER', 'your_email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your_app_password')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)

MAIL_SENDER = app.config['MAIL_USERNAME']
MAIL_PASSWORD = app.config['MAIL_PASSWORD']

def send_email_notification(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_SENDER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(MAIL_SENDER, MAIL_PASSWORD)
        server.sendmail(MAIL_SENDER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email could not be sent: {e}")
        return False
def send_employee_credentials(email, username, password):
    try:
        subject = "Rent Hub Employee Account Approved"
        login_link = url_for('employee', _external=True)
        
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
    except Exception as e:
        print(f"Employee credentials email could not be sent: {e}")
        return False

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Login required decorator to protect dashboard routes
def login_required(role_required=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'error')
                return redirect(url_for('index'))

            if role_required and session.get('role') != role_required:
                flash('You do not have permission to access that page.', 'error')
                return redirect(url_for('index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('auth_user') or request.form.get('username')
    password = request.form.get('auth_pass') or request.form.get('password')

    if not username or not password:
        flash('Missing credentials.', 'error')
        return redirect(url_for('index'))

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND account_status = 'approved'",
            (username,)
        ).fetchone()

        if user and check_password_hash(user['password'], password):
            conn.execute("UPDATE users SET is_online = 1 WHERE id = ?", (user['id'],))
            conn.commit()
            session.clear()
            session.permanent = False
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            
            if user['role'] == 'admin':
                return redirect(url_for('dashboard_admin'))
            elif user['role'] == 'employee':
                return redirect(url_for('dashboard_employee'))
            else:
                return redirect(url_for('dashboard_user'))
        else:
            flash('Invalid credentials or account not approved.', 'error')
            return redirect(url_for('index'))


def process_login(request, expected_role, template, success_redirect):
    if request.method == 'POST':
        username = (request.form.get('username') or
                    request.form.get('adm_user') or
                    request.form.get('usr_user') or
                    request.form.get('emp_user'))
        password = (request.form.get('password') or
                    request.form.get('adm_pass') or
                    request.form.get('usr_pass') or
                    request.form.get('emp_pass'))

        if not username or not password:
            flash('Missing credentials.', 'error')
            return render_template(template)

        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ? AND role = ? AND account_status = 'approved'",
                (username, expected_role)
            ).fetchone()

            if user and check_password_hash(user['password'], password):
                conn.execute("UPDATE users SET is_online = 1 WHERE id = ?", (user['id'],))
                conn.commit()
                session.clear()
                session.permanent = False
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                flash('Login successful!', 'success')
                return redirect(url_for(success_redirect))
            else:
                flash('Invalid credentials or role.', 'error')

    return render_template(template)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    return process_login(request, 'admin', 'admin_login.html', 'dashboard_admin')


@app.route('/user', methods=['GET', 'POST'])
def user():
    return process_login(request, 'user', 'user_login.html', 'dashboard_user')


@app.route('/register_user', methods=['POST'])
def register_user():
    username = request.form.get('username') or request.form.get('usr_user')
    password = request.form.get('password') or request.form.get('usr_pass')
    gmail = request.form.get('gmail')
    if gmail:
        gmail = gmail.strip().lower()

    if not username or not password or not gmail:
        flash('Please fill all fields.', 'error')
        return redirect(url_for('user'))

    try:
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT * FROM users WHERE (username = ? AND role = 'user') OR gmail = ?", 
                (username, gmail)
            ).fetchone()
            
            if existing:
                if existing['username'] == username and existing['role'] == 'user':
                    flash(f'Username "{username}" is already taken by another user.', 'error')
                else:
                    flash(f'Gmail ID "{gmail}" is already registered.', 'error')
                return redirect(url_for('user'))

            conn.commit()

            conn.execute("UPDATE users SET is_online = 1 WHERE id = ?", (user_id,))
            conn.commit()

            session.clear()
            session['user_id'] = user_id
            session['username'] = username
            session['role'] = 'user'

            flash('Registered and logged in successfully!', 'success')
            return redirect(url_for('dashboard_user'))
    except Exception as e:
        print(f"Registration error: {e}")
        flash('An error occurred during registration.', 'error')
        return redirect(url_for('user'))


@app.route('/register_employee', methods=['POST'])
def register_employee():
    username = request.form.get('username') or request.form.get('emp_user')
    gmail = request.form.get('gmail')
    if gmail:
        gmail = gmail.strip().lower()
    work_details_list = request.form.getlist('work_details')
    work_details = ", ".join(work_details_list) if work_details_list else ""

    if not username or not gmail or not work_details:
        flash('Please fill all fields.', 'error')
        return redirect(url_for('employee'))

    try:
        with get_db_connection() as conn:
            # For employee registration, we check if there's an existing employee with this username
            # or ANY existing user with this gmail ID.
            existing = conn.execute(
                "SELECT * FROM users WHERE (username = ? AND role = 'employee') OR gmail = ?",
                (username, gmail)
            ).fetchone()
            if existing:
                if existing['username'] == username and existing['role'] == 'employee':
                    flash(f'Username "{username}" is already taken by another employee.', 'error')
                else:
                    flash(f'Gmail ID "{gmail}" is already registered.', 'error')
                return redirect(url_for('employee'))

            cursor = conn.execute(
                'INSERT INTO users (username, password, role, gmail, work_details, account_status, availability) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (username, 'pending_setup', 'employee', gmail, work_details, 'pending', 'AVAILABLE')
            )
            user_id = cursor.lastrowid

            conn.commit()

            flash('Registration successful! Please wait for approval.', 'success')
            return redirect(url_for('index'))
    except Exception:
        flash('An error occurred during registration.', 'error')
        return redirect(url_for('employee'))


@app.route('/employee', methods=['GET', 'POST'])
def employee():
    return process_login(request, 'employee', 'employee_login.html', 'dashboard_employee')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    user_id = session.get('user_id')
    if user_id:
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET is_online = 0 WHERE id = ?", (user_id,))
            conn.commit()
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard_admin')
@login_required('admin')
def dashboard_admin():
    admin_id = session.get('user_id')
    with get_db_connection() as conn:
        admin_info = conn.execute("SELECT * FROM users WHERE id = ?", (admin_id,)).fetchone()
        users = conn.execute(
            "SELECT id, username, password, account_status, is_online, profile_pic FROM users WHERE role = 'user'"
        ).fetchall()
        employees = conn.execute(
            "SELECT id, username, password, account_status, availability, is_online, profile_pic FROM users WHERE role = 'employee' AND account_status IN ('approved', 'blocked')"
        ).fetchall()
        try:
            pending_employees = conn.execute(
                "SELECT * FROM users WHERE role = 'employee' AND account_status = 'pending'"
            ).fetchall()
        except sqlite3.OperationalError:
            pending_employees = []

        try:
            requests_list = conn.execute(
                "SELECT r.id, u.username, u.profile_pic, r.item_name, r.status FROM requests r JOIN users u ON r.user_id = u.id"
            ).fetchall()
        except sqlite3.OperationalError:
            requests_list = []

        try:
            withdrawal_requests = conn.execute(
                "SELECT w.id, w.amount, w.status, w.requested_at, u.username, u.role, u.gmail, u.profile_pic, w.bank_details "
                "FROM withdrawal_requests w JOIN users u ON w.user_id = u.id "
                "WHERE w.status = 'Pending' ORDER BY w.id DESC"
            ).fetchall()
        except sqlite3.OperationalError:
            withdrawal_requests = []

        try:
            upi_withdraw_requests = conn.execute(
                "SELECT w.id, w.amount, w.upi_id, w.status, u.username "
                "FROM withdraw_requests w JOIN users u ON w.user_id = u.id "
                "WHERE w.status = 'Pending' ORDER BY w.id DESC"
            ).fetchall()
        except sqlite3.OperationalError:
            upi_withdraw_requests = []

    return render_template('dashboard_admin.html',
                           admin_info=admin_info,
                           users=users,
                           employees=employees,
                           pending_employees=pending_employees,
                           requests_list=requests_list,
                           withdrawal_requests=withdrawal_requests,
                           upi_withdraw_requests=upi_withdraw_requests)

@app.route('/admin_handle_withdrawal/<int:req_id>/<action>', methods=['POST'])
@login_required('admin')
def admin_handle_withdrawal(req_id, action):
    if action not in ('approve', 'reject'):
        flash("Invalid action.", "error")
        return redirect(url_for('dashboard_admin'))

    with get_db_connection() as conn:
        req = conn.execute("SELECT * FROM withdrawal_requests WHERE id = ? AND status = 'Pending'", (req_id,)).fetchone()
        if req:
            new_status = 'Approved' if action == 'approve' else 'Rejected'
            conn.execute("UPDATE withdrawal_requests SET status = ? WHERE id = ?", (new_status, req_id))
            
            if action == 'reject':
                conn.execute(
                    "UPDATE users SET deposit_balance = deposit_balance + ? WHERE id = ?",
                    (req['amount'], req['user_id'])
                )
            
            user = conn.execute("SELECT * FROM users WHERE id = ?", (req['user_id'],)).fetchone()
            if user:
                msg = f"Your withdrawal request of ₹{req['amount']} has been {new_status.lower()}."
                if user['role'] == 'employee' and user['gmail']:
                    conn.execute("INSERT INTO employee_messages (gmail, message) VALUES (?, ?)", (user['gmail'], msg))
                else:
                    conn.execute("INSERT INTO user_messages (user_id, message) VALUES (?, ?)", (user['id'], msg))
            
            conn.commit()
            flash(f"Withdrawal request has been {new_status.lower()}.", 'success')
        else:
            flash("Withdrawal request not found or already processed.", "error")

    return redirect(url_for('dashboard_admin'))


@app.route('/view_service/<path:service_name>')
@login_required('user')
def view_service(service_name):
    with get_db_connection() as conn:
        providers = conn.execute(
            "SELECT * FROM users WHERE role = 'employee' AND account_status = 'approved' AND work_details LIKE ?",
            (f'%{service_name}%',)
        ).fetchall()
        
    return render_template('service_providers.html', service_name=service_name, providers=providers)


@app.route('/user_employee_details/<int:emp_id>')
@login_required('user')
def user_employee_details(emp_id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)
        ).fetchone()
        if not employee:
            flash("Professional not found.", "error")
            return redirect(url_for('dashboard_user'))
    return render_template('user_employee_details.html', employee=employee)

@app.route('/rate_profile/<int:emp_id>', methods=['POST'])
@login_required('user')
def rate_profile(emp_id):
    data = request.get_json()
    if not data or 'rating' not in data:
        return jsonify({"error": "No rating provided"}), 400
        
    try:
        rating_val = int(data['rating'])
        if rating_val < 1 or rating_val > 5:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Invalid rating value"}), 400

    with get_db_connection() as conn:
        emp = conn.execute("SELECT rating, rating_count FROM users WHERE id = ? AND role = 'employee'", (emp_id,)).fetchone()
        if not emp:
            return jsonify({"error": "Professional not found"}), 404
            
        curr_rating = emp['rating'] or 0.0
        curr_count = emp['rating_count'] or 0
        
        new_count = curr_count + 1
        new_rating = ((curr_rating * curr_count) + rating_val) / new_count
        
        conn.execute(
            "UPDATE users SET rating = ?, rating_count = ? WHERE id = ?",
            (new_rating, new_count, emp_id)
        )
        conn.commit()
        
    return jsonify({
        "message": "Rating saved",
        "average": new_rating
    })


@app.route('/user_add_deposit', methods=['POST'])
@login_required('user')
def user_add_deposit():
    user_id = session.get('user_id')
    amount_str = request.form.get('amount')
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Deposit amount must be greater than zero.", "error")
            return redirect(url_for('dashboard_user'))
            
        try:
            key_id = os.environ.get("RAZORPAY_KEY_ID")
            key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
            client = razorpay.Client(auth=(key_id, key_secret))
            order = client.order.create({
                "amount": int(amount * 100),  # converting to paise
                "currency": "INR",
                "payment_capture": 1
            })
            return render_template('payment.html', key_id=key_id, order_id=order['id'], amount=amount, role='user')


        except Exception as e:
            flash(f"Payment gateway error: {e}", "error")
            return redirect(url_for('dashboard_user'))
            
    except (ValueError, TypeError):
        flash("Invalid deposit amount.", "error")
        return redirect(url_for('dashboard_user'))

@app.route('/user_withdraw_deposit', methods=['POST'])
@login_required('user')
def user_withdraw_deposit():
    user_id = session.get('user_id')
    amount_str = request.form.get('amount')
    confirmed = request.form.get('confirmed')
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Withdrawal amount must be greater than zero.", "error")
            return redirect(url_for('dashboard_user'))
    except (ValueError, TypeError):
        flash("Invalid withdrawal amount.", "error")
        return redirect(url_for('dashboard_user'))
        
    with get_db_connection() as conn:
        user = conn.execute("SELECT deposit_balance, bank_name, bank_branch, bank_account_name, bank_account_number, bank_ifsc FROM users WHERE id = ?", (user_id,)).fetchone()
        current_balance = user['deposit_balance'] or 0.0
        
        if amount > current_balance:
            flash(f"Insufficient deposit balance. You can withdraw up to ₹{current_balance}.", "error")
            return redirect(url_for('dashboard_user'))
            
        if confirmed != 'true':
            return render_template('withdraw_form.html', amount=amount, post_action=url_for('user_withdraw_deposit'), user_bank=user)
            
        status = 'Pending' if (current_balance - amount) < 500 else 'Approved'
        
        conn.execute(
            "UPDATE users SET deposit_balance = deposit_balance - ? WHERE id = ?",
            (amount, user_id)
        )
        bank_details = ""
        if confirmed == 'true':
            account_name = request.form.get('account_name', '')
            acc_number = request.form.get('account_number', '')
            ifsc = request.form.get('ifsc_code', '')
            bank_details = f"Name: {account_name}, A/C: {acc_number}, IFSC: {ifsc}"

            if account_name and acc_number and ifsc:
                conn.execute(
                    "UPDATE users SET bank_account_name = ?, bank_account_number = ?, bank_ifsc = ? WHERE id = ?",
                    (account_name, acc_number, ifsc, user_id)
                )

        conn.execute(
            "INSERT INTO withdrawal_requests (user_id, amount, status, bank_details) VALUES (?, ?, ?, ?)",
            (user_id, amount, status, bank_details)
        )
        
        if status == 'Approved':
            msg = f"Your withdrawal of ₹{amount} has been approved."
            conn.execute("INSERT INTO user_messages (user_id, message) VALUES (?, ?)", (user_id, msg))
            
        conn.commit()
        
    if status == 'Pending':
        flash(f"Withdrawal request for ₹{amount} submitted for admin approval.", "success")
    else:
        flash(f"Withdrawal of ₹{amount} processed successfully.", "success")
        
    return redirect(url_for('dashboard_user'))


@app.route('/dashboard_user')
@login_required('user')
def dashboard_user():
    user_id = session.get('user_id')
    with get_db_connection() as conn:
        user_info = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


        try:
            user_messages = conn.execute(
                "SELECT * FROM user_messages WHERE user_id = ? ORDER BY id DESC", (user_id,)
            ).fetchall()
        except sqlite3.OperationalError:
            user_messages = []

        try:
            res = conn.execute(
                "SELECT SUM(amount) as pending_total FROM withdrawal_requests WHERE user_id = ? AND status = 'Pending'",
                (user_id,)
            ).fetchone()
            pending_total = res['pending_total'] if res and res['pending_total'] else 0.0
        except sqlite3.OperationalError:
            pending_total = 0.0

        try:
            transactions = conn.execute(
                "SELECT amount, status, requested_at, bank_details FROM withdrawal_requests WHERE user_id = ? ORDER BY id DESC",
                (user_id,)
            ).fetchall()
        except sqlite3.OperationalError:
            transactions = []
            
        # Fetch user's service bookings
        try:
            bookings = conn.execute(
                """
                SELECT sr.id, sr.status, sr.rating, u.username as employee_name, u.gmail as employee_gmail, u.id as employee_id
                FROM service_requests sr
                JOIN users u ON sr.employee_id = u.id
                WHERE sr.user_id = ?
                ORDER BY sr.id DESC
                """, (user_id,)
            ).fetchall()
        except sqlite3.OperationalError:
            bookings = []

    return render_template('dashboard_user.html',
                           user_info=user_info,
                           pending_withdrawals=pending_total,
                           bookings=bookings,
                           transactions=transactions)


@app.route('/dashboard_employee')
@login_required('employee')
def dashboard_employee():
    user_id = session.get('user_id')
    with get_db_connection() as conn:
        employee = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        emp_messages = []
        service_requests = []
        if employee:
            try:
                emp_messages = conn.execute(
                    "SELECT * FROM employee_messages WHERE gmail = ? ORDER BY id DESC",
                    (employee['gmail'],)
                ).fetchall()
                
                service_requests = conn.execute(
                    """
                    SELECT sr.id, sr.status, sr.rating, u.username as user_name, u.gmail as user_gmail, u.profile_pic 
                    FROM service_requests sr
                    JOIN users u ON sr.user_id = u.id
                    WHERE sr.employee_id = ?
                    ORDER BY sr.id DESC
                    """, (user_id,)
                ).fetchall()
                
                pending_withdrawals = conn.execute(
                    "SELECT SUM(amount) as pending_total FROM withdrawal_requests WHERE user_id = ? AND status = 'Pending'",
                    (user_id,)
                ).fetchone()
                pending_total = pending_withdrawals['pending_total'] if pending_withdrawals and pending_withdrawals['pending_total'] else 0.0
                
                transactions = conn.execute(
                    "SELECT amount, status, requested_at, bank_details FROM withdrawal_requests WHERE user_id = ? ORDER BY id DESC",
                    (user_id,)
                ).fetchall()
                
            except sqlite3.OperationalError:
                emp_messages = []
                service_requests = []
                pending_total = 0.0
                transactions = []
        else:
            pending_total = 0.0
            transactions = []

    return render_template('dashboard_employee.html',
                           employee=employee,
                           service_requests=service_requests,
                           pending_withdrawals=pending_total,
                           transactions=transactions)


@app.route('/update_employee', methods=['POST'])
@login_required('employee')
def update_employee():
    user_id = session.get('user_id')
    new_username = request.form.get('username')
    new_password = request.form.get('password')
    new_phone = request.form.get('gmail')
    if new_phone:
        new_phone = new_phone.strip().lower()
    new_work_list = request.form.getlist('work_details')
    new_work = ", ".join(new_work_list) if new_work_list else ""
    


    if not new_username or not new_phone:
        flash('Please fill out all required fields.', 'error')
        return redirect(url_for('dashboard_employee'))

    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE ((username = ? AND role = 'employee') OR gmail = ?) AND id != ?", (new_username, new_phone, user_id)
        ).fetchone()
        if existing:
            if existing['username'] == new_username and existing['role'] == 'employee':
                flash(f'Username "{new_username}" is already taken by another employee.', 'error')
            else:
                flash(f'Gmail ID "{new_phone}" is already registered to another user.', 'error')
            return redirect(url_for('dashboard_employee'))

        updates = ["username = ?", "gmail = ?", "work_details = ?"]
        params = [new_username, new_phone, new_work]
        
        if new_password:
            updates.append("password = ?")
            params.append(generate_password_hash(new_password))
            

            
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        
        session['username'] = new_username
        flash('Your details have been updated successfully.', 'success')

    return redirect(url_for('dashboard_employee'))


@app.route('/update_employee_availability', methods=['POST'])
@login_required('employee')
def update_employee_availability():
    user_id = session.get('user_id')
    new_timing = request.form.get('availability')

    VALID_AVAILABILITY = ('AVAILABLE', 'NOT AVAILABLE', 'BOOKED')
    if new_timing and new_timing in VALID_AVAILABILITY:
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE users SET availability = ? WHERE id = ?
            """, (new_timing, user_id))
            conn.commit()
            flash('Availability updated successfully.', 'success')
    elif new_timing:
        flash('Invalid availability value.', 'error')

    return redirect(url_for('dashboard_employee'))


@app.route('/update_admin', methods=['POST'])
@login_required('admin')
def update_admin():
    user_id = session.get('user_id')
    new_username = request.form.get('username')
    new_password = request.form.get('password')
    new_phone = request.form.get('gmail')
    if new_phone:
        new_phone = new_phone.strip().lower()
    new_work_list = request.form.getlist('work_details')
    new_work = ", ".join(new_work_list) if new_work_list else ""
    


    if not new_username:
        flash('Username is required.', 'error')
        return redirect(url_for('dashboard_admin'))

    with get_db_connection() as conn:
        
        updates = ["username = ?"]
        params = [new_username]
        
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
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        
        session['username'] = new_username
        flash('Your details have been updated successfully.', 'success')

    return redirect(url_for('dashboard_admin'))

@app.route('/update_user', methods=['POST'])
@login_required('user')
def update_user():
    user_id = session.get('user_id')
    new_username = request.form.get('username')
    new_password = request.form.get('password')
    new_phone = request.form.get('gmail')
    if new_phone:
        new_phone = new_phone.strip().lower()
        


    if not new_username:
        flash('Username is required.', 'error')
        return redirect(url_for('dashboard_user'))

    with get_db_connection() as conn:
        # Check for existing user/gmail
        if new_phone:
            existing = conn.execute(
                "SELECT * FROM users WHERE ((username = ? AND role = 'user') OR gmail = ?) AND id != ?", (new_username, new_phone, user_id)
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT * FROM users WHERE (username = ? AND role = 'user') AND id != ?", (new_username, user_id)
            ).fetchone()
            
        if existing:
            if existing['username'] == new_username and existing['role'] == 'user':
                flash(f'Username "{new_username}" is already taken by another user.', 'error')
            else:
                flash(f'Gmail ID "{new_phone}" is already registered to another user.', 'error')
            return redirect(url_for('dashboard_user'))

        updates = ["username = ?", "gmail = ?"]
        params = [new_username, new_phone]
        
        if new_password:
            updates.append("password = ?")
            params.append(generate_password_hash(new_password))

            
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        
        session['username'] = new_username
        flash('Your details have been updated successfully.', 'success')

    return redirect(url_for('dashboard_user'))

@app.route('/remove_user_accept_employee') 
def remove_user_accept_employee():
    return redirect(url_for('dashboard_user'))


@app.route('/admin_accept_employee/<int:emp_id>', methods=['POST'])
@login_required('admin')
def admin_accept_employee(emp_id):
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    with get_db_connection() as conn:
        emp = conn.execute("SELECT * FROM users WHERE id = ?", (emp_id,)).fetchone()
        if emp and emp['account_status'] == 'pending':
            hashed_password = generate_password_hash(password)
            conn.execute(
                "UPDATE users SET password = ?, account_status = 'approved' WHERE id = ?",
                (hashed_password, emp_id)
            )
            message = f"Your employee application for Rent Hub has been approved.\n\nYour login details are as follows:\nUsername: {emp['username']}\nPassword: {password}\n\nPlease keep these details secure."
            conn.execute(
                "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                (emp['gmail'], message)
            )
            conn.commit()
            
            # Send actual email
            send_employee_credentials(emp['gmail'], emp['username'], password)
            
            flash(f"Employee {emp['username']} accepted. Login details sent to their email.", 'success')
    return redirect(url_for('dashboard_admin'))


@app.route('/admin_reject_employee/<int:emp_id>', methods=['POST'])
@login_required('admin')
def admin_reject_employee(emp_id):
    with get_db_connection() as conn:
        emp = conn.execute("SELECT * FROM users WHERE id = ?", (emp_id,)).fetchone()
        if emp and emp['account_status'] == 'pending':
            conn.execute("UPDATE users SET account_status = 'rejected' WHERE id = ?", (emp_id,))
            conn.execute(
                "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                (emp['gmail'], "Your employee application has been rejected.")
            )
            conn.commit()
            flash(f"Employee {emp['username']} rejected.", 'success')
    return redirect(url_for('dashboard_admin'))


@app.route('/admin_toggle_block/<int:user_id>', methods=['POST'])
@login_required('admin')
def admin_toggle_block(user_id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            new_status = 'blocked' if user['account_status'] != 'blocked' else 'approved'
            conn.execute("UPDATE users SET account_status = ? WHERE id = ?", (new_status, user_id))

            if user['role'] == 'employee' and user['gmail']:
                msg = f"Your account has been {new_status} by the administrator."
                conn.execute(
                    "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                    (user['gmail'], msg)
                )
            elif user['role'] == 'user':
                msg = f"Your account has been {new_status} by the administrator."
                conn.execute(
                    "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                    (user_id, msg)
                )

            conn.commit()
            flash(f"Account {user['username']} is now {new_status}.", 'success')
    return redirect(request.referrer or url_for('dashboard_admin'))


@app.route('/admin_user_details/<int:user_id>')
@login_required('admin')
def admin_user_details(user_id):
    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'user'", (user_id,)
        ).fetchone()
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('dashboard_admin'))
    return render_template('admin_user_details.html', user=user)


@app.route('/admin_warn_user/<int:user_id>', methods=['POST'])
@login_required('admin')
def admin_warn_user(user_id):
    warning_text = request.form.get('warning_message')
    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'user'", (user_id,)
        ).fetchone()
        if user and warning_text:
            msg = f"WARNING from Admin: {warning_text}"
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (user_id, msg)
            )
            conn.commit()
            flash(f"Warning sent to {user['username']}.", "success")
        else:
            flash("Failed to send warning.", "error")
    return redirect(url_for('admin_user_details', user_id=user_id))


@app.route('/admin_employee_details/<int:emp_id>')
@login_required('admin')
def admin_employee_details(emp_id):
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)
        ).fetchone()
        if not employee:
            flash("Employee not found.", "error")
            return redirect(url_for('dashboard_admin'))
        
        # Fetch withdrawal history for this employee
        withdrawals = conn.execute(
            "SELECT * FROM withdrawal_requests WHERE user_id = ? ORDER BY id DESC",
            (emp_id,)
        ).fetchall()
        
        import datetime
        current_month = datetime.datetime.now().strftime('%Y-%m')
        work_done_row = conn.execute(
            "SELECT COUNT(*) as count FROM service_requests WHERE employee_id = ? AND status = 'Completed' AND strftime('%Y-%m', created_at) = ?",
            (emp_id, current_month)
        ).fetchone()
        work_done_month = work_done_row['count'] if work_done_row else 0
        
    return render_template('admin_employee_details.html', employee=employee, withdrawals=withdrawals, work_done_month=work_done_month)


@app.route('/admin_warn_employee/<int:emp_id>', methods=['POST'])
@login_required('admin')
def admin_warn_employee(emp_id):
    warning_text = request.form.get('warning_message')
    with get_db_connection() as conn:
        employee = conn.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)
        ).fetchone()
        if employee and warning_text:
            msg = f"WARNING from Admin: {warning_text}"
            conn.execute(
                "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                (employee['gmail'], msg)
            )
            conn.commit()
            flash(f"Warning sent to {employee['username']}.", "success")
        else:
            flash("Failed to send warning.", "error")
    return redirect(url_for('admin_employee_details', emp_id=emp_id))


@app.route('/admin_update_request/<int:req_id>/<action>', methods=['POST'])
@login_required('admin')
def admin_update_request(req_id, action):
    if action not in ('accept', 'reject'):
        flash("Invalid action.", "error")
        return redirect(url_for('dashboard_admin'))

    new_status = 'Approved' if action == 'accept' else 'Rejected'

    with get_db_connection() as conn:
        req = conn.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
        if req:
            conn.execute("UPDATE requests SET status = ? WHERE id = ?", (new_status, req_id))
            conn.commit()
            flash(f"Request '{req['item_name']}' has been {new_status.lower()}.", 'success')
        else:
            flash("Request not found.", "error")

    return redirect(url_for('dashboard_admin'))


@app.route('/book_service/<int:emp_id>', methods=['POST'])
@login_required('user')
def book_service(emp_id):
    user_id = session.get('user_id')
    with get_db_connection() as conn:
        employee = conn.execute("SELECT * FROM users WHERE id = ? AND role = 'employee'", (emp_id,)).fetchone()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        
        if employee and user:
            emp_availability = (employee['availability'] or 'AVAILABLE').strip().upper()
            if emp_availability == 'BOOKED':
                flash(f"Professional '{employee['username']}' is currently booked.", "error")
                return redirect(request.referrer or url_for('dashboard_user'))
            
            if emp_availability == 'NOT AVAILABLE':
                flash(f"Professional '{employee['username']}' is not available.", "error")
                return redirect(request.referrer or url_for('dashboard_user'))

            if (user['deposit_balance'] or 0.0) < 500.0:
                flash("You cannot book this service because your advance deposit balance is below ₹500.", "error")
                return redirect(request.referrer or url_for('dashboard_user'))

            if (employee['deposit_balance'] or 0.0) < 2000.0:
                flash(f"Professional '{employee['username']}' is currently not accepting requests (advance deposit below ₹2000).", "error")
                return redirect(request.referrer or url_for('dashboard_user'))
                
            existing = conn.execute("SELECT * FROM service_requests WHERE user_id = ? AND employee_id = ? AND status = 'Pending'", (user_id, emp_id)).fetchone()
            if existing:
                flash(f"You already have a pending request for {employee['username']}.", "error")
            else:
                conn.execute(
                    "INSERT INTO service_requests (user_id, employee_id, status) VALUES (?, ?, 'Pending')",
                    (user_id, emp_id)
                )
                
                # Send a notification message to the user
                user_msg = f"Your booking request has been sent to '{employee['username']}'. Please wait for their acceptance."
                conn.execute(
                    "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                    (user_id, user_msg)
                )

                # Send a notification message to the employee
                deposit_balance = employee['deposit_balance'] or 0.0
                emp_msg = f"You received a new service request from {user['username']}. Your current Advance Deposit balance is ₹{deposit_balance}."
                conn.execute(
                    "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                    (employee['gmail'], emp_msg)
                )

                conn.commit()
                flash(f"Booking request sent successfully to {employee['username']}!", 'success')
        else:
            flash("Failed to send booking request. Employee not found.", "error")
            
    return redirect(request.referrer or url_for('dashboard_user'))


@app.route('/employee_handle_request/<int:req_id>/<action>', methods=['POST'])
@login_required('employee')
def employee_handle_request(req_id, action):
    employee_id = session.get('user_id')
    if action not in ('accept', 'reject'):
        flash("Invalid action.", "error")
        return redirect(url_for('dashboard_employee'))

    new_status = 'Accepted' if action == 'accept' else 'Rejected'

    with get_db_connection() as conn:
        if action == 'accept':
            emp_data = conn.execute("SELECT deposit_balance FROM users WHERE id = ?", (employee_id,)).fetchone()
            if not emp_data or (emp_data['deposit_balance'] or 0.0) < 2000.0:
                flash("You must maintain a minimum advance deposit of ₹2000 to accept new requests.", "error")
                return redirect(url_for('dashboard_employee'))

        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND employee_id = ?", 
            (req_id, employee_id)
        ).fetchone()
        
        if req:
            conn.execute("UPDATE service_requests SET status = ? WHERE id = ?", (new_status, req_id))
            
            if new_status == 'Accepted':
                conn.execute("UPDATE users SET availability = 'BOOKED' WHERE id = ?", (employee_id,))
            
            # Send a message to the user
            employee = conn.execute("SELECT username FROM users WHERE id = ?", (employee_id,)).fetchone()
            msg = f"Your service booking request with professional '{employee['username']}' has been {new_status.lower()}."
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (req['user_id'], msg)
            )
            
            conn.commit()
            flash(f"Service request has been {new_status.lower()}.", 'success')
        else:
            flash("Service request not found or not authorized.", "error")

    return redirect(url_for('dashboard_employee'))
    
@app.route('/submit_rating/<int:req_id>', methods=['POST'])
@login_required('user')
def submit_rating(req_id):
    user_id = session.get('user_id')
    rating = request.form.get('rating')
    review = request.form.get('review', '')
    
    if not rating:
        flash("Please select a rating.", "error")
        return redirect(url_for('dashboard_user'))
        
    try:
        rating_val = int(rating)
        if rating_val < 1 or rating_val > 5:
            raise ValueError
    except ValueError:
        flash("Invalid rating value.", "error")
        return redirect(url_for('dashboard_user'))

    with get_db_connection() as conn:
        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND user_id = ? AND status = 'Completed'",
            (req_id, user_id)
        ).fetchone()
        
        if req:
            if req['rating'] is not None:
                flash("You have already rated this service.", "error")
                return redirect(url_for('dashboard_user'))
                
            conn.execute(
                "UPDATE service_requests SET rating = ?, review = ? WHERE id = ?",
                (rating_val, review, req_id)
            )
            
            # Update employee average rating
            emp_id = req['employee_id']
            emp_stats = conn.execute(
                "SELECT rating, rating_count FROM users WHERE id = ?", (emp_id,)
            ).fetchone()
            
            curr_rating = emp_stats['rating'] or 0.0
            curr_count = emp_stats['rating_count'] or 0
            
            new_count = curr_count + 1
            new_rating = ((curr_rating * curr_count) + rating_val) / new_count
            
            conn.execute(
                "UPDATE users SET rating = ?, rating_count = ? WHERE id = ?",
                (new_rating, new_count, emp_id)
            )
            
            conn.commit()
            flash("Thank you for your feedback!", "success")
        else:
            flash("Service request not found or not eligible for rating.", "error")
            
    return redirect(url_for('dashboard_user'))

@app.route('/complete_service/<int:req_id>', methods=['POST'])
@login_required('employee')
def complete_service(req_id):
    employee_id = session.get('user_id')
    with get_db_connection() as conn:
        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND employee_id = ? AND status = 'Accepted'",
            (req_id, employee_id)
        ).fetchone()
        
        if req:
            conn.execute("UPDATE service_requests SET status = 'Completed' WHERE id = ?", (req_id,))
            conn.execute("UPDATE users SET availability = 'AVAILABLE' WHERE id = ?", (employee_id,))
            
            # Message to user
            conn.execute(
                "INSERT INTO user_messages (user_id, message) VALUES (?, ?)",
                (req['user_id'], "Your service has been marked as completed. Please rate the professional in your dashboard.")
            )
            
            conn.commit()
            flash("Service marked as completed.", "success")
        else:
            flash("Service request not found or not in progress.", "error")
            
    return redirect(url_for('dashboard_employee'))

@app.route('/add_deposit', methods=['POST'])
@login_required('employee')
def add_deposit():
    employee_id = session.get('user_id')
    amount_str = request.form.get('amount')
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Deposit amount must be greater than zero.", "error")
            return redirect(url_for('dashboard_employee'))
            
        try:
            key_id = os.environ.get("RAZORPAY_KEY_ID")
            key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
            client = razorpay.Client(auth=(key_id, key_secret))
            order = client.order.create({
                "amount": int(amount * 100),  # converting to paise
                "currency": "INR",
                "payment_capture": 1
            })
            return render_template('payment.html', key_id=key_id, order_id=order['id'], amount=amount, role='employee')
        except Exception as e:
            flash(f"Payment gateway error: {e}", "error")
            return redirect(url_for('dashboard_employee'))
            
    except (ValueError, TypeError):
        flash("Invalid deposit amount.", "error")
        return redirect(url_for('dashboard_employee'))

@app.route('/complete_deposit', methods=['POST'])
@csrf.exempt
def complete_deposit():
    user_id = session.get('user_id')
    role = request.form.get('role')
    amount_str = request.form.get('amount')
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    
    if not user_id or not amount_str or not payment_id:
        flash("Payment verification failed.", "error")
        return redirect(url_for('index'))
        
    try:
        # Verify Razorpay payment signature
        key_secret = os.environ.get('RAZORPAY_KEY_SECRET')
        if order_id and signature and key_secret:
            generated_signature = hmac.new(
                key_secret.encode('utf-8'),
                f"{order_id}|{payment_id}".encode('utf-8'),
                hashlib.sha256
            ).hexdigest()  # hmac.new is Python 3 compatible here
            if not hmac.compare_digest(generated_signature, signature):
                flash("Payment verification failed. Invalid signature.", "error")
                if role == 'employee':
                    return redirect(url_for('dashboard_employee'))
                return redirect(url_for('dashboard_user'))
        
        amount = float(amount_str)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET deposit_balance = COALESCE(deposit_balance, 0) + ? WHERE id = ?",
                (amount, user_id)
            )
            conn.commit()
        flash(f"Payment successful! Successfully added ₹{amount} to your deposit balance.", "success")
    except Exception as e:
        flash("An error occurred while updating the balance.", "error")
        
    if role == 'employee':
        return redirect(url_for('dashboard_employee'))
    else:
        return redirect(url_for('dashboard_user'))

@app.route('/withdraw_deposit', methods=['POST'])
@login_required('employee')
def withdraw_deposit():
    employee_id = session.get('user_id')
    amount_str = request.form.get('amount')
    confirmed = request.form.get('confirmed')
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Withdrawal amount must be greater than zero.", "error")
            return redirect(url_for('dashboard_employee'))
    except (ValueError, TypeError):
        flash("Invalid withdrawal amount.", "error")
        return redirect(url_for('dashboard_employee'))
        
    with get_db_connection() as conn:
        employee = conn.execute("SELECT deposit_balance, gmail, bank_name, bank_branch, bank_account_name, bank_account_number, bank_ifsc FROM users WHERE id = ?", (employee_id,)).fetchone()
        current_balance = employee['deposit_balance'] or 0.0
        
        if amount > current_balance:
            flash(f"Insufficient deposit balance. You can withdraw up to ₹{current_balance}.", "error")
            return redirect(url_for('dashboard_employee'))
            
        if confirmed != 'true':
            return render_template('withdraw_form.html', amount=amount, post_action=url_for('withdraw_deposit'), user_bank=employee)
            
        status = 'Pending' if (current_balance - amount) < 2000 else 'Approved'
            
        conn.execute(
            "UPDATE users SET deposit_balance = deposit_balance - ? WHERE id = ?",
            (amount, employee_id)
        )
        bank_details = ""
        if confirmed == 'true':
            account_name = request.form.get('account_name', '')
            acc_number = request.form.get('account_number', '')
            ifsc = request.form.get('ifsc_code', '')
            bank_details = f"Name: {account_name}, A/C: {acc_number}, IFSC: {ifsc}"

            if account_name and acc_number and ifsc:
                conn.execute(
                    "UPDATE users SET bank_account_name = ?, bank_account_number = ?, bank_ifsc = ? WHERE id = ?",
                    (account_name, acc_number, ifsc, employee_id)
                )

        conn.execute(
            "INSERT INTO withdrawal_requests (user_id, amount, status, bank_details) VALUES (?, ?, ?, ?)",
            (employee_id, amount, status, bank_details)
        )
        
        if status == 'Approved' and employee['gmail']:
            msg = f"Your withdrawal of ₹{amount} has been approved."
            conn.execute("INSERT INTO employee_messages (gmail, message) VALUES (?, ?)", (employee['gmail'], msg))
            
        conn.commit()
        
    if status == 'Pending':
        flash(f"Withdrawal request for ₹{amount} submitted for admin approval.", "success")
    else:
        flash(f"Withdrawal of ₹{amount} processed successfully.", "success")
        
    return redirect(url_for('dashboard_employee'))

@app.route('/withdraw', methods=['POST'])
@login_required()
def withdraw():
    user_id = session.get('user_id')
    role = session.get('role')
    upi = request.form.get('upi')
    amount_str = request.form.get('amount')
    dashboard_route = f'dashboard_{role}' if role in ['user', 'employee'] else 'index'

    try:
        amount = int(amount_str)
    except (ValueError, TypeError):
        flash("Invalid amount.", "error")
        return redirect(url_for(dashboard_route))

    with get_db_connection() as conn:
        user = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
        balance = user['balance'] if user else 0

        if amount > balance:
            flash("Insufficient balance", "error")
            return redirect(url_for(dashboard_route))

        # Subtract balance immediately to prevent over-withdrawal
        conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
        conn.execute("INSERT INTO withdraw_requests (user_id, upi_id, amount, status) VALUES (?, ?, ?, ?)",
                    (user_id, upi, amount, "Pending"))
        conn.commit()

    flash("Withdraw request submitted", "success")
    return redirect(url_for(dashboard_route))


@app.route('/admin_approve_upi/<int:req_id>', methods=['POST'])
@login_required('admin')
def admin_approve_upi(req_id):
    with get_db_connection() as conn:
        req = conn.execute("SELECT user_id, amount FROM withdraw_requests WHERE id=? AND status='Pending'", (req_id,)).fetchone()
        if req:
            conn.execute("UPDATE withdraw_requests SET status='Paid' WHERE id=?", (req_id,))
            conn.commit()
            flash("UPI Withdrawal Approved and marked as Paid", "success")
        else:
            flash("Request not found or already processed", "error")

    return redirect(url_for('dashboard_admin'))


@app.route('/admin_reject_upi/<int:req_id>', methods=['POST'])
@login_required('admin')
def admin_reject_upi(req_id):
    with get_db_connection() as conn:
        req = conn.execute("SELECT user_id, amount FROM withdraw_requests WHERE id=? AND status='Pending'", (req_id,)).fetchone()
        if req:
            # Refund balance
            conn.execute("UPDATE users SET balance = balance + ? WHERE id=?", (req['amount'], req['user_id']))
            conn.execute("UPDATE withdraw_requests SET status='Rejected' WHERE id=?", (req_id,))
            conn.commit()
            flash("UPI Withdrawal Rejected and amount refunded", "success")
        else:
            flash("Request not found or already processed", "error")

    return redirect(url_for('dashboard_admin'))


def send_reset_email(to_email, link):
    subject = "Rent Hub - Password Reset Request"
    body = f"Click the link to reset your password: {link}"
    send_email_notification(to_email, subject, body)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('gmail') or request.form.get('email')
        if email:
            email = email.strip().lower()
        if not email:
            flash('Please enter your email.', 'error')
            return render_template('forgot_password.html')
        
        with get_db_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE gmail = ?", (email,)).fetchone()
            if user:
                token = s.dumps(email, salt='password-reset-salt')
                link = url_for('reset_password', token=token, _external=True)
                send_reset_email(email, link)
                flash('Password reset link sent to your email', 'success')
            else:
                flash('Email not found', 'error')

    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('Link expired or invalid', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or new_password != confirm_password:
            flash('Passwords do not match or are empty.', 'error')
            return render_template('reset_password.html', token=token)
            
        hashed_password = generate_password_hash(new_password)
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET password = ? WHERE gmail = ?", (hashed_password, email))
            conn.commit()
            
        flash('Password updated successfully. You can now login.', 'success')
        return redirect(url_for('index'))
        
    return render_template('reset_password.html', token=token)


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')
