import sqlite3

def migrate_db():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    cursor = conn.cursor()
    # Check if column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'is_online' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_online INTEGER DEFAULT 0")
        print("Added is_online column to users table.")
    else:
        print("is_online column already exists.")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate_db()
