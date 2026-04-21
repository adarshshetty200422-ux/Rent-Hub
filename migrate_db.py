"""
Safe database migration script.
Adds missing columns to the existing database WITHOUT deleting any data.
Run once: python migrate_db.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    return column in cols

def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=== Rent Hub DB Migration ===\n")

    # --- users table: add missing columns ---
    users_columns_to_add = [
        ("deposit_balance", "REAL DEFAULT 0.0"),
        ("balance",         "INTEGER DEFAULT 0"),
        ("bank_account_name",   "TEXT"),
        ("bank_account_number", "TEXT"),
        ("bank_ifsc",       "TEXT"),
        ("bank_name",       "TEXT"),
        ("bank_branch",     "TEXT"),
        ("rating",          "REAL DEFAULT 0.0"),
        ("rating_count",    "INTEGER DEFAULT 0"),
        ("profile_pic",     "TEXT"),
    ]
    for col, col_def in users_columns_to_add:
        if not column_exists(cursor, 'users', col):
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
            print(f"  [users] Added column: {col}")
        else:
            print(f"  [users] Column already exists: {col}")

    # --- service_requests: add rating and review columns ---
    sr_columns_to_add = [
        ("rating", "INTEGER"),
        ("review", "TEXT"),
    ]
    for col, col_def in sr_columns_to_add:
        if not column_exists(cursor, 'service_requests', col):
            cursor.execute(f"ALTER TABLE service_requests ADD COLUMN {col} {col_def}")
            print(f"  [service_requests] Added column: {col}")
        else:
            print(f"  [service_requests] Column already exists: {col}")

    # --- withdrawal_requests: create if not exists ---
    if not table_exists(cursor, 'withdrawal_requests'):
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
        print("  [withdrawal_requests] Table created.")
    else:
        # Add bank_details if missing
        if not column_exists(cursor, 'withdrawal_requests', 'bank_details'):
            cursor.execute("ALTER TABLE withdrawal_requests ADD COLUMN bank_details TEXT")
            print("  [withdrawal_requests] Added column: bank_details")
        if not column_exists(cursor, 'withdrawal_requests', 'requested_at'):
            cursor.execute("ALTER TABLE withdrawal_requests ADD COLUMN requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("  [withdrawal_requests] Added column: requested_at")
        print("  [withdrawal_requests] Table OK.")

    # --- withdraw_requests (UPI): create if not exists ---
    if not table_exists(cursor, 'withdraw_requests'):
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
        print("  [withdraw_requests] Table created.")
    else:
        print("  [withdraw_requests] Table OK.")

    # --- user_messages: create if not exists ---
    if not table_exists(cursor, 'user_messages'):
        cursor.execute("""
        CREATE TABLE user_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        print("  [user_messages] Table created.")
    else:
        print("  [user_messages] Table OK.")

    # --- employee_messages: create if not exists ---
    if not table_exists(cursor, 'employee_messages'):
        cursor.execute("""
        CREATE TABLE employee_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail TEXT NOT NULL,
            message TEXT NOT NULL
        )
        """)
        print("  [employee_messages] Table created.")
    else:
        print("  [employee_messages] Table OK.")

    # --- requests: create if not exists ---
    if not table_exists(cursor, 'requests'):
        cursor.execute("""
        CREATE TABLE requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        print("  [requests] Table created.")
    else:
        print("  [requests] Table OK.")

    # Fix any NULL deposit_balance / balance / rating values in users
    cursor.execute("UPDATE users SET deposit_balance = 0.0 WHERE deposit_balance IS NULL")
    cursor.execute("UPDATE users SET balance = 0 WHERE balance IS NULL")
    cursor.execute("UPDATE users SET rating = 0.0 WHERE rating IS NULL")
    cursor.execute("UPDATE users SET rating_count = 0 WHERE rating_count IS NULL")
    print("\n  Cleaned NULL numeric fields in users.")

    conn.commit()
    conn.close()
    print("\n=== Migration complete! ===")

if __name__ == '__main__':
    migrate()
