import os
from flask import Flask
from flask_login import LoginManager
from backend.database import db
from backend.models.user import User
from datetime import date, timedelta

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object('backend.config.Config')
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register template filter for trip time labels
    @app.template_filter('trip_time_label')
    def trip_time_label(trip_date):
        """
        Returns a descriptive label for a trip based on how long ago it occurred.
        
        Args:
            trip_date (date): The date of the trip
            
        Returns:
            str: A descriptive label like 'Yesterday', 'Recent', 'Last Week', etc.
        """
        if not trip_date:
            return "Past"
            
        today = date.today()
        if hasattr(trip_date, 'date'):
            trip_date = trip_date.date()
            
        days_ago = (today - trip_date).days
        
        if days_ago == 1:
            return "Yesterday"
        elif days_ago <= 7:
            return "Recent"
        elif days_ago <= 14:
            return "Last Week"
        elif days_ago <= 30:
            return "Last Month"
        else:
            return "Earlier"
    
    # Register blueprints
    from backend.routes.auth import bp as auth_bp
    from backend.routes.main import bp as main_bp
    from backend.routes.trips import trips_bp
    from backend.routes.expenses import bp as expenses_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(trips_bp, url_prefix='/trips')
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    
    return app