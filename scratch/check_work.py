import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')

def get_work_details():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT work_details FROM users WHERE role = 'employee'")
    rows = cursor.fetchall()
    for row in rows:
        print(row['work_details'])
    conn.close()

if __name__ == "__main__":
    get_work_details()
