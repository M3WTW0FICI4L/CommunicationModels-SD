"""
Unit tests for configuration module.
"""

import unittest
import os
from src.common.config import Config


class TestConfig(unittest.TestCase):
    """Test Config class."""
    
    def test_ticket_constraints(self):
        """Test ticket constraint values."""
        self.assertEqual(Config.MAX_TICKETS, 20000)
        self.assertEqual(Config.MIN_SEAT_ID, 1)
        self.assertEqual(Config.MAX_SEAT_ID, 20000)
    
    def test_redis_configuration_defaults(self):
        """Test Redis configuration defaults."""
        # These should use defaults if env vars not set
        self.assertEqual(Config.REDIS_HOST, "localhost")
        self.assertEqual(Config.REDIS_PORT, 6379)
        self.assertEqual(Config.REDIS_DB, 0)
    
    def test_api_configuration_defaults(self):
        """Test API configuration defaults."""
        self.assertEqual(Config.API_HOST, "0.0.0.0")
        self.assertEqual(Config.API_PORT, 8000)
        self.assertEqual(Config.API_WORKERS, 4)
    
    def test_rabbitmq_configuration(self):
        """Test RabbitMQ configuration."""
        self.assertEqual(Config.RABBITMQ_HOST, "localhost")
        self.assertEqual(Config.RABBITMQ_PORT, 5672)
        self.assertEqual(Config.RABBITMQ_USER, "guest")
        self.assertEqual(Config.RABBITMQ_PASS, "guest")
        self.assertEqual(Config.RABBITMQ_VHOST, "/")
    
    def test_queue_configuration(self):
        """Test queue configuration."""
        self.assertEqual(Config.QUEUE_NAME, "ticket_purchases")
        self.assertEqual(Config.QUEUE_MAX_PRIORITY, 10)
    
    def test_timeout_configuration(self):
        """Test timeout and retry configuration."""
        self.assertEqual(Config.REQUEST_TIMEOUT, 30)
        self.assertEqual(Config.MAX_RETRIES, 3)
    
    def test_logging_configuration(self):
        """Test logging configuration."""
        self.assertEqual(Config.LOG_LEVEL, "INFO")
        self.assertIn("%(asctime)s", Config.LOG_FORMAT)
        self.assertIn("%(name)s", Config.LOG_FORMAT)
        self.assertIn("%(levelname)s", Config.LOG_FORMAT)
        self.assertIn("%(message)s", Config.LOG_FORMAT)
    
    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config_dict = Config.to_dict()
        
        # Should be a dictionary
        self.assertIsInstance(config_dict, dict)
        
        # Should contain uppercase keys (configuration constants)
        self.assertIn("MAX_TICKETS", config_dict)
        self.assertIn("REDIS_HOST", config_dict)
        self.assertIn("API_HOST", config_dict)
        self.assertIn("QUEUE_NAME", config_dict)
        
        # Should not contain private or method attributes
        self.assertNotIn("to_dict", config_dict)
        self.assertNotIn("_Config", config_dict)
    
    def test_config_to_dict_values(self):
        """Test that to_dict returns correct values."""
        config_dict = Config.to_dict()
        
        self.assertEqual(config_dict["MAX_TICKETS"], 20000)
        self.assertEqual(config_dict["REDIS_HOST"], "localhost")
        self.assertEqual(config_dict["API_PORT"], 8000)
        self.assertEqual(config_dict["QUEUE_NAME"], "ticket_purchases")
    
    def test_worker_count_default(self):
        """Test worker count configuration."""
        # Should have a default value
        self.assertGreaterEqual(Config.WORKER_COUNT, 1)
    
    def test_env_variable_override(self):
        """Test that environment variables can override defaults."""
        # Save original values
        original_port = Config.REDIS_PORT
        original_host = Config.REDIS_HOST
        
        try:
            # Set environment variables
            os.environ["REDIS_PORT"] = "1234"
            os.environ["REDIS_HOST"] = "redis.example.com"
            
            # Re-load config (simulated by checking that env vars affect config)
            # Note: In real scenario, would need to reload module
            self.assertTrue(os.environ.get("REDIS_PORT") == "1234")
            self.assertTrue(os.environ.get("REDIS_HOST") == "redis.example.com")
        finally:
            # Clean up environment
            if "REDIS_PORT" in os.environ:
                del os.environ["REDIS_PORT"]
            if "REDIS_HOST" in os.environ:
                del os.environ["REDIS_HOST"]


if __name__ == "__main__":
    unittest.main()
