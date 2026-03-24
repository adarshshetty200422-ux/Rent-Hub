import sqlite3
import os

# Use relative path for better portability
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def init():
    # Connect to database (creates it if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing tables to ensure schema updates
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS employee_messages")
    cursor.execute("DROP TABLE IF EXISTS user_messages")
    cursor.execute("DROP TABLE IF EXISTS requests")
    cursor.execute("DROP TABLE IF EXISTS service_requests")

    # Create tables
    # 1. Users Table
    cursor.execute("""
    CREATE TABLE users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        gmail TEXT,
        work_details TEXT,
        account_status TEXT DEFAULT 'approved',
        availability TEXT DEFAULT 'Not specified',
        is_online INTEGER DEFAULT 0,
        deposit_balance REAL DEFAULT 0.0
    )
    """)

    # 2. Employee Messages Table
    cursor.execute("""
    CREATE TABLE employee_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gmail TEXT NOT NULL,
        message TEXT NOT NULL
    )
    """)

    # 3. User Messages Table
    cursor.execute("""
    CREATE TABLE user_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 4. Requests Table
    cursor.execute("""
    CREATE TABLE requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 5. Service Requests Table
    cursor.execute("""
    CREATE TABLE service_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        employee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (employee_id) REFERENCES users(id)
    )
    """)

    # Seed default admin only
    users_to_seed = [
        ('admin_user', 'admin123', 'admin')
    ]
    cursor.executemany("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", users_to_seed)

    # Do not seed requests
    # requests_to_seed = [
    #     (3, 'Power Drill', 'Pending'),
    #     (3, 'Lawn Mower', 'Approved')
    # ]
    # cursor.executemany("INSERT INTO requests (user_id, item_name, status) VALUES (?, ?, ?)", requests_to_seed)

    conn.commit()
    conn.close()
    print(f"Database initialized completely at {DB_PATH} and seeded with default data.")

if __name__ == '__main__':
    init()
