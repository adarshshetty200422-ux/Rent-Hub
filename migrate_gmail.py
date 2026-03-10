import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE users RENAME COLUMN phone_number TO gmail")
        print("Renamed phone_number to gmail in users table.")
    except Exception as e:
        print("users error:", e)

    try:
        conn.execute("ALTER TABLE employee_messages RENAME COLUMN phone_number TO gmail")
        print("Renamed phone_number to gmail in employee_messages table.")
    except Exception as e:
        print("employee_messages error:", e)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
