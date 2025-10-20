import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.app_factory import create_app
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    # Run the application
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    # Use port 5003 instead of 5001 to avoid conflicts
    app.run(debug=debug, host='0.0.0.0', port=5003)