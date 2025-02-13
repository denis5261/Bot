from dotenv import load_dotenv
import os
import logging

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
LOG_FILE = "requests_log.json"
REQUEST_LIMIT_mes = 25
REQUEST_LIMIT_pdf = 5

ADMIN_IDS = ['696933310']
