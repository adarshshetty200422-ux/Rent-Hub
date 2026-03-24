import sqlite3
connection = sqlite3.connect('database.db')
cursor = connection.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for row in cursor.fetchall():
    if row[0]:
        print(row[0])
