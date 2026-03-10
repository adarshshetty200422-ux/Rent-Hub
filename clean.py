import sqlite3

def clean_db():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    cursor = conn.cursor()
    
    # 1. Remove references to 'test_user' entirely so their requests vanish too
    cursor.execute("SELECT id FROM users WHERE username = 'test_user'")
    test_user_row = cursor.fetchone()
    if test_user_row:
        test_user_id = test_user_row[0]
        # Delete their requests
        cursor.execute("DELETE FROM requests WHERE user_id = ?", (test_user_id,))
        # Delete the user itself (optional based on phrasing, assuming full deletion is clean)
        cursor.execute("DELETE FROM users WHERE id = ?", (test_user_id,))
        print("Removed test_user and their requests.")
    
    # 2. Remove 'worker 1'
    cursor.execute("DELETE FROM users WHERE username = 'worker 1'")
    if cursor.rowcount > 0:
        print("Removed worker 1.")

    # 3. Remove 'test_employee'
    cursor.execute("DELETE FROM users WHERE username = 'test_employee'")
    if cursor.rowcount > 0:
        print("Removed test_employee.")

    # Or simply: Delete all specified accounts safely just by username:
    cursor.execute("DELETE FROM users WHERE username IN ('test_employee', 'worker 1', 'test_user')")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    clean_db()
