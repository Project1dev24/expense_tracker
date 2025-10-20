from datetime import datetime
import json
from backend.database import db

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='INR')
    category = db.Column(db.String(50), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Split method: 'equal', 'exact', 'itemized'
    split_method = db.Column(db.String(20), default='equal')
    
    # Relationships
    payer_id = db.Column(db.String(100), nullable=False)  # Can be user ID or 'unregistered_name'
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    
    # Define a property to check if payer is registered or unregistered
    @property
    def is_payer_registered(self):
        return not self.payer_id.startswith('unregistered_')
    
    # JSON fields to store participant IDs and their shares
    participants = db.Column(db.Text, nullable=False, default='[]')  # Registered participants
    shares = db.Column(db.Text, nullable=False, default='{}')  # Shares for all participants
    items = db.Column(db.Text, nullable=True, default='[]')  # For itemized expenses and unregistered participants
    
    def get_participants_list(self):
        """Convert JSON string to list of participant IDs"""
        return json.loads(self.participants)
    
    def set_participants_list(self, participants):
        """Convert list of participant IDs to JSON string"""
        self.participants = json.dumps(participants)
    
    def get_shares(self):
        """Convert JSON string to dict of shares"""
        return json.loads(self.shares)
    
    def set_shares(self, shares):
        """Convert dict of shares to JSON string"""
        self.shares = json.dumps(shares)
    
    def get_items(self):
        """Convert JSON string to list of items"""
        return json.loads(self.items) if self.items else []
    
    def set_items(self, items):
        """Convert list of items to JSON string"""
        self.items = json.dumps(items)
        
    def get_unregistered_participants(self):
        """Get unregistered participants from the items data"""
        try:
            # First try to parse the items field
            if not self.items:
                return []
                
            items_data = json.loads(self.items)
            
            # Check for unregistered_participants key in the items dictionary
            if isinstance(items_data, dict):
                if 'unregistered_participants' in items_data:
                    return items_data['unregistered_participants']
                elif 'unregistered' in items_data:
                    return items_data['unregistered']
            
            # If items_data is a list of items with 'unregistered' lists
            if isinstance(items_data, list):
                # Collect all unregistered participants from all items
                unregistered = set()
                for item in items_data:
                    if isinstance(item, dict) and 'unregistered' in item:
                        for name in item['unregistered']:
                            unregistered.add(name)
                return list(unregistered)
            
            # Check if the shares field contains unregistered participants
            shares = self.get_shares()
            if shares:
                unregistered = []
                for user_id in shares.keys():
                    if user_id.startswith('unregistered_'):
                        name = user_id.replace('unregistered_', '')
                        unregistered.append(name)
                if unregistered:
                    return unregistered
                    
            return []
        except Exception as e:
            print(f"Error getting unregistered participants: {str(e)}")
            return []
    
    def calculate_equal_split(self, unregistered_participants=None):
        """Calculate equal shares for all participants including unregistered ones"""
        participants = self.get_participants_list()
        
        # If unregistered_participants parameter is None, try to get it from the expense
        if unregistered_participants is None:
            unregistered_participants = self.get_unregistered_participants()
            print(f"Retrieved {len(unregistered_participants)} unregistered participants from expense data")
        
        # Include unregistered participants in the calculation
        total_participants = len(participants)
        if unregistered_participants:
            total_participants += len(unregistered_participants)
            print(f"Including {len(unregistered_participants)} unregistered participants in equal split")
        
        if total_participants == 0:
            return {}
        
        # Calculate equal share for each participant
        share = round(self.amount / total_participants, 2)
        print(f"Equal share per participant: {share} (total participants: {total_participants})")
        
        # Create shares dictionary for registered participants
        shares = {participant: share for participant in participants}
        
        # Add shares for unregistered participants
        for name in unregistered_participants:
            shares[f'unregistered_{name}'] = share
            print(f"Added share for unregistered participant: {name}")
        
        # Adjust for rounding errors
        total = sum(shares.values())
        expected_total = self.amount
        
        if abs(total - expected_total) > 0.01 and shares:  # Only adjust if we have participants and there's a difference
            # Add the difference to the first participant
            first_participant = next(iter(shares.keys()))
            diff = round(expected_total - total, 2)
            shares[first_participant] = round(shares[first_participant] + diff, 2)
            print(f"Adjusted share for {first_participant} by {diff} to account for rounding")
        
        return shares
    
    def calculate_exact_split(self, shares_input, unregistered_participants=None):
        """Calculate exact shares based on input, including unregistered participants"""
        if not shares_input:
            return {}
        
        # Convert all values to float for calculation
        processed_shares = {user_id: float(amount) for user_id, amount in shares_input.items()}
        
        # Calculate total of registered participants' shares
        registered_total = sum(processed_shares.values())
        
        # Log for debugging
        print(f"Exact split - Registered total: {registered_total}, Expense amount: {self.amount}")
        
        # If the total doesn't match the expense amount and we have unregistered participants,
        # it's likely because the unregistered participants' shares aren't included in shares_input
        if abs(registered_total - self.amount) > 0.01 and unregistered_participants:
            print(f"Exact split - Difference detected, likely due to unregistered participants")
            # We don't need to raise an error as the unregistered participants' shares are stored separately
        elif abs(registered_total - self.amount) > 0.01:
            # If no unregistered participants, the totals should match
            print(f"Exact split - Error: Sum of shares ({registered_total}) does not equal expense amount ({self.amount})")
            # Adjust the first participant's share to make up the difference
            if processed_shares:
                first_key = next(iter(processed_shares))
                diff = round(self.amount - registered_total, 2)
                processed_shares[first_key] = round(processed_shares[first_key] + diff, 2)
                print(f"Exact split - Adjusted first participant's share by {diff}")
        
        return processed_shares
    
    def calculate_itemized_split(self, items_input, unregistered_participants=None):
        """Calculate shares based on items consumed by each participant, including unregistered ones"""
        if not items_input:
            return {}
        
        # Structure of items_input:
        # [
        #   {
        #     "name": "Pizza",
        #     "price": 500,
        #     "participants": ["1", "2", "3"],
        #     "unregistered": ["John", "Mary"]
        #   },
        #   ...
        # ]
        
        print(f"Calculating itemized split with {len(items_input)} items")
        print(f"Items data: {items_input}")
        
        # Initialize shares for all participants
        shares = {}
        for item in items_input:
            item_price = float(item['price'])
            item_participants = item['participants']
            item_unregistered = item.get('unregistered', [])
            
            # Count total participants for this item (both registered and unregistered)
            total_item_participants = len(item_participants) + len(item_unregistered)
            if total_item_participants == 0:
                print(f"Warning: Item '{item.get('name', 'unnamed')}' has no participants")
                continue
                
            # Split item price equally among all item participants
            per_person = round(item_price / total_item_participants, 2)
            
            # Add shares for registered participants
            for participant in item_participants:
                if participant in shares:
                    shares[participant] = round(shares[participant] + per_person, 2)
                else:
                    shares[participant] = per_person
            
            # Add shares for unregistered participants
            for name in item_unregistered:
                unregistered_id = f'unregistered_{name}'
                if unregistered_id in shares:
                    shares[unregistered_id] = round(shares[unregistered_id] + per_person, 2)
                else:
                    shares[unregistered_id] = per_person
        
        # Validate that sum of shares equals the expense amount
        total = sum(shares.values())
        if abs(total - self.amount) > 0.01:  # Allow for small rounding errors
            # Adjust the first participant's share to match the total
            diff = round(self.amount - total, 2)
            first_participant = list(shares.keys())[0]
            shares[first_participant] = round(shares[first_participant] + diff, 2)
        
        return shares
    
    def update_split(self, split_method, participants, shares_data=None, items_data=None, unregistered_participants=None):
        """Update the expense split based on the selected method"""
        try:
            print(f"Updating split with method: {split_method}")
            print(f"Participants: {participants}")
            print(f"Unregistered participants: {unregistered_participants}")
            
            # Set the split method
            self.split_method = split_method
            
            # Save the registered participants list
            if participants is not None:
                self.set_participants_list(participants)
                print(f"Set participants list: {self.participants}")
            
            # Store unregistered participants in the items field
            items_dict = {}
            
            # If we already have items data, try to preserve it
            if self.items:
                try:
                    existing_items = json.loads(self.items)
                    if isinstance(existing_items, dict):
                        items_dict = existing_items
                    elif isinstance(existing_items, list) and items_data is None:
                        # If existing items is a list and no new items data, preserve it as 'items'
                        items_dict['items'] = existing_items
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing existing items: {e}")
                    # Initialize with empty dict if there's an error
                    items_dict = {}
            
            # Add unregistered participants to the items dictionary
            if unregistered_participants:
                items_dict['unregistered_participants'] = unregistered_participants
                print(f"Added unregistered participants to items dict: {unregistered_participants}")
            
            # If we have new items data, add it to the dictionary
            if items_data and isinstance(items_data, list):
                items_dict['items'] = items_data
                print(f"Added items data to items dict: {len(items_data)} items")
            
            # Save the updated items dictionary
            self.items = json.dumps(items_dict)
            print(f"Updated items field: {self.items}")
            
            # Calculate shares based on split method
            if split_method == 'equal':
                # For equal split, include unregistered participants in the calculation
                calculated_shares = self.calculate_equal_split(unregistered_participants)
            elif split_method == 'exact':
                # For exact split, use the provided shares data
                if not shares_data:
                    shares_data = {}
                calculated_shares = self.calculate_exact_split(shares_data, unregistered_participants)
            elif split_method == 'itemized':
                # For itemized split, use the provided items data
                if not items_data:
                    # If no items data provided, try to get it from the items field
                    try:
                        items_dict = json.loads(self.items)
                        if 'items' in items_dict and isinstance(items_dict['items'], list):
                            items_data = items_dict['items']
                    except (json.JSONDecodeError, TypeError, KeyError):
                        # If we can't get items data, use an empty list
                        items_data = []
                calculated_shares = self.calculate_itemized_split(items_data, unregistered_participants)
            else:
                raise ValueError(f"Invalid split method: {split_method}")
            
            # Save the calculated shares
            self.set_shares(calculated_shares)
            print(f"Set shares: {self.shares}")
            
            return calculated_shares
        except Exception as e:
            import traceback
            print(f"Error in update_split: {str(e)}")
            traceback.print_exc()
            raise
    
    def __repr__(self):
        return f'<Expense {self.description}: {self.currency} {self.amount}>'
