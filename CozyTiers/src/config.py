import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
REGISTER_USER_IDS = [int(x.strip()) for x in os.getenv('REGISTER_USER_IDS', '').split(',') if x.strip().isdigit()]