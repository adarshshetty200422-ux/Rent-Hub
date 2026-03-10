import sqlite3

def init_user_msgs():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()
    print("user_messages table created successfully.")

if __name__ == '__main__':
    init_user_msgs()
