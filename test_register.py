"""
Test suite for user registration functionality.
"""
import unittest
from app import app, get_db_connection  # type: ignore


class TestRegister(unittest.TestCase):
    """Test cases for the user registration process."""
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def test_register_user(self):
        """Test successful registration of a new user."""
        print("Testing Registration...")
        response = self.client.post(
            "/register_user",
            data={
                "username": "newuser123",
                "password": "Password1!",
                "gmail": "testuser123@example.com",
            },
        )
        print("POST /register_user Response:", response.status_code)
        # Should redirect to dashboard
        self.assertIn(response.status_code, [302, 200])

        print("Checking Database...")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username='newuser123'")
            user = cursor.fetchone()

            if user:
                print("User successfully inserted:", dict(user))
                cursor.execute("DELETE FROM users WHERE username='newuser123'")
                conn.commit()
                print("Test user cleaned up.")
            else:
                print("User NOT inserted.")

        self.assertIsNotNone(user)


if __name__ == "__main__":
    unittest.main()
