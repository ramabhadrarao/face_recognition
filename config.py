import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    COMPREFACE_URL = os.environ.get('COMPREFACE_URL') or 'http://69.62.73.201:8000'
    COMPREFACE_API_KEY = os.environ.get('COMPREFACE_API_KEY') or 'your-api-key-here'
    
    # Simple user store (in production, use a database)
    USERS = {
        'admin': 'Admin@123!',  # Change this!
        'user1': 'user123'
    }