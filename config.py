import os
from pathlib import Path
from dotenv import load_dotenv



REDDIT_APP_ID = os.getenv("REDDIT_APP_ID", "")
REDDIT_APP_SECRET = os.getenv("REDDIT_APP_SECRET", "")
REDIT_USER_AGENT = os.getenv("REDIT_USER_AGENT", "testingLangchain")


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")




REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_EXPIRE_SECONDS = int(os.getenv("REDIS_EXPIRE_SECONDS", 3600))


load_dotenv()


DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'social_media_materials'),
    'port': int(os.getenv('DB_PORT', 3306))
}