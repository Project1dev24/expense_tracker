from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from backend.database import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    # New column to track linked unregistered participants
    linked_unregistered_names = db.Column(db.Text, nullable=False, default='[]')
    
    # Relationships
    trips_created = db.relationship('Trip', backref='admin', lazy='dynamic', foreign_keys='Trip.admin_id')
    
    def set_password(self, password):
        """Set the password for the user"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the provided password matches the user's password"""
        return check_password_hash(self.password_hash, password)
    
    def update_last_seen(self):
        """Update the last seen timestamp for the user"""
        self.last_seen = datetime.utcnow()
        from backend.database import db
        db.session.commit()
    
    def get_trips(self):
        """Get all trips where user is a participant or admin"""
        from .trip import Trip
        admin_trips = Trip.query.filter_by(admin_id=self.id).all()
        # Find trips where user is a participant (stored in JSON field)
        participant_trips = Trip.query.filter(Trip.participants.contains(f'"{self.id}"')).all()
        # Combine and remove duplicates
        all_trips = list(set(admin_trips + participant_trips))
        return all_trips
    
    def get_total_balance(self):
        """Calculate total balance across all trips"""
        trips = self.get_trips()
        total_balance = 0
        for trip in trips:
            total_balance += trip.calculate_user_balance(self.id)
        return total_balance
    
    # Get expenses paid by this user
    def get_expenses_paid(self):
        from .expense import Expense
        return Expense.query.filter(Expense.payer_id == str(self.id)).all()
    
    def get_linked_unregistered_names(self):
        """Get list of unregistered participant names linked to this user"""
        print(f"DEBUG: get_linked_unregistered_names called for user {self.id}")
        if not self.linked_unregistered_names or self.linked_unregistered_names == 'null':
            print(f"DEBUG: No linked_unregistered_names found, returning empty list")
            return []
        try:
            import json
            result = json.loads(self.linked_unregistered_names)
            print(f"DEBUG: get_linked_unregistered_names returning: {result}")
            return result
        except (json.JSONDecodeError, TypeError) as e:
            print(f"DEBUG: Error parsing linked_unregistered_names: {e}, returning empty list")
            return []
    
    def set_linked_unregistered_names(self, names):
        """Set the list of unregistered participant names linked to this user"""
        print(f"DEBUG: set_linked_unregistered_names called for user {self.id} with names: {names}")
        import json
        self.linked_unregistered_names = json.dumps(names)
        print(f"DEBUG: set_linked_unregistered_names completed, linked_unregistered_names now: {self.linked_unregistered_names}")
    
    def add_linked_unregistered_name(self, name):
        """Add an unregistered participant name to this user's linked list"""
        print(f"DEBUG: add_linked_unregistered_name called for user {self.id} with name: {name}")
        linked_names = self.get_linked_unregistered_names()
        print(f"DEBUG: Current linked names: {linked_names}")
        if name not in linked_names:
            linked_names.append(name)
            print(f"DEBUG: Name not in list, adding it. New list: {linked_names}")
            self.set_linked_unregistered_names(linked_names)
            print(f"DEBUG: add_linked_unregistered_name returning True")
            return True
        print(f"DEBUG: Name already in list, not adding. Returning False")
        return False
    
    def remove_linked_unregistered_name(self, name):
        """Remove an unregistered participant name from this user's linked list"""
        print(f"DEBUG: remove_linked_unregistered_name called for user {self.id} with name: {name}")
        linked_names = self.get_linked_unregistered_names()
        print(f"DEBUG: Current linked names: {linked_names}")
        if name in linked_names:
            linked_names.remove(name)
            print(f"DEBUG: Name found and removed. New list: {linked_names}")
            self.set_linked_unregistered_names(linked_names)
            print(f"DEBUG: remove_linked_unregistered_name returning True")
            return True
        print(f"DEBUG: Name not found in list. Returning False")
        return False

    def __repr__(self):
        return f'<User {self.name}>'