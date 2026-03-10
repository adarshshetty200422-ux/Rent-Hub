import urllib.request
import urllib.parse
import sqlite3

print("Testing Registration...")

# Test POST to /register_user
try:
    data = urllib.parse.urlencode({'usr_user': 'newuser123', 'usr_pass': 'Password1!'}).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:5000/register_user', data=data, method='POST')
    # Will likely return a redirect, which we can catch or ignore
    with urllib.request.urlopen(req) as response:
        print("POST /register_user Response:", response.status)
except Exception as e:
    print("POST /register_user ERROR:", e)

print("Checking Database...")
try:
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username='newuser123'")
    user = cursor.fetchone()
    if user:
        print("User successfully inserted:", user)
    else:
        print("User NOT inserted.")
        
    # clean up test user
    if user:
        cursor.execute("DELETE FROM users WHERE username='newuser123'")
        conn.commit()
        print("Test user cleaned up.")
    conn.close()
except Exception as e:
    print("Database check ERROR:", e)
