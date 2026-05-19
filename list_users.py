"""
Utility script to list all users in the database.
"""
import sqlite3

def list_users():
    """Fetches and prints all users and their roles from the database."""
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
