import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_EXPIRE_SECONDS
import json

class RedisClient:
    _instance = None

    def __new__(cls):
        """
        Implement Singleton design pattern to ensure a single Redis client instance throughout the application.
        Prevents excessive database connections and ensures consistent connection configuration.
        """
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True  # Automatically decode Redis responses to UTF-8 strings (avoids byte string handling)
            )
        return cls._instance

    @staticmethod
    def set_cache(key: str, data, expire_seconds: int = REDIS_EXPIRE_SECONDS):
        """
        Store data in Redis with automatic JSON serialization for complex data structures.
        Applies a default TTL (time-to-live) to prevent stale cache accumulation, with override support.
        
        Args:
            key (str): Unique string key for cache lookup
            data: Data to be cached (can be str, dict, list, or other serializable types)
            expire_seconds (int, optional): TTL in seconds for the cache entry. Defaults to REDIS_EXPIRE_SECONDS from config.
        """
        client = RedisClient()
        # Serialize dicts/lists to JSON strings for Redis storage (Redis natively supports string values)
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        client.set(key, data, ex=expire_seconds)

    @staticmethod
    def get_cache(key: str):
        """
        Retrieve data from Redis with automatic JSON deserialization for complex data structures.
        Gracefully handles non-JSON data (e.g., plain strings) to ensure compatibility with all cached values.
        
        Args:
            key (str): Unique string key for cache lookup
        
        Returns:
            Deserialized dict/list (if data was JSON-serialized) or raw string (if plain text) or None (if key does not exist)
        """
        client = RedisClient()
        data = client.get(key)
        if not data:
            return None
        try:
            # Attempt to deserialize JSON data back to native Python structures
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            # Return raw string if data is not valid JSON (plain text values)
            return data

    @staticmethod
    def delete_cache(key: str):
        """
        Remove a specific cache entry from Redis by its key.
        
        Args:
            key (str): Unique string key of the cache entry to be deleted
        """
        client = RedisClient()
        client.delete(key)