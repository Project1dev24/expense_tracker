import os
from datetime import timedelta

class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-development-only'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)
    
    # Application settings
    DEFAULT_CURRENCY = 'INR'
    
    # Expense splitting methods
    SPLIT_METHODS = {
        'equal': 'Split equally among all participants',
        'exact': 'Specify exact amount for each participant',
        'itemized': 'Split by items consumed by each participant'
    }
