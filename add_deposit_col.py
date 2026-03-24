import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE users ADD COLUMN deposit_balance REAL DEFAULT 0.0")
    print("Added deposit_balance column")
except Exception as e:
    print("Error:", e)

conn.commit()
conn.close()
