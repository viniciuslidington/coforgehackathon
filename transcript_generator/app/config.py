import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv('GOOGLE_API_KEY')
R2_ENDPOINT = os.getenv('R2_URL')
R2_ACCESS_KEY = os.getenv('ACCESS_KEY_ID')
R2_SECRET_KEY = os.getenv('SECRET_ACCESS_KEY')
BUCKET_NAME = os.getenv('BUCKET_NAME', 'hackathon-traders-vtt')

if not GEMINI_KEY:
    raise ValueError("GOOGLE_API_KEY is missing in environment variables.")