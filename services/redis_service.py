import redis
import json
import logging
from config.config import Config

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self):
        try:
            self.redis = redis.from_url(Config.REDIS_URL)
            self.session_ttl = 3600  # 1 hour session timeout
            self.is_connected = True
        except redis.ConnectionError:
            logger.warning("Could not connect to Redis. Running without cache.")
            self.is_connected = False

    def _get_user_key(self, user_id: str, key_type: str) -> str:
        """Generate a unique key for user data"""
        return f"user:{user_id}:{key_type}"

    def _validate_user_id(self, user_id: str) -> bool:
        """Validate user ID to prevent key injection"""
        return isinstance(user_id, str) and ":" not in user_id

    def set_medical_record(self, user_id: str, data, is_json=False):
        """Store medical record data for a user"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return False

        if not self._validate_user_id(user_id):
            logger.error(f"Invalid user_id format: {user_id}")
            return False

        try:
            key = self._get_user_key(user_id, "medical_record")
            if is_json:
                self.redis.setex(key, self.session_ttl, json.dumps(data))
            else:
                self.redis.setex(key, self.session_ttl, data)
            logger.info(f"Stored medical record for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing medical record for user {user_id}: {str(e)}")
            return False

    def get_medical_record(self, user_id: str, is_json=False):
        """Get stored medical record for a user"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        if not self._validate_user_id(user_id):
            logger.error(f"Invalid user_id format: {user_id}")
            return None

        try:
            key = self._get_user_key(user_id, "medical_record")
            data = self.redis.get(key)
            
            if not data:
                return None
                
            if is_json:
                return json.loads(data)
            return data.decode('utf-8')
        except Exception as e:
            logger.error(f"Error retrieving medical record for user {user_id}: {str(e)}")
            return None

    def clear_medical_record(self, user_id: str):
        """Clear stored medical record for a user"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return False

        if not self._validate_user_id(user_id):
            logger.error(f"Invalid user_id format: {user_id}")
            return False

        try:
            key = self._get_user_key(user_id, "medical_record")
            self.redis.delete(key)
            logger.info(f"Cleared medical record for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing medical record for user {user_id}: {str(e)}")
            return False

    def clear_all_user_data(self, user_id: str):
        """Clear all data for a user"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return False

        if not self._validate_user_id(user_id):
            logger.error(f"Invalid user_id format: {user_id}")
            return False

        try:
            pattern = f"user:{user_id}:*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
            logger.info(f"Cleared all data for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing all data for user {user_id}: {str(e)}")
            return False

    def set_structured_summary(self, user_id: str, summary_data: dict) -> bool:
        """Store structured summary data for a user"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return False

        if not self._validate_user_id(user_id):
            logger.error(f"Invalid user_id format: {user_id}")
            return False

        try:
            key = self._get_user_key(user_id, "structured_summary")
            self.redis.setex(key, self.session_ttl, json.dumps(summary_data))
            logger.info(f"Stored structured summary for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing structured summary for user {user_id}: {str(e)}")
            return False

    def get_structured_summary(self, user_id: str) -> dict:
        """Get stored structured summary for a user"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        if not self._validate_user_id(user_id):
            logger.error(f"Invalid user_id format: {user_id}")
            return None

        try:
            key = self._get_user_key(user_id, "structured_summary")
            data = self.redis.get(key)
            
            if not data:
                return None
                
            return json.loads(data)
        except Exception as e:
            logger.error(f"Error retrieving structured summary for user {user_id}: {str(e)}")
            return None

    def get_visualizations(self, user_id: str) -> list:
        """Get visualizations from stored structured summary"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        summary = self.get_structured_summary(user_id)
        if not summary:
            return None
        return summary.get('visualizations', [])

    def get_medical_entities(self, user_id: str) -> dict:
        """Get medical entities from stored structured summary"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        summary = self.get_structured_summary(user_id)
        if not summary:
            return None
        return summary.get('medical_entities', {})

    def get_lab_results(self, user_id: str) -> list:
        """Get all lab results from stored structured summary"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        summary = self.get_structured_summary(user_id)
        if not summary:
            return None
        return summary.get('lab_results', {}).get('tests', [])

    def get_test_results_by_name(self, user_id: str, test_name: str) -> list:
        """Get all results for a specific test from stored structured summary"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        lab_results = self.get_lab_results(user_id)
        if not lab_results:
            return []
        return [test for test in lab_results if test.get('name', '').lower() == test_name.lower()]

    def get_visualization_by_title(self, user_id: str, title: str) -> dict:
        """Get a specific visualization from stored structured summary"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        visualizations = self.get_visualizations(user_id)
        if not visualizations:
            return None
        for viz in visualizations:
            if viz.get('title', '').lower() == title.lower():
                return viz
        return None

    def get_all_test_names(self, user_id: str) -> list:
        """Get list of all unique test names from stored structured summary"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        lab_results = self.get_lab_results(user_id)
        if not lab_results:
            return []
        return list(set(test.get('name') for test in lab_results if test.get('name')))

    def set_cached_text(self, file_name: str, text: str) -> bool:
        """Cache extracted text for development/testing"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return False

        try:
            key = f"cached_text:{file_name}"
            self.redis.setex(key, self.session_ttl, text)
            logger.info(f"Cached text for file: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error caching text for file {file_name}: {str(e)}")
            return False

    def get_cached_text(self, file_name: str) -> str:
        """Get cached text for development/testing"""
        if not self.is_connected:
            logger.warning("Redis not connected. Skipping cache operation.")
            return None

        try:
            key = f"cached_text:{file_name}"
            data = self.redis.get(key)
            if not data:
                return None
            return data.decode('utf-8')
        except Exception as e:
            logger.error(f"Error retrieving cached text for file {file_name}: {str(e)}")
            return None