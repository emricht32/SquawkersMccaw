import unittest

from birdpi_main.web_interface import create_web_interface
from birdpi_main.bird_registry import registry


class TestHealthEndpoint(unittest.TestCase):
    def setUp(self):
        # Clear existing birds and register a couple for the test.
        registry.birds.clear()
        registry.register("id1", "10.0.0.1", "Fritz")
        registry.register("id2", "10.0.0.2", "Pierre")

        # Minimal song list and callbacks for web interface creation.
        self.songs = []
        self.app = create_web_interface(self.songs, lambda i: None, lambda: None, lambda: [])
        self.client = self.app.test_client()

    def test_health_keys_and_counts(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200, "Health endpoint should return 200")
        data = resp.get_json()
        for key in ["status", "bird_count", "registered", "time"]:
            self.assertIn(key, data, f"Missing key '{key}' in /api/health response")
        self.assertEqual(data["bird_count"], 2, "bird_count should match registered birds")
        self.assertEqual(set(data["registered"]), {"Fritz", "Pierre"}, "Registered list mismatch")


if __name__ == "__main__":
    unittest.main()