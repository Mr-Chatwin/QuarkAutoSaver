import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    TMDB_API_URL = os.getenv("TMDB_API_URL", "https://api.themoviedb.org/3")
    QUARK_COOKIE = os.getenv("QUARK_COOKIE", "")
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
    PANSOU_API_URL = os.getenv("PANSOU_API_URL", "https://so.252035.xyz")
    # Base folder ID in Quark Drive where all media should be saved (0 is root)
    QUARK_BASE_FOLDER_ID = os.getenv("QUARK_BASE_FOLDER_ID", "0")
    # Whitelisted Telegram user IDs, format: 12345,67890 (empty means allow all)
    ALLOWED_USERS = [int(x.strip()) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip().isdigit()]
    # Admin Telegram user IDs, format: 12345,67890 (empty means none)
    ADMIN_USERS = [int(x.strip()) for x in os.getenv("ADMIN_USERS", "").split(",") if x.strip().isdigit()]
    
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

settings = Settings()
