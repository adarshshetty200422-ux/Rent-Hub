import sqlite3

def list_users():
    conn = sqlite3.connect('c:/Users/adars/OneDrive/Documents/Rent hub/rent_hub/database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users")
    users = cursor.fetchall()
    print("CURRENT USERS:")
    for user in users:
        print(f"Username: '{user[0]}', Role: '{user[1]}'")
    conn.close()

if __name__ == '__main__':
    list_users()
