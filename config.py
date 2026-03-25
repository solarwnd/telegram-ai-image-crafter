import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Tokens and API keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# URL API ComfyUI (локальный сервер)
COMFYUI_SERVER_URL = os.getenv("COMFYUI_SERVER_URL", "http://127.0.0.1:8188")

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# Create directories on config initialization
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)
