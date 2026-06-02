import unittest
import sqlite3
import os
import sys

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, get_db_connection

class TestCompletedFlow(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        
        # We will set up a test user, a test employee, and a service request in the database
        with get_db_connection() as conn:
            # Let's clean up any previous test records
            conn.execute("DELETE FROM users WHERE username IN ('test_user_flow', 'test_emp_flow')")
            conn.execute("DELETE FROM service_requests WHERE user_id IN (SELECT id FROM users WHERE username = 'test_user_flow')")
            conn.execute("DELETE FROM user_messages WHERE user_id IN (SELECT id FROM users WHERE username = 'test_user_flow')")
            
            # Create user
            cursor = conn.execute(
                "INSERT INTO users (username, password, role, gmail, account_status) VALUES (?, ?, ?, ?, ?)",
                ("test_user_flow", "pbkdf2:sha256:...", "user", "user@test.com", "approved")
            )
            self.user_id = cursor.lastrowid
            
            # Create employee
            cursor = conn.execute(
                "INSERT INTO users (username, password, role, gmail, work_details, rating, account_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("test_emp_flow", "pbkdf2:sha256:...", "employee", "emp@test.com", "Plumbing", 4.7, "approved")
            )
            self.emp_id = cursor.lastrowid
            
            # Create service request
            cursor = conn.execute(
                "INSERT INTO service_requests (user_id, employee_id, status) VALUES (?, ?, 'Accepted')",
                (self.user_id, self.emp_id)
            )
            self.req_id = cursor.lastrowid
            conn.commit()

    def tearDown(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM users WHERE username IN ('test_user_flow', 'test_emp_flow')")
            conn.execute("DELETE FROM service_requests WHERE id = ?", (self.req_id,))
            conn.execute("DELETE FROM user_messages WHERE user_id = ?", (self.user_id,))
            conn.commit()

    def test_complete_service_flow(self):
        # We will simulate employee logged in
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.emp_id
            sess["username"] = "test_emp_flow"
            sess["role"] = "employee"
            
        # Call complete_service
        response = self.client.post(f"/complete_service/{self.req_id}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify status in database
        with get_db_connection() as conn:
            req = conn.execute("SELECT * FROM service_requests WHERE id = ?", (self.req_id,)).fetchone()
            self.assertEqual(req["status"], "Completed")
            
            # Verify user notification
            msg = conn.execute("SELECT * FROM user_messages WHERE user_id = ?", (self.user_id,)).fetchone()
            self.assertIsNotNone(msg)
            print("Generated Message for User:", msg["message"])
            self.assertIn("Plumbing", msg["message"])
            self.assertIn("test_emp_flow", msg["message"])
            self.assertIn("4.7", msg["message"])

    def test_submit_rating_flow(self):
        # Set service status to Completed so it can be rated
        with get_db_connection() as conn:
            conn.execute("UPDATE service_requests SET status = 'Completed' WHERE id = ?", (self.req_id,))
            conn.commit()

        # Simulate user logged in
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["username"] = "test_user_flow"
            sess["role"] = "user"

        # Submit rating and review
        response = self.client.post(f"/submit_rating/{self.req_id}", data={
            "rating": "5",
            "review": "Excellent plumbing work!"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Verify employee message in database
        with get_db_connection() as conn:
            emp_msg = conn.execute("SELECT * FROM employee_messages WHERE gmail = 'emp@test.com'").fetchone()
            self.assertIsNotNone(emp_msg)
            print("Generated Message for Employee:", emp_msg["message"])
            self.assertIn("test_user_flow", emp_msg["message"])
            self.assertIn("5 stars", emp_msg["message"])
            self.assertIn("Excellent plumbing work!", emp_msg["message"])

if __name__ == "__main__":
    unittest.main()
