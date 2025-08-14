import os
from dotenv import load_dotenv
import pytz

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    COMPREFACE_URL = os.environ.get('COMPREFACE_URL') or 'http://69.62.73.201:8000'
    COMPREFACE_API_KEY = os.environ.get('COMPREFACE_API_KEY') or 'your-api-key-here'
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///face_recognition.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Timezone configuration
    TIMEZONE = pytz.timezone('Asia/Kolkata')  # Indian Standard Time
    
    # Simple user store (in production, use a database)
    USERS = {
        'admin': 'Admin@123!',  # Change this!
        'user1': 'user123'
    }
    
    # Attendance settings
    MINIMUM_INTERVAL_MINUTES = 30  # Minimum time between punch in/out
    WORKING_HOURS_PER_DAY = 8
    SIMILARITY_THRESHOLD = 0.97  # Minimum similarity for recognition
    
    # Salary calculation settings
    WORKING_DAYS_PER_MONTH = 22
    INCOMPLETE_DAY_POLICY = 'HALF_DAY'  # Options: 'HALF_DAY', 'NO_PAY', 'FULL_DAY'
    MINIMUM_HOURS_FOR_FULL_DAY = 6  # Minimum hours to count as full day