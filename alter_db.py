import sqlite3
import os

db_path = os.path.join(r"c:\Users\adars\OneDrive\Documents\Rent hub\rent_hub", 'database.db')
conn = sqlite3.connect(db_path)
try:
    conn.execute("ALTER TABLE withdrawal_requests ADD COLUMN bank_details TEXT")
    print("Added bank_details column")
except Exception as e:
    print(e)
conn.commit()
conn.close()
