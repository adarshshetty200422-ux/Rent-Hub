import unittest
from app import app  # type: ignore


class TestApp(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def test_admin_get(self):
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 200)
        print("GET /admin OK")

    def test_admin_post(self):
        response = self.client.post("/admin", data={"username": "a", "password": "b"})
        # Should render login page with missing/invalid credentials error
        self.assertEqual(response.status_code, 200)
        print("POST /admin OK")


if __name__ == "__main__":
    unittest.main()
