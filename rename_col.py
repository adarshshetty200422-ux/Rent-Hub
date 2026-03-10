import sqlite3

def rename_col():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    try:
        conn.execute("ALTER TABLE users RENAME COLUMN available_timing TO availability")
        print("Column renamed to availability.")
    except sqlite3.OperationalError as e:
        print("Could not rename:", e)
        # Maybe it doesn't exist or is already availability. Let's try adding it if missing.
        try:
            conn.execute("ALTER TABLE users ADD COLUMN availability TEXT DEFAULT 'Available'")
            print("Column availability added.")
        except Exception as e2:
            print("Could not add:", e2)
    conn.commit()
    conn.close()

if __name__ == '__main__':
    rename_col()
