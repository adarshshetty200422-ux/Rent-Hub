import sqlite3

def drop_unique():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    cursor = conn.cursor()
    
    # Create new table without UNIQUE constraint on username
    cursor.execute("""
    CREATE TABLE users_new(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        gmail TEXT,
        work_details TEXT,
        account_status TEXT DEFAULT 'approved',
        availability TEXT DEFAULT 'Not specified',
        is_online INTEGER DEFAULT 0
    )
    """)
    
    # Copy data
    cursor.execute("INSERT INTO users_new SELECT * FROM users")
    
    # Drop old table
    cursor.execute("DROP TABLE users")
    
    # Rename new table
    cursor.execute("ALTER TABLE users_new RENAME TO users")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    drop_unique()
    print("Dropped unique constraint on username.")
