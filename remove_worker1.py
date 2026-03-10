import sqlite3

def remove_worker1():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = 'Worker1'")
    if cursor.rowcount > 0:
        print("Removed Worker1.")
    else:
        print("Worker1 not found in database.")
    
    # Check for anything containing 'employee' or '1' just in case
    cursor.execute("DELETE FROM users WHERE username LIKE '%employee1%'")
    if cursor.rowcount > 0:
        print(f"Removed additional {cursor.rowcount} users matching employee1")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    remove_worker1()
