import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(BASE_DIR), "data.sqlite3"))
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
COUNCIL_TITLE = os.getenv("COUNCIL_TITLE", "Knights of Columbus Council")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "0"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@example.com")
EMAIL_TEXT = os.getenv('EMAIL_TEXT', 'This is a default email text.')
#
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
