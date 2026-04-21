import sqlite3
import os
from werkzeug.security import generate_password_hash

# Use relative path for better portability
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def init():
    # Connect to database (creates it if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing tables to ensure schema updates
    cursor.execute("DROP TABLE IF EXISTS service_requests")
    cursor.execute("DROP TABLE IF EXISTS withdrawal_requests")
    cursor.execute("DROP TABLE IF EXISTS withdraw_requests")
    cursor.execute("DROP TABLE IF EXISTS employee_messages")
    cursor.execute("DROP TABLE IF EXISTS user_messages")
    cursor.execute("DROP TABLE IF EXISTS requests")
    cursor.execute("DROP TABLE IF EXISTS users")

    # 1. Users Table — complete schema including all required columns
    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        gmail TEXT,
        work_details TEXT,
        account_status TEXT DEFAULT 'approved',
        availability TEXT DEFAULT 'NOT SPECIFIED',
        is_online INTEGER DEFAULT 0,
        deposit_balance REAL DEFAULT 0.0,
        balance INTEGER DEFAULT 0,
        bank_account_name TEXT,
        bank_account_number TEXT,
        bank_ifsc TEXT,
        bank_name TEXT,
        bank_branch TEXT,
        rating REAL DEFAULT 0.0,
        rating_count INTEGER DEFAULT 0,
        profile_pic TEXT
    )
    """)

    # 2. Employee Messages Table
    cursor.execute("""
    CREATE TABLE employee_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gmail TEXT NOT NULL,
        message TEXT NOT NULL
    )
    """)

    # 3. User Messages Table
    cursor.execute("""
    CREATE TABLE user_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 4. Requests Table
    cursor.execute("""
    CREATE TABLE requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 5. Service Requests Table
    cursor.execute("""
    CREATE TABLE service_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        employee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'Pending',
        rating INTEGER,
        review TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (employee_id) REFERENCES users(id)
    )
    """)

    # 6. Withdrawal Requests Table (bank transfer)
    cursor.execute("""
    CREATE TABLE withdrawal_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'Pending',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        bank_details TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 7. UPI Withdraw Requests Table
    cursor.execute("""
    CREATE TABLE withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        upi_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Seed default admin only (password will be set manually or via app)
    hashed = generate_password_hash('admin123')
    cursor.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        ('admin_user', hashed, 'admin')
    )

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH} and seeded with default admin (admin_user / admin123).")

if __name__ == '__main__':
    init()
