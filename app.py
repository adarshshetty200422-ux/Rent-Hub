from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3
import random
import string
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'super_secret_premium_key'

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
            "SELECT * FROM users WHERE username = ? AND password = ? AND account_status = 'approved'",
            (username, password)
        ).fetchone()

        if user:
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
                "SELECT * FROM users WHERE username = ? AND password = ? AND role = ? AND account_status = 'approved'",
                (username, password, expected_role)
            ).fetchone()

            if user:
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

    if not username or not password:
        flash('Please fill all fields.', 'error')
        return redirect(url_for('user'))

    try:
        with get_db_connection() as conn:
            existing = conn.execute("SELECT * FROM users WHERE username = ? AND role = 'user'", (username,)).fetchone()
            if existing:
                flash(f'Username "{username}" is already taken by another user.', 'error')
                return redirect(url_for('user'))

            cursor = conn.execute(
                'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                (username, password, 'user')
            )
            conn.commit()

            user_id = cursor.lastrowid
            conn.execute("UPDATE users SET is_online = 1 WHERE id = ?", (user_id,))
            conn.commit()

            session.clear()
            session['user_id'] = user_id
            session['username'] = username
            session['role'] = 'user'

            flash('Registered and logged in successfully!', 'success')
            return redirect(url_for('dashboard_user'))
    except Exception:
        flash('An error occurred during registration.', 'error')
        return redirect(url_for('user'))


@app.route('/register_employee', methods=['POST'])
def register_employee():
    username = request.form.get('username') or request.form.get('emp_user')
    gmail = request.form.get('gmail')
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

            conn.execute(
                'INSERT INTO users (username, password, role, gmail, work_details, account_status) VALUES (?, ?, ?, ?, ?, ?)',
                (username, 'pending_setup', 'employee', gmail, work_details, 'pending')
            )
            conn.commit()

            flash('Registration successful! Please wait for approval.', 'success')
            return redirect(url_for('index'))
    except Exception:
        flash('An error occurred during registration.', 'error')
        return redirect(url_for('employee'))


@app.route('/employee', methods=['GET', 'POST'])
def employee():
    return process_login(request, 'employee', 'employee_login.html', 'dashboard_employee')


@app.route('/logout')
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
            "SELECT id, username, password, account_status, is_online FROM users WHERE role = 'user'"
        ).fetchall()
        employees = conn.execute(
            "SELECT id, username, password, account_status, availability, is_online FROM users WHERE role = 'employee' AND account_status IN ('approved', 'blocked')"
        ).fetchall()
        try:
            pending_employees = conn.execute(
                "SELECT * FROM users WHERE role = 'employee' AND account_status = 'pending'"
            ).fetchall()
        except sqlite3.OperationalError:
            pending_employees = []

        try:
            requests_list = conn.execute(
                "SELECT r.id, u.username, r.item_name, r.status FROM requests r JOIN users u ON r.user_id = u.id"
            ).fetchall()
        except sqlite3.OperationalError:
            requests_list = []

    return render_template('dashboard_admin.html',
                           admin_info=admin_info,
                           users=users,
                           employees=employees,
                           pending_employees=pending_employees,
                           requests_list=requests_list)


@app.route('/view_service/<service_name>')
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


@app.route('/user_add_deposit', methods=['POST'])
@login_required('user')
def user_add_deposit():
    user_id = session.get('user_id')
    amount_str = request.form.get('amount')
    try:
        amount = float(amount_str)
        if amount < 2000:
            flash("Deposit amount must be at least ₹2000.", "error")
            return redirect(url_for('dashboard_user'))
    except (ValueError, TypeError):
        flash("Invalid deposit amount.", "error")
        return redirect(url_for('dashboard_user'))
        
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET deposit_balance = COALESCE(deposit_balance, 0) + ? WHERE id = ?",
            (amount, user_id)
        )
        conn.commit()
    flash(f"Successfully added ₹{amount} to your deposit balance.", "success")
    return redirect(url_for('dashboard_user'))

@app.route('/user_withdraw_deposit', methods=['POST'])
@login_required('user')
def user_withdraw_deposit():
    user_id = session.get('user_id')
    amount_str = request.form.get('amount')
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Withdrawal amount must be greater than zero.", "error")
            return redirect(url_for('dashboard_user'))
    except (ValueError, TypeError):
        flash("Invalid withdrawal amount.", "error")
        return redirect(url_for('dashboard_user'))
        
    with get_db_connection() as conn:
        user = conn.execute("SELECT deposit_balance FROM users WHERE id = ?", (user_id,)).fetchone()
        current_balance = user['deposit_balance'] or 0.0
        
        if amount > current_balance:
            flash(f"Insufficient deposit balance. You can withdraw up to ₹{current_balance}.", "error")
            return redirect(url_for('dashboard_user'))
            
        conn.execute(
            "UPDATE users SET deposit_balance = deposit_balance - ? WHERE id = ?",
            (amount, user_id)
        )
        conn.commit()
    flash(f"Successfully withdrew ₹{amount} from your deposit balance.", "success")
    return redirect(url_for('dashboard_user'))


@app.route('/dashboard_user')
@login_required('user')
def dashboard_user():
    user_id = session.get('user_id')
    with get_db_connection() as conn:
        user_info = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        try:
            pending_employees = conn.execute(
                "SELECT * FROM users WHERE role = 'employee' AND account_status = 'pending'"
            ).fetchall()
        except sqlite3.OperationalError:
            pending_employees = []

        try:
            user_messages = conn.execute(
                "SELECT * FROM user_messages WHERE user_id = ? ORDER BY id DESC", (user_id,)
            ).fetchall()
        except sqlite3.OperationalError:
            user_messages = []

    return render_template('dashboard_user.html',
                           user_info=user_info,
                           pending_employees=pending_employees,
                           user_messages=user_messages)


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
                    SELECT sr.id, sr.status, u.username as user_name, u.gmail as user_gmail 
                    FROM service_requests sr
                    JOIN users u ON sr.user_id = u.id
                    WHERE sr.employee_id = ? AND sr.status = 'Pending'
                    ORDER BY sr.id DESC
                    """, (user_id,)
                ).fetchall()
            except sqlite3.OperationalError:
                emp_messages = []
                service_requests = []

    return render_template('dashboard_employee.html',
                           employee=employee,
                           emp_messages=emp_messages,
                           service_requests=service_requests)


@app.route('/update_employee', methods=['POST'])
@login_required('employee')
def update_employee():
    user_id = session.get('user_id')
    new_username = request.form.get('username')
    new_password = request.form.get('password')
    new_phone = request.form.get('gmail')
    new_work_list = request.form.getlist('work_details')
    new_work = ", ".join(new_work_list) if new_work_list else ""

    if not new_username or not new_phone or not new_work:
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

        if new_password:
            conn.execute("""
                UPDATE users SET username = ?, password = ?, gmail = ?, work_details = ?
                WHERE id = ?
            """, (new_username, new_password, new_phone, new_work, user_id))
        else:
            conn.execute("""
                UPDATE users SET username = ?, gmail = ?, work_details = ?
                WHERE id = ?
            """, (new_username, new_phone, new_work, user_id))

        conn.commit()
        session['username'] = new_username
        flash('Your details have been updated successfully.', 'success')

    return redirect(url_for('dashboard_employee'))


@app.route('/update_employee_availability', methods=['POST'])
@login_required('employee')
def update_employee_availability():
    user_id = session.get('user_id')
    new_timing = request.form.get('availability')

    if new_timing:
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE users SET availability = ? WHERE id = ?
            """, (new_timing, user_id))
            conn.commit()
            flash('Availability updated successfully.', 'success')

    return redirect(url_for('dashboard_employee'))


@app.route('/update_admin', methods=['POST'])
@login_required('admin')
def update_admin():
    user_id = session.get('user_id')
    new_username = request.form.get('username')
    new_password = request.form.get('password')
    new_phone = request.form.get('gmail')
    new_work_list = request.form.getlist('work_details')
    new_work = ", ".join(new_work_list) if new_work_list else ""

    if not new_username:
        flash('Username is required.', 'error')
        return redirect(url_for('dashboard_admin'))

    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE ((username = ? AND role = 'admin') OR gmail = ?) AND id != ?", (new_username, new_phone, user_id)
        ).fetchone()
        if existing:
            if existing['username'] == new_username and existing['role'] == 'admin':
                flash(f'Username "{new_username}" is already taken by another admin.', 'error')
            else:
                flash(f'Gmail ID "{new_phone}" is already registered to another user.', 'error')
            return redirect(url_for('dashboard_admin'))

        if new_password:
            conn.execute("""
                UPDATE users SET username = ?, password = ?, gmail = ?, work_details = ?
                WHERE id = ?
            """, (new_username, new_password, new_phone, new_work, user_id))
        else:
            conn.execute("""
                UPDATE users SET username = ?, gmail = ?, work_details = ?
                WHERE id = ?
            """, (new_username, new_phone, new_work, user_id))

        conn.commit()
        session['username'] = new_username
        flash('Your details have been updated successfully.', 'success')

    return redirect(url_for('dashboard_admin'))


@app.route('/accept_employee/<int:emp_id>', methods=['POST'])
@login_required('user')
def accept_employee(emp_id):
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    with get_db_connection() as conn:
        emp = conn.execute("SELECT * FROM users WHERE id = ?", (emp_id,)).fetchone()
        if emp and emp['account_status'] == 'pending':
            conn.execute(
                "UPDATE users SET password = ?, account_status = 'approved' WHERE id = ?",
                (password, emp_id)
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
    return redirect(url_for('dashboard_user'))


@app.route('/admin_accept_employee/<int:emp_id>', methods=['POST'])
@login_required('admin')
def admin_accept_employee(emp_id):
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    with get_db_connection() as conn:
        emp = conn.execute("SELECT * FROM users WHERE id = ?", (emp_id,)).fetchone()
        if emp and emp['account_status'] == 'pending':
            conn.execute(
                "UPDATE users SET password = ?, account_status = 'approved' WHERE id = ?",
                (password, emp_id)
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
    return render_template('admin_employee_details.html', employee=employee)


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
            if (employee['deposit_balance'] or 0.0) < 2000.0:
                flash(f"Professional '{employee['username']}' is currently not accepting requests.", "error")
                return redirect(request.referrer or url_for('dashboard_user'))
                
            existing = conn.execute("SELECT * FROM service_requests WHERE user_id = ? AND employee_id = ? AND status = 'Pending'", (user_id, emp_id)).fetchone()
            if existing:
                flash(f"You already have a pending request for {employee['username']}.", "error")
            else:
                conn.execute(
                    "INSERT INTO service_requests (user_id, employee_id, status) VALUES (?, ?, 'Pending')",
                    (user_id, emp_id)
                )
                
                # Send a notification message to the employee
                deposit_balance = employee['deposit_balance'] or 0.0
                msg = f"You received a new service request from {user['username']}. Your current Advance Deposit balance is ₹{deposit_balance}."
                conn.execute(
                    "INSERT INTO employee_messages (gmail, message) VALUES (?, ?)",
                    (employee['gmail'], msg)
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
                flash("You must maintain a minimum deposit advance of ₹2000 to accept new requests. Please add funds.", "error")
                return redirect(url_for('dashboard_employee'))

        req = conn.execute(
            "SELECT * FROM service_requests WHERE id = ? AND employee_id = ?", 
            (req_id, employee_id)
        ).fetchone()
        
        if req:
            conn.execute("UPDATE service_requests SET status = ? WHERE id = ?", (new_status, req_id))
            
            if new_status == 'Accepted':
                conn.execute("UPDATE users SET availability = 'Booked' WHERE id = ?", (employee_id,))
            
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

@app.route('/add_deposit', methods=['POST'])
@login_required('employee')
def add_deposit():
    employee_id = session.get('user_id')
    amount_str = request.form.get('amount')
    try:
        amount = float(amount_str)
        if amount < 2000:
            flash("Deposit amount must be at least ₹2000.", "error")
            return redirect(url_for('dashboard_employee'))
    except (ValueError, TypeError):
        flash("Invalid deposit amount.", "error")
        return redirect(url_for('dashboard_employee'))
        
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET deposit_balance = COALESCE(deposit_balance, 0) + ? WHERE id = ?",
            (amount, employee_id)
        )
        conn.commit()
    flash(f"Successfully added ₹{amount} to your deposit balance.", "success")
    return redirect(url_for('dashboard_employee'))

@app.route('/withdraw_deposit', methods=['POST'])
@login_required('employee')
def withdraw_deposit():
    employee_id = session.get('user_id')
    amount_str = request.form.get('amount')
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Withdrawal amount must be greater than zero.", "error")
            return redirect(url_for('dashboard_employee'))
    except (ValueError, TypeError):
        flash("Invalid withdrawal amount.", "error")
        return redirect(url_for('dashboard_employee'))
        
    with get_db_connection() as conn:
        employee = conn.execute("SELECT deposit_balance FROM users WHERE id = ?", (employee_id,)).fetchone()
        current_balance = employee['deposit_balance'] or 0.0
        
        if amount > current_balance:
            flash(f"Insufficient deposit balance. You can withdraw up to ₹{current_balance}.", "error")
            return redirect(url_for('dashboard_employee'))
            
        conn.execute(
            "UPDATE users SET deposit_balance = deposit_balance - ? WHERE id = ?",
            (amount, employee_id)
        )
        conn.commit()
    flash(f"Successfully withdrew ₹{amount} from your deposit balance.", "success")
    return redirect(url_for('dashboard_employee'))

if __name__ == '__main__':
    app.run(debug=True)
