import sqlite3

DB_PATH = 'c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db'

def alter():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN available_timing TEXT DEFAULT 'Not specified'")
        print("Column added successfully.")
    except sqlite3.OperationalError as e:
        print("Error/Already exists:", e)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    alter()
