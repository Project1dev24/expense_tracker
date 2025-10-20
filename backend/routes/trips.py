from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import current_user, login_required
from datetime import datetime
from backend.models.trip import Trip
from backend.models.user import User
from backend.models.expense import Expense
from backend.models.unregistered_participant import UnregisteredParticipant
from backend.database import db
from sqlalchemy import func
from io import BytesIO
import json

# Define the blueprint without a URL prefix
trips_bp = Blueprint('trips', __name__)

@trips_bp.route('/')
@login_required
def list_trips():
    # Get all trips where user is a participant or admin
    trips = current_user.get_trips()
    # Sort trips by start date (most recent first)
    trips = sorted(trips, key=lambda t: t.start_date, reverse=True)
    return render_template('trips/list.html', trips=trips)

@trips_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_trip():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        # Validate input
        if not name or not start_date_str or not end_date_str:
            flash('Name and dates are required', 'error')
            return render_template('trips/add.html')
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format', 'error')
            return render_template('trips/add.html')
        
        if end_date < start_date:
            flash('End date cannot be before start date', 'error')
            return render_template('trips/add.html')
        
        # Create new trip
        trip = Trip(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            admin_id=current_user.id,
            participants='[]'  # Initialize with empty JSON array
        )
        
        # Add current user as a participant
        trip.add_participant(current_user.id)
        
        db.session.add(trip)
        db.session.commit()
        
        flash('Trip created successfully', 'success')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))
    
    return render_template('trips/add.html')

@trips_bp.route('/test')
def test_route():
    return "Test route works!"

@trips_bp.route('/<int:trip_id>')
@login_required
def view_trip(trip_id):
    try:
        # Debug information
        print(f"Attempting to view trip with ID: {trip_id}")
        
        # Get the trip
        trip = Trip.query.get_or_404(trip_id)
        print(f"Found trip: {trip.name}")
        
        # Check if user is a participant or admin
        participants = trip.get_participants_list()
        print(f"Participants: {participants}")
        print(f"Current user ID: {current_user.id}")
        print(f"Trip admin ID: {trip.admin_id}")
        
        if str(current_user.id) not in participants and current_user.id != trip.admin_id:
            print("Access denied: User is not a participant or admin")
            flash('You do not have access to this trip', 'error')
            return redirect(url_for('trips.list_trips'))
        
        # Get expenses for this trip
        expenses = Expense.query.filter_by(trip_id=trip_id).order_by(Expense.date.desc()).all()
        print(f"Found {len(expenses)} expenses")
        
        # Get user names for display
        participant_ids = trip.get_participants_list()
        if str(trip.admin_id) not in participant_ids:
            participant_ids.append(str(trip.admin_id))
        
        # Get registered participants
        registered_participants = User.query.filter(User.id.in_([int(pid) for pid in participant_ids if pid.isdigit()])).all()
        user_map = {str(user.id): user.name for user in registered_participants}
        
        # Check for linked unregistered participants and map them to their registered user names
        # This needs to be done BEFORE adding unregistered participants to avoid overriding
        linked_unregistered_participants = trip.unregistered_participants_list.filter(UnregisteredParticipant.linked_user_id.isnot(None)).all()
        for linked_participant in linked_unregistered_participants:
            unregistered_id = f'unregistered_{linked_participant.name}'
            linked_user = User.query.get(linked_participant.linked_user_id)
            if linked_user:
                # Map the unregistered ID to the registered user's name
                user_map[unregistered_id] = linked_user.name
        
        # Add unregistered participants to user_map (use display names)
        # Only add unregistered participants that are NOT linked to avoid overriding linked mappings
        unregistered_names = trip.get_unregistered_participants_display()
        for name in unregistered_names:
            unregistered_id = f'unregistered_{name.lower()}'
            # Only add to user_map if not already mapped (i.e., not linked)
            if unregistered_id not in user_map:
                user_map[unregistered_id] = name
        
        # Also add any unregistered participants that might be in expenses
        expense_payers = [str(e.payer_id) for e in expenses]
        for payer_id in expense_payers:
            if payer_id.startswith('unregistered_'):
                name = payer_id.replace('unregistered_', '')
                if payer_id not in user_map:
                    user_map[payer_id] = name
        
        # Create participant objects for display (both registered and unregistered)
        participants = []
        
        # Add registered participants
        for user in registered_participants:
            participants.append({
                'id': str(user.id),
                'name': user.name,
                'type': 'registered'
            })
        
        # Add unregistered participants (use display names)
        # Only show unregistered participants that are NOT linked
        unregistered_names = trip.get_unregistered_participants_display()
        for name in unregistered_names:
            unregistered_id = f'unregistered_{name.lower()}'
            # Only add to participants list if not linked
            if unregistered_id not in [f'unregistered_{lp.name}' for lp in linked_unregistered_participants]:
                participants.append({
                    'id': unregistered_id,  # Store with the unregistered ID format
                    'name': name,  # Display name is already in title case
                    'type': 'unregistered'
                })
                # Also add to user_map for settlements display (if not already added)
                if unregistered_id not in user_map:
                    user_map[unregistered_id] = name
        
        # Calculate total expenses
        total_expenses = trip.calculate_total_expenses()
        
        # Calculate settlements with error handling
        try:
            settlements = trip.calculate_settlements()
        except MemoryError:
            print("Memory error occurred during settlements calculation, using empty settlements")
            settlements = []
        except Exception as e:
            print(f"Error calculating settlements: {str(e)}")
            settlements = []
        
        # Get expense contributors
        expense_contributors = trip.get_expense_contributors()
        
        return render_template('trips/view.html', 
                            trip=trip, 
                            expenses=expenses, 
                            participants=participants,
                            user_map=user_map,
                            total_expenses=total_expenses,
                            settlements=settlements,
                            expense_contributors=expense_contributors)
                            
    except Exception as e:
        print(f"Error viewing trip: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error viewing trip: {str(e)}', 'error')
        return redirect(url_for('trips.list_trips'))
    
    # This code is now inside the try block

@trips_bp.route('/<int:trip_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is the admin
    if trip.admin_id != current_user.id:
        flash('You do not have permission to edit this trip', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip_id))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        # Validate input
        if not name or not start_date_str or not end_date_str:
            flash('Name and dates are required', 'error')
            return render_template('trips/edit.html', trip=trip)
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format', 'error')
            return render_template('trips/edit.html', trip=trip)
        
        if end_date < start_date:
            flash('End date cannot be before start date', 'error')
            return render_template('trips/edit.html', trip=trip)
        
        # Update trip
        trip.name = name
        trip.description = description
        trip.start_date = start_date
        trip.end_date = end_date
        
        db.session.commit()
        
        flash('Trip updated successfully', 'success')
        return redirect(url_for('trips.view_trip', trip_id=trip.id))
    
    # Format dates for the form
    start_date = trip.start_date.strftime('%Y-%m-%d')
    end_date = trip.end_date.strftime('%Y-%m-%d')
    
    return render_template('trips/edit.html', 
                          trip=trip,
                          start_date=start_date,
                          end_date=end_date)

@trips_bp.route('/<int:trip_id>/manage-participants', methods=['GET', 'POST'])
@login_required
def manage_participants(trip_id):
    print(f"DEBUG: manage_participants called with trip_id: {trip_id}")
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is the admin
    if trip.admin_id != current_user.id:
        flash('You do not have permission to manage participants', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip_id))
    
    if request.method == 'POST':
        print(f"DEBUG: POST request received")
        print(f"DEBUG: Request headers: {dict(request.headers)}")
        print(f"DEBUG: Content-Type: {request.headers.get('Content-Type')}")
        print(f"DEBUG: Request form data: {request.form}")
        print(f"DEBUG: Request JSON data: {request.get_json()}")
        
        action = request.form.get('action') if request.form.get('action') else (request.get_json().get('action') if request.get_json() else None)
        print(f"DEBUG: Action: {action}")
        
        if action == 'add_registered':
            email = request.form.get('email')
            
            # Find user by email
            user = User.query.filter_by(email=email).first()
            if not user:
                flash(f'No user found with email: {email}', 'error')
                return redirect(url_for('trips.manage_participants', trip_id=trip_id))
            
            # Add user to trip
            if trip.add_participant(user.id):
                db.session.commit()
                flash(f'Added {user.name} to the trip', 'success')
            else:
                flash(f'{user.name} is already a participant', 'info')
        
        elif action == 'add_unregistered':
            name = request.form.get('name')
            
            # Add unregistered participant by name
            if trip.add_unregistered_participant(name):
                db.session.commit()
                # Display name in title case
                display_name = name.strip().title()
                flash(f'Added {display_name} to the trip', 'success')
            else:
                display_name = name.strip().title()
                flash(f'{display_name} is already a participant or the name is invalid', 'info')
        
        elif action == 'add_participant':
            # New unified approach
            participant_input = request.form.get('participant_input') if request.form.get('participant_input') else (request.get_json().get('participant_input') if request.get_json() else None)
            
            # Validate input
            if not participant_input:
                return jsonify({'success': False, 'message': 'Please enter a name or email'}) if request.headers.get('Content-Type') == 'application/json' else flash('Please enter a name or email', 'error')
            
            # Check if input is an email (contains @)
            if '@' in participant_input and '.' in participant_input:
                # Treat as email - try to find existing user
                user = User.query.filter(func.lower(User.email) == func.lower(participant_input)).first()
                if user:
                    # User exists, add as registered participant
                    if trip.add_participant(user.id):
                        db.session.commit()
                        return jsonify({'success': True, 'message': f'Added {user.name} to the trip as a registered user', 'type': 'registered'}) if request.headers.get('Content-Type') == 'application/json' else redirect(url_for('trips.manage_participants', trip_id=trip_id))
                    else:
                        return jsonify({'success': False, 'message': f'{user.name} is already a participant'}) if request.headers.get('Content-Type') == 'application/json' else flash(f'{user.name} is already a participant', 'info')
                else:
                    # User doesn't exist, treat as unregistered participant with email
                    name = participant_input.split('@')[0].title()  # Use part before @ as name
                    if trip.add_unregistered_participant(name):
                        db.session.commit()
                        return jsonify({'success': True, 'message': f'Added {name} to the trip as an unregistered participant', 'type': 'unregistered'}) if request.headers.get('Content-Type') == 'application/json' else redirect(url_for('trips.manage_participants', trip_id=trip_id))
                    else:
                        return jsonify({'success': False, 'message': f'{name} is already a participant'}) if request.headers.get('Content-Type') == 'application/json' else flash(f'{name} is already a participant', 'info')
            else:
                # Treat as name - first check if a user exists with this name
                # Convert input to title case for consistent matching
                name_input = participant_input.strip().title()
                
                # Try to find existing user with this name (case-insensitive)
                user = User.query.filter(func.lower(User.name) == func.lower(name_input)).first()
                if user:
                    # User exists with this name, add as registered participant
                    if trip.add_participant(user.id):
                        db.session.commit()
                        return jsonify({'success': True, 'message': f'Added {user.name} to the trip as a registered user', 'type': 'registered'}) if request.headers.get('Content-Type') == 'application/json' else redirect(url_for('trips.manage_participants', trip_id=trip_id))
                    else:
                        return jsonify({'success': False, 'message': f'{user.name} is already a participant'}) if request.headers.get('Content-Type') == 'application/json' else flash(f'{user.name} is already a participant', 'info')
                else:
                    # No user exists with this name, add as unregistered participant
                    if trip.add_unregistered_participant(participant_input):
                        db.session.commit()
                        display_name = participant_input.strip().title()
                        return jsonify({'success': True, 'message': f'Added {display_name} to the trip as an unregistered participant', 'type': 'unregistered'}) if request.headers.get('Content-Type') == 'application/json' else redirect(url_for('trips.manage_participants', trip_id=trip_id))
                    else:
                        display_name = participant_input.strip().title()
                        return jsonify({'success': False, 'message': f'{display_name} is already a participant'}) if request.headers.get('Content-Type') == 'application/json' else flash(f'{display_name} is already a participant', 'info')
        
        elif action == 'remove_registered':
            user_id = request.form.get('user_id')
            
            # Remove user from trip
            if trip.remove_participant(user_id):
                db.session.commit()
                flash('Participant removed from the trip', 'success')
            else:
                flash('Participant not found', 'error')
        
        elif action == 'remove_unregistered':
            name = request.form.get('name')
            
            # Remove unregistered participant
            if trip.remove_unregistered_participant(name):
                db.session.commit()
                flash(f'Removed {name} from the trip', 'success')
            else:
                flash('Participant not found', 'error')
        
        elif action == 'link_participant':
            print(f"DEBUG: link_participant action triggered in manage_participants route")
            print(f"DEBUG: Request headers: {dict(request.headers)}")
            print(f"DEBUG: Request content type: {request.headers.get('Content-Type')}")
            # Handle both form data and JSON data (AJAX requests)
            if request.headers.get('Content-Type') == 'application/json':
                print(f"DEBUG: Processing JSON request")
                # AJAX request with JSON data
                json_data = request.get_json()
                print(f"DEBUG: JSON data received: {json_data}")
                name = json_data.get('name')
                email = json_data.get('email')
            else:
                print(f"DEBUG: Processing form data")
                # Regular form submission
                name = request.form.get('name')
                email = request.form.get('email')
            
            print(f"DEBUG: Linking participant - name: '{name}', email: '{email}'")
            print(f"DEBUG: Name type: {type(name)}, Name length: {len(name) if name else 0}")
            
            # Validate that we have a name
            if not name or not name.strip():
                print(f"DEBUG: Participant name is missing or empty")
                # Check if this is an AJAX request
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({'success': False, 'message': 'Participant name is missing. Please try again.'}), 400
                else:
                    flash('Participant name is missing. Please try again.', 'error')
                    return redirect(url_for('trips.manage_participants', trip_id=trip_id))
            
            # Find user by email (case-insensitive)
            print(f"DEBUG: Searching for user with email: {email}")
            user = User.query.filter(func.lower(User.email) == func.lower(email)).first()
            if not user:
                print(f"DEBUG: No user found with email: {email}")
                # Check if this is an AJAX request
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({'success': False, 'message': f'No user found with email: {email}'}), 404
                else:
                    flash(f'No user found with email: {email}', 'error')
                    return redirect(url_for('trips.manage_participants', trip_id=trip_id))
            
            print(f"DEBUG: Found user - id: {user.id}, name: {user.name}, email: {user.email}")
            
            # Check if the user is a participant of this trip or is the admin
            participant_ids = trip.get_participants_list()
            print(f"DEBUG: Trip participants: {participant_ids}")
            print(f"DEBUG: Trip admin_id: {trip.admin_id}")
            print(f"DEBUG: Checking if user {user.id} is in participants or is admin")
            print(f"DEBUG: user.id: {user.id}, str(user.id): {str(user.id)}")
            print(f"DEBUG: user.id != trip.admin_id: {user.id != trip.admin_id}")
            print(f"DEBUG: str(user.id) in participant_ids: {str(user.id) in participant_ids}")
            
            # Check if user is already a participant in this trip
            if str(user.id) in participant_ids:
                print(f"DEBUG: User {user.name} is already a participant in this trip")
                # Check if this is an AJAX request
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({'success': False, 'message': f'User {user.name} is already added in this trip'}), 400
                else:
                    flash(f'User {user.name} is already added in this trip', 'error')
                    return redirect(url_for('trips.manage_participants', trip_id=trip_id))
            
            # Check if user is the admin (admins are automatically participants)
            if user.id == trip.admin_id:
                print(f"DEBUG: User {user.name} is the admin of this trip")
                # Check if this is an AJAX request
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({'success': False, 'message': f'User {user.name} is already the admin of this trip'}), 400
                else:
                    flash(f'User {user.name} is already the admin of this trip', 'error')
                    return redirect(url_for('trips.manage_participants', trip_id=trip_id))
            
            # Link unregistered participant to user
            # The name passed from the template is in display format (title case)
            # Convert to lowercase to match database storage format
            name_lower = name.strip().lower()
            print(f"DEBUG: All validations passed, calling link_participant with name: '{name_lower}', user_id: {user.id}")
            result = trip.link_participant(name_lower, user.id)
            print(f"DEBUG: link_participant result: {result}")
            
            if result:
                db.session.commit()
                print(f"DEBUG: Database commit completed")
                # Check if this is an AJAX request
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({'success': True, 'message': f'Linked {name} to user {user.name}'})
                else:
                    flash(f'Linked {name} to user {user.name}', 'success')
            else:
                print(f"DEBUG: Failed to link {name} to user {user.name}")
                # Check if this is an AJAX request
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({'success': False, 'message': f'Failed to link {name} to user {user.name}'}), 400
                else:
                    flash(f'Failed to link {name} to user {user.name}', 'error')
        
        elif action == 'sync_linked_participants':
            # New action to synchronize all linked participants
            print(f"DEBUG: sync_linked_participants action triggered")
            
            # Get all linked unregistered participants for this trip
            linked_participants = trip.unregistered_participants_list.filter(UnregisteredParticipant.linked_user_id.isnot(None)).all()
            
            sync_count = 0
            for linked_participant in linked_participants:
                unregistered_id = f"unregistered_{linked_participant.name}"
                user_id = str(linked_participant.linked_user_id)
                
                print(f"DEBUG: Syncing {unregistered_id} to user {user_id}")
                
                # Update all expenses
                for expense in trip.expenses:
                    updated = False
                    
                    # Update payer_id if it matches the unregistered participant ID
                    if expense.payer_id == unregistered_id:
                        expense.payer_id = user_id
                        print(f"DEBUG: Updated payer_id from {unregistered_id} to {user_id} in expense {expense.id}")
                        updated = True
                    
                    # Update participants list if it contains the unregistered participant ID
                    participants = expense.get_participants_list()
                    if unregistered_id in participants:
                        participants.remove(unregistered_id)
                        participants.append(user_id)
                        expense.set_participants_list(participants)
                        print(f"DEBUG: Updated participants list in expense {expense.id}")
                        updated = True
                    
                    # Update shares to replace the unregistered participant with the registered user
                    shares = expense.get_shares()
                    if unregistered_id in shares:
                        amount = shares.pop(unregistered_id)
                        shares[user_id] = amount
                        expense.set_shares(shares)
                        print(f"DEBUG: Updated shares in expense {expense.id}")
                        updated = True
                    
                    if updated:
                        db.session.add(expense)
                        sync_count += 1
                
                # Update advances
                advances = trip.get_advances()
                if unregistered_id in advances:
                    amount = advances.pop(unregistered_id)
                    advances[user_id] = amount
                    trip.set_advances(advances)
                    print(f"DEBUG: Updated advances for {unregistered_id} to {user_id}")
                    sync_count += 1
                
                # Update general payments
                payments = trip.get_general_payments()
                payment_updated = False
                for payment in payments:
                    if payment.get('participant_id') == unregistered_id:
                        payment['participant_id'] = user_id
                        payment_updated = True
                        print(f"DEBUG: Updated general payment for {unregistered_id} to {user_id}")
                
                if payment_updated:
                    trip.set_general_payments(payments)
                    sync_count += 1
            
            # Commit all changes
            db.session.commit()
            
            flash(f'Synchronized {sync_count} linked participant records', 'success')
            print(f"DEBUG: Synchronization completed. {sync_count} records updated.")
        
        # For AJAX requests, return JSON response
        if request.headers.get('Content-Type') == 'application/json':
            # Get updated list of unregistered participants
            unregistered_participants = trip.get_unregistered_participants_display()
            return jsonify({'success': True, 'message': 'Operation completed', 'unregistered_participants': unregistered_participants})
        
        return redirect(url_for('trips.manage_participants', trip_id=trip_id))
    
    # Get current registered participants
    participant_ids = trip.get_participants_list()
    participants = User.query.filter(User.id.in_([int(pid) for pid in participant_ids if pid.isdigit()])).all()
    
    # Get all registered users for linking (including admin if not already in participants)
    all_registered_users = participants.copy()
    admin_user = User.query.get(trip.admin_id)
    if admin_user and admin_user not in all_registered_users:
        all_registered_users.append(admin_user)
    
    # Get unregistered participants (use display names)
    unregistered_participants = trip.get_unregistered_participants_display()
    
    return render_template('trips/manage_participants.html', 
                          trip=trip,
                          participants=participants,
                          unregistered_participants=unregistered_participants,
                          all_registered_users=all_registered_users)

@trips_bp.route('/<int:trip_id>/delete', methods=['POST'])
@login_required
def delete_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is the admin
    if trip.admin_id != current_user.id:
        flash('You do not have permission to delete this trip', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip_id))
    
    db.session.delete(trip)
    db.session.commit()
    
    flash('Trip deleted successfully', 'success')
    return redirect(url_for('trips.list_trips'))

@trips_bp.route('/<int:trip_id>/advances', methods=['GET', 'POST'])
@login_required
def manage_advances(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is a participant or admin
    participants = trip.get_participants_list()
    if str(current_user.id) not in participants and current_user.id != trip.admin_id:
        flash('You do not have access to this trip', 'error')
        return redirect(url_for('trips.list_trips'))
    
    # Get all participants (registered and unregistered)
    registered_participants = User.query.filter(User.id.in_([int(pid) for pid in trip.get_participants_list()])).all()
    registered_map = {str(user.id): user for user in registered_participants}
    
    # Add admin if not already in participants
    if str(trip.admin_id) not in [str(p.id) for p in registered_participants]:
        admin = User.query.get(trip.admin_id)
        registered_participants.append(admin)
        registered_map[str(admin.id)] = admin
    
    # Get unregistered participants (use display names)
    unregistered_participants = trip.get_unregistered_participants_display()
    
    # Get current advances
    advances = trip.get_advances()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            participant_id = request.form.get('participant_id')
            amount = request.form.get('amount')
            
            try:
                print(f"Adding advance for participant ID: {participant_id}, type: {type(participant_id)}")
                
                # Handle participant_id
                if participant_id is None:
                    flash('Participant must be selected', 'error')
                    return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                    
                amount = float(amount)
                if amount <= 0:
                    flash('Amount must be greater than zero', 'error')
                    return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
                # Add advance payment
                trip.add_advance(participant_id, amount)
                db.session.commit()
                
                # Recalculate all balances to ensure consistency
                balances = trip.recalculate_all_balances()
                
                # Determine participant name for the flash message
                if participant_id.startswith('unregistered_'):
                    name = participant_id.replace('unregistered_', '')
                    # Display name in title case
                    display_name = trip.get_unregistered_participant_display_name(name)
                    print(f"Detected unregistered participant with name: {name}")
                    flash(f'Added advance payment of ₹{amount} for {display_name}', 'success')
                else:
                    user = registered_map.get(participant_id)
                    name = user.name if user else 'Unknown'
                    flash(f'Added advance payment of ₹{amount} for {name}', 'success')
                    
                return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
            except (ValueError, TypeError) as e:
                flash(f'Invalid input: {str(e)}', 'error')
                return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
        elif action == 'edit':
            participant_id = request.form.get('participant_id')
            amount = request.form.get('amount')
            
            try:
                amount = float(amount)
                if amount <= 0:
                    flash('Amount must be greater than zero', 'error')
                    return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
                # Get current amount to calculate the difference
                current_amount = advances.get(participant_id, 0)
                amount_difference = amount - current_amount
                
                # Edit advance payment
                if not trip.edit_advance(participant_id, amount):
                    flash('Advance payment not found', 'error')
                    return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                    
                db.session.commit()
                
                # Recalculate all balances to ensure consistency
                balances = trip.recalculate_all_balances()
                
                # Determine participant name for the flash message
                if participant_id.startswith('unregistered_'):
                    name = participant_id.replace('unregistered_', '')
                    # Display name in title case
                    display_name = trip.get_unregistered_participant_display_name(name)
                    flash(f'Updated advance payment for {display_name} by ₹{amount_difference}', 'success')
                else:
                    user = registered_map.get(participant_id)
                    name = user.name if user else 'Unknown'
                    flash(f'Updated advance payment for {name} by ₹{amount_difference}', 'success')
                    
                return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
            except (ValueError, TypeError) as e:
                flash(f'Invalid input: {str(e)}', 'error')
                return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
        elif action == 'delete':
            participant_id = request.form.get('participant_id')
            
            try:
                print(f"Attempting to delete advance for participant ID: {participant_id}")
                # Debug the advance data
                advances = trip.get_advances()
                if participant_id in advances:
                    print(f"Advance to delete: {advances[participant_id]} for participant {participant_id}")
                else:
                    print(f"No advance found for participant: {participant_id}")
                    print(f"Available advances: {advances}")
                
                # Delete advance payment
                if not trip.delete_advance(participant_id):
                    flash('Advance payment not found', 'error')
                    return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                    
                db.session.commit()
                
                # Recalculate all balances to ensure consistency
                balances = trip.recalculate_all_balances()
                
                # Determine participant name for the flash message
                if participant_id.startswith('unregistered_'):
                    name = participant_id.replace('unregistered_', '')
                    # Display name in title case
                    display_name = trip.get_unregistered_participant_display_name(name)
                    flash(f'Deleted advance payment for {display_name}', 'success')
                else:
                    user = registered_map.get(participant_id)
                    name = user.name if user else 'Unknown'
                    flash(f'Deleted advance payment for {name}', 'success')
                    
                return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error deleting advance payment: {str(e)}', 'error')
                return redirect(url_for('trips.manage_advances', trip_id=trip_id))
                
        else:
            flash('Invalid action', 'error')
            return redirect(url_for('trips.manage_advances', trip_id=trip_id))
    
    # Format advances for display
    formatted_advances = []
    for participant_id, amount in advances.items():
        if participant_id.startswith('unregistered_'):
            name = participant_id.replace('unregistered_', '')
            # Display name in title case
            display_name = trip.get_unregistered_participant_display_name(name)
            formatted_advances.append({
                'id': participant_id,
                'name': display_name,
                'type': 'unregistered',
                'amount': amount
            })
        elif participant_id in registered_map:
            user = registered_map[participant_id]
            formatted_advances.append({
                'id': participant_id,
                'name': user.name,
                'type': 'registered',
                'amount': amount
            })
    
    # Sort advances by participant name
    formatted_advances.sort(key=lambda x: x['name'])
    
    return render_template('trips/manage_advances.html',
                          trip=trip,
                          registered_participants=registered_participants,
                          unregistered_participants=unregistered_participants,
                          advances=formatted_advances)

@trips_bp.route('/<int:trip_id>/payments', methods=['GET', 'POST'])
@login_required
def manage_payments(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is a participant or admin
    participants = trip.get_participants_list()
    if str(current_user.id) not in participants and current_user.id != trip.admin_id:
        flash('You do not have access to this trip', 'error')
        return redirect(url_for('trips.list_trips'))
    
    # Get all participants (registered and unregistered)
    registered_participants = User.query.filter(User.id.in_([int(pid) for pid in trip.get_participants_list()])).all()
    registered_map = {str(user.id): user for user in registered_participants}
    
    # Add admin if not already in participants
    if str(trip.admin_id) not in [str(p.id) for p in registered_participants]:
        admin = User.query.get(trip.admin_id)
        registered_participants.append(admin)
        registered_map[str(admin.id)] = admin
    
    # Get unregistered participants (use display names)
    unregistered_participants = trip.get_unregistered_participants_display()
    
    # Get current payments
    payments = trip.get_general_payments()
    
    # Get all expenses for this trip
    expenses = trip.expenses.all()
    
    # Calculate expense summary by category
    expense_summary = {}
    for expense in expenses:
        category = expense.category or 'Uncategorized'
        if category not in expense_summary:
            expense_summary[category] = {
                'count': 0,
                'total': 0
            }
        expense_summary[category]['count'] += 1
        expense_summary[category]['total'] += expense.amount
    
    # Convert to sorted list for display
    expense_summary_list = [
        {
            'category': category,
            'count': data['count'],
            'total': data['total']
        }
        for category, data in expense_summary.items()
    ]
    
    # Sort by total amount (highest first)
    expense_summary_list.sort(key=lambda x: x['total'], reverse=True)
    
    # Calculate overall totals
    total_expense_count = sum(item['count'] for item in expense_summary_list)
    total_expense_amount = sum(item['total'] for item in expense_summary_list)
    
    # Calculate general payment summary by extracting categories from descriptions
    payment_summary = {}
    
    # Format payments for display and calculate summary
    formatted_payments = []
    for payment in payments:
        participant_id = payment['participant_id']
        payment_amount = payment['amount']
        description = payment['description']
        
        # Extract payment category from description (use first word or 'Miscellaneous')
        category = description.split()[0].capitalize() if description else 'Miscellaneous'
        
        # Add to payment summary
        if category not in payment_summary:
            payment_summary[category] = {
                'count': 0,
                'total': 0
            }
        payment_summary[category]['count'] += 1
        payment_summary[category]['total'] += payment_amount
        
        # Format the payment for display
        if participant_id.startswith('unregistered_'):
            name = participant_id.replace('unregistered_', '')
            # Display name in title case
            display_name = trip.get_unregistered_participant_display_name(name)
            formatted_payments.append({
                'id': participant_id,
                'name': display_name,
                'type': 'unregistered',
                'amount': payment_amount,
                'description': description,
                'date': payment['date'],
                'expense_id': payment.get('expense_id')  # Use .get() to handle missing key
            })
        elif participant_id in registered_map:
            user = registered_map[participant_id]
            formatted_payments.append({
                'id': participant_id,
                'name': user.name,
                'type': 'registered',
                'amount': payment_amount,
                'description': description,
                'date': payment['date'],
                'expense_id': payment.get('expense_id')  # Use .get() to handle missing key
            })
    
    # Convert payment summary to sorted list for display
    payment_summary_list = [
        {
            'category': category,
            'count': data['count'],
            'total': data['total']
        }
        for category, data in payment_summary.items()
    ]
    
    # Sort by total amount (highest first)
    payment_summary_list.sort(key=lambda x: x['total'], reverse=True)
    
    # Calculate overall payment totals
    total_payment_count = sum(item['count'] for item in payment_summary_list)
    total_payment_amount = sum(item['total'] for item in payment_summary_list)
    
    # Sort payments by date (newest first)
    formatted_payments.sort(key=lambda x: x['date'], reverse=True)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            participant_id = request.form.get('participant_id')
            description = request.form.get('description')
            amount = request.form.get('amount')
            date_str = request.form.get('date')
            expense_id = request.form.get('expense_id')
            
            try:
                amount = float(amount)
                if amount <= 0:
                    flash('Amount must be greater than zero', 'error')
                    return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
                date = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Add general payment
                trip.add_general_payment(participant_id, amount, description, date, expense_id)
                db.session.commit()
                
                # Recalculate all balances to ensure consistency
                balances = trip.recalculate_all_balances()
                
                # Determine participant name for the flash message
                if participant_id.startswith('unregistered_'):
                    name = participant_id.replace('unregistered_', '')
                    # Display name in title case
                    display_name = trip.get_unregistered_participant_display_name(name)
                    flash(f'Added payment of ₹{amount} for {display_name}', 'success')
                else:
                    user = registered_map.get(participant_id)
                    name = user.name if user else 'Unknown'
                    flash(f'Added payment of ₹{amount} for {name}', 'success')
                    
                return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
            except (ValueError, TypeError) as e:
                flash(f'Invalid input: {str(e)}', 'error')
                return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
        elif action == 'edit':
            payment_index = int(request.form.get('payment_index'))
            participant_id = request.form.get('participant_id')
            description = request.form.get('description')
            amount = request.form.get('amount')
            date_str = request.form.get('date')
            expense_id = request.form.get('expense_id')
            
            try:
                amount = float(amount)
                if amount <= 0:
                    flash('Amount must be greater than zero', 'error')
                    return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
                date = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Edit general payment
                if not trip.edit_general_payment(payment_index, participant_id, amount, description, date, expense_id):
                    flash('Payment not found', 'error')
                    return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                    
                db.session.commit()
                
                # Recalculate all balances to ensure consistency
                balances = trip.recalculate_all_balances()
                
                flash('Payment updated successfully', 'success')
                return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
            except (ValueError, TypeError) as e:
                flash(f'Invalid input: {str(e)}', 'error')
                return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
        elif action == 'delete':
            payment_index = int(request.form.get('payment_index'))
            
            try:
                print(f"Attempting to delete payment at index: {payment_index}")
                # Debug the payment data
                all_payments = trip.get_general_payments()
                if 0 <= payment_index < len(all_payments):
                    print(f"Payment to delete: {all_payments[payment_index]}")
                else:
                    print(f"Invalid payment index: {payment_index}, total payments: {len(all_payments)}")
                
                # Delete general payment
                if not trip.delete_general_payment(payment_index):
                    flash('Invalid payment index', 'error')
                    return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                    
                db.session.commit()
                
                # Recalculate all balances to ensure consistency
                balances = trip.recalculate_all_balances()
                
                flash('Payment deleted successfully', 'success')
                return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error deleting payment: {str(e)}', 'error')
                return redirect(url_for('trips.manage_payments', trip_id=trip_id))
                
        else:
            flash('Invalid action', 'error')
            return redirect(url_for('trips.manage_payments', trip_id=trip_id))
    
    return render_template('trips/manage_payments.html',
                          trip=trip,
                          registered_participants=registered_participants,
                          unregistered_participants=unregistered_participants,
                          payments=formatted_payments,
                          expenses=expenses,
                          expense_summary=expense_summary_list,
                          total_expense_count=total_expense_count,
                          total_expense_amount=total_expense_amount,
                          payment_summary=payment_summary_list,
                          total_payment_count=total_payment_count,
                          total_payment_amount=total_payment_amount)

@trips_bp.route('/<int:trip_id>/settlements')
@login_required
def view_settlements(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is a participant or admin
    participants = trip.get_participants_list()
    if str(current_user.id) not in participants and current_user.id != trip.admin_id:
        flash('You do not have access to this trip', 'error')
        return redirect(url_for('trips.list_trips'))
    
    # Get user names for display
    participant_ids = trip.get_participants_list()
    if str(trip.admin_id) not in participant_ids:
        participant_ids.append(str(trip.admin_id))
    
    participants = User.query.filter(User.id.in_([int(pid) for pid in participant_ids])).all()
    user_map = {str(user.id): user.name for user in participants}
    
    # Calculate settlements
    settlements = trip.calculate_settlements()
    
    # Calculate individual balances
    balances = {}
    total_paid = {}
    total_share = {}
    
    # For each registered participant, calculate their balance, total paid and total share
    for participant_id in participant_ids:
        # Calculate balance using the existing method
        balance = trip.calculate_user_balance(participant_id)
        balances[participant_id] = balance
        
        # Calculate total paid (from expenses + advances + general payments)
        # Sum of expenses paid
        expense_paid = sum(expense.amount for expense in 
                          Expense.query.filter_by(trip_id=trip.id, payer_id=str(participant_id)))
        
        # Add general payments
        general_payments = trip.get_participant_general_payments(participant_id)
        
        # Add advance payments
        advances = trip.get_advances()
        advance_amount = advances.get(str(participant_id), 0)
        
        # Total paid is the sum of all three
        total_paid_amount = expense_paid + general_payments + advance_amount
        total_paid[participant_id] = total_paid_amount
        
        # Total share is what the participant owes (their share of all expenses)
        total_share_amount = 0
        for expense in trip.expenses:
            shares = expense.get_shares()
            if str(participant_id) in shares:
                total_share_amount += shares[str(participant_id)]
        
        total_share[participant_id] = total_share_amount
    
    # Also calculate for unregistered participants
    unregistered_participants = trip.get_unregistered_participants()
    for name in unregistered_participants:
        # Create a unique ID for the unregistered participant (using the stored lowercase name)
        unregistered_id = f'unregistered_{name}'
        
        # Calculate balance using the dedicated method
        balance = trip.calculate_unregistered_balance(unregistered_id)
        balances[unregistered_id] = balance
        
        # Add to user_map for display (using title case for display)
        display_name = trip.get_unregistered_participant_display_name(name)
        user_map[unregistered_id] = display_name
        
        # Calculate total paid (similar to registered participants)
        expense_paid = sum(expense.amount for expense in 
                          Expense.query.filter_by(trip_id=trip.id, payer_id=unregistered_id))
        general_payments = trip.get_participant_general_payments(unregistered_id)
        advances = trip.get_advances()
        advance_amount = advances.get(unregistered_id, 0)
        
        total_paid_amount = expense_paid + general_payments + advance_amount
        total_paid[unregistered_id] = total_paid_amount
        
        # Calculate total share (what they owe)
        total_share_amount = 0
        for expense in trip.expenses:
            shares = expense.get_shares()
            if unregistered_id in shares:
                total_share_amount += shares[unregistered_id]
        
        total_share[unregistered_id] = total_share_amount
    
    # Get all expenses for this trip, ordered by date (newest first)
    expenses = Expense.query.filter_by(trip_id=trip.id).order_by(Expense.date.desc()).all()
    
    return render_template('trips/settlements.html', 
                          trip=trip,
                          user_map=user_map,
                          settlements=settlements,
                          balances=balances,
                          total_paid=total_paid,
                          total_share=total_share,
                          expenses=expenses)

@trips_bp.route('/<int:trip_id>/export-pdf')
@login_required
def export_pdf(trip_id):
    """Export settlements as PDF"""
    from expense_tracker.backend.utils.pdf_generator import generate_settlement_pdf
    
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is a participant
    participants = trip.get_participants_list()
    if str(current_user.id) not in participants and current_user.id != trip.admin_id:
        flash('You do not have access to this trip', 'error')
        return redirect(url_for('trips.list_trips'))
    
    # Calculate settlements
    settlements = trip.calculate_settlements()
    
    # Calculate individual balances
    balances = {}
    for participant_id in participants:
        balances[participant_id] = trip.calculate_user_balance(int(participant_id))
    
    # Add admin if not already in participants
    if str(trip.admin_id) not in participants:
        balances[str(trip.admin_id)] = trip.calculate_user_balance(trip.admin_id)
    
    # Create a user map for easy lookup
    users = User.query.filter(User.id.in_([int(pid) for pid in participants] + [trip.admin_id])).all()
    user_map = {str(user.id): user.name for user in users}
    
    # Generate PDF
    pdf_content = generate_settlement_pdf(trip, settlements, balances, user_map)
    
    # Create a BytesIO object
    pdf_io = BytesIO(pdf_content)
    
    # Send the PDF as a downloadable file
    return send_file(
        pdf_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'settlement_report_{trip.name.replace(" ", "_")}.pdf'
    )

@trips_bp.route('/<int:trip_id>/sync-linked-participants', methods=['POST'])
@login_required
def sync_linked_participants(trip_id):
    """AJAX endpoint to synchronize linked participant data by checking expense table"""
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is the admin
    if trip.admin_id != current_user.id:
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action'}), 403
    
    try:
        # Get all linked unregistered participants for this trip
        linked_participants = trip.unregistered_participants_list.filter(UnregisteredParticipant.linked_user_id.isnot(None)).all()
        
        print(f"DEBUG: Found {len(linked_participants)} linked participants for trip {trip_id}")
        
        if not linked_participants:
            return jsonify({
                'success': True, 
                'message': 'No linked participants found for this trip',
                'sync_count': 0
            })
        
        sync_count = 0
        updated_expenses = []
        
        # For each linked participant, check the expense table for references
        for linked_participant in linked_participants:
            # The database stores names in lowercase, but expense records might use original case
            # So we need to check for both formats
            unregistered_ids_to_check = [
                f"unregistered_{linked_participant.name}",  # lowercase version (database format)
                f"unregistered_{linked_participant.name.title()}",  # Title case version
                f"unregistered_{linked_participant.name.upper()}",  # Uppercase version
                f"unregistered_{linked_participant.name.capitalize()}"  # Capitalized version
            ]
            
            user_id = str(linked_participant.linked_user_id)
            
            print(f"DEBUG: Checking for references to {linked_participant.name} (linked to user {user_id}) in expenses")
            print(f"DEBUG: Will check for these IDs: {unregistered_ids_to_check}")
            
            # Check all expenses in this trip for references to this unregistered participant
            for expense in trip.expenses:
                expense_updated = False
                
                # Check if this expense references the unregistered participant in any format
                for unregistered_id in unregistered_ids_to_check:
                    # 1. Check payer_id
                    if expense.payer_id == unregistered_id:
                        expense.payer_id = user_id
                        print(f"DEBUG: Updated payer_id in expense {expense.id} from {unregistered_id} to {user_id}")
                        expense_updated = True
                    
                    # 2. Check participants list
                    participants = expense.get_participants_list()
                    if unregistered_id in participants:
                        participants.remove(unregistered_id)
                        participants.append(user_id)
                        expense.set_participants_list(participants)
                        print(f"DEBUG: Updated participants list in expense {expense.id}")
                        expense_updated = True
                    
                    # 3. Check shares
                    shares = expense.get_shares()
                    if unregistered_id in shares:
                        amount = shares.pop(unregistered_id)
                        shares[user_id] = amount
                        expense.set_shares(shares)
                        print(f"DEBUG: Updated shares in expense {expense.id}")
                        expense_updated = True
                
                # If this expense was updated, add it to the session
                if expense_updated:
                    db.session.add(expense)
                    if expense.id not in updated_expenses:
                        updated_expenses.append(expense.id)
                    sync_count += 1
            
            # Check advances for this unregistered participant (check all formats)
            advances = trip.get_advances()
            advance_updated = False
            for unregistered_id in unregistered_ids_to_check:
                if unregistered_id in advances:
                    amount = advances.pop(unregistered_id)
                    advances[user_id] = amount
                    advance_updated = True
                    print(f"DEBUG: Updated advances for {unregistered_id} to {user_id}")
            
            if advance_updated:
                trip.set_advances(advances)
                sync_count += 1
            
            # Check general payments for this unregistered participant (check all formats)
            payments = trip.get_general_payments()
            payment_updated = False
            for payment in payments:
                for unregistered_id in unregistered_ids_to_check:
                    if payment.get('participant_id') == unregistered_id:
                        payment['participant_id'] = user_id
                        payment_updated = True
                        print(f"DEBUG: Updated general payment for {unregistered_id} to {user_id}")
            
            if payment_updated:
                trip.set_general_payments(payments)
                sync_count += 1
        
        # Commit all changes
        if sync_count > 0:
            db.session.commit()
            print(f"DEBUG: Committed {sync_count} updates to database")
        else:
            print(f"DEBUG: No updates needed")
        
        message = f'Successfully synchronized {sync_count} linked participant records across {len(updated_expenses)} expenses'
        if sync_count == 0:
            message += " (No updates were needed as all records were already synchronized)"
        
        return jsonify({
            'success': True, 
            'message': message,
            'sync_count': sync_count,
            'updated_expenses': len(updated_expenses)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error during synchronization: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error during synchronization: {str(e)}'}), 500

@trips_bp.route('/<int:trip_id>/sync-balances', methods=['POST'])
@login_required
def sync_trip_balances(trip_id):
    """Route to manually sync/refresh all trip balances"""
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is the admin
    if trip.admin_id != current_user.id:
        flash('You do not have permission to sync this trip', 'error')
        return redirect(url_for('trips.view_trip', trip_id=trip_id))
    
    try:
        # Recalculate all balances
        balances = trip.recalculate_all_balances()
        
        # Flash a success message
        flash(f'Successfully synchronized all balances for trip "{trip.name}"', 'success')
        
    except Exception as e:
        # Flash an error message if something goes wrong
        flash(f'Error synchronizing balances: {str(e)}', 'error')
    
    # Redirect back to the trip view
    return redirect(url_for('trips.view_trip', trip_id=trip_id))
