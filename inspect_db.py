import sqlite3
import pprint

conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for name, sql in tables:
    print(f"Table: {name}")
    print(f"SQL: {sql}")
    print("-" * 50)
    
cursor.execute("SELECT * FROM users")
print("Users:", cursor.fetchall())
