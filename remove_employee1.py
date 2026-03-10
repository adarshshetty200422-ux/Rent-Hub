import sqlite3

def clean_db():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    cursor = conn.cursor()
    
    # Remove 'employee1'
    cursor.execute("DELETE FROM users WHERE username = 'employee1'")
    if cursor.rowcount > 0:
        print("Removed employee1.")
    else:
        print("employee1 not found in database.")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    clean_db()
