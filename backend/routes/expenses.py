from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from datetime import datetime
import json
from backend.models.expense import Expense
from backend.models.trip import Trip
from backend.models.user import User
from backend.models.unregistered_participant import UnregisteredParticipant
from backend.database import db
from backend.config import Config

bp = Blueprint('expenses', __name__, url_prefix='/trip')

@bp.route('/<int:trip_id>/expenses')
@login_required
def list_expenses(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is a participant or admin
    participants = trip.get_participants_list()
    if str(current_user.id) not in participants and current_user.id != trip.admin_id:
        flash('You do not have access to this trip', 'error')
        return redirect(url_for('trips.list_trips'))
    
    expenses = Expense.query.filter_by(trip_id=trip_id).order_by(Expense.date.desc()).all()
    
    # Get user names for display - improved version
    user_map = {str(user.id): user.name for user in User.query.all()}
    
    # Check for linked unregistered participants and map them to their registered user names
    # This needs to be done BEFORE adding unregistered participants to avoid overriding
    linked_unregistered_participants = trip.unregistered_participants_list.filter(UnregisteredParticipant.linked_user_id.isnot(None)).all()
    for linked_participant in linked_unregistered_participants:
        unregistered_id = f'unregistered_{linked_participant.name}'
        linked_user = User.query.get(linked_participant.linked_user_id)
        if linked_user:
            # Map the unregistered ID to the registered user's name
            user_map[unregistered_id] = linked_user.name
    
    # Also add unregistered participants to user_map (use display names)
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
            # Check if this unregistered participant is linked to a registered user
            linked_participant = trip.unregistered_participants_list.filter_by(name=name.strip().lower()).first()
            if linked_participant and linked_participant.linked_user_id:
                # Use the registered user's name instead
                linked_user = User.query.get(linked_participant.linked_user_id)
                if linked_user and payer_id not in user_map:
                    user_map[payer_id] = linked_user.name
            else:
                # Display name in title case
                display_name = trip.get_unregistered_participant_display_name(name)
                if payer_id not in user_map:
                    user_map[payer_id] = display_name
    
    return render_template('expenses/list.html', 
                          trip=trip, 
                          expenses=expenses, 
                          user_map=user_map)

@bp.route('/<int:trip_id>/expenses/add', methods=['GET', 'POST'])
@login_required
def add_expense(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if user is a participant or admin
    participants = trip.get_participants_list()
    if str(current_user.id) not in participants and current_user.id != trip.admin_id:
        flash('You do not have access to this trip', 'error')
        return redirect(url_for('trips.list_trips'))
    
    if request.method == 'POST':
        try:
            print("Form submitted, processing expense data...")
            description = request.form.get('description')
            amount = request.form.get('amount')
            date_str = request.form.get('date')
            split_method = request.form.get('split_method')
            selected_participants = request.form.getlist('participants')
            selected_unregistered = request.form.getlist('unregistered_participants')
            category = request.form.get('category')
            
            print(f"Form data: description={description}, amount={amount}, date={date_str}, split_method={split_method}, category={category}")
            print(f"Selected participants: {selected_participants}")
            print(f"Selected unregistered: {selected_unregistered}")
            
            # Validate input
            if not description or not amount or not date_str or not split_method:
                flash('All fields are required', 'error')
                return redirect(url_for('expenses.add_expense', trip_id=trip_id))
            
            # Validate that at least one participant is selected (registered or unregistered)
            if not selected_participants and not selected_unregistered:
                flash('Please select at least one participant for this expense', 'error')
                return redirect(url_for('expenses.add_expense', trip_id=trip_id))
            
            try:
                amount = float(amount)
                if amount <= 0:
                    flash('Amount must be greater than zero', 'error')
                    return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                    
                date = datetime.strptime(date_str, '%Y-%m-%d')
            except (ValueError, TypeError) as e:
                print(f"Error parsing amount or date: {e}")
                flash('Invalid amount or date format', 'error')
                return redirect(url_for('expenses.add_expense', trip_id=trip_id))
        
            # Get payer ID (default to current user if not specified)
            payer_id = request.form.get('payer_id', str(current_user.id))
            print(f"Payer ID: {payer_id}")
            
            # Handle 'group_everyone' special case for payer
            if payer_id == 'group_everyone':
                print("Group payment detected: This expense was paid by everyone collectively")
                # We'll store this special value directly
            
            # Create new expense
            print("Creating expense object...")
            expense = Expense(
                description=description,
                amount=amount,
                date=date,
                payer_id=payer_id,
                trip_id=trip_id,
                split_method=split_method,
                category=category
            )
            
            # Store both registered and unregistered participants
            all_participants = {
                'registered': selected_participants,
                'unregistered': selected_unregistered
            }
            print(f"All participants: {all_participants}")
        
            # Handle different split methods
            if split_method == 'equal':
                print("Using equal split method")
                # Make sure we pass lists, not None
                participants_list = selected_participants if selected_participants else []
                unregistered_list = selected_unregistered if selected_unregistered else []
                
                # Validate that we have at least one participant total
                if not participants_list and not unregistered_list:
                    flash('Please select at least one participant for this expense', 'error')
                    return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                    
                expense.update_split('equal', participants_list, unregistered_participants=unregistered_list)
            
            elif split_method == 'exact':
                print("Using exact split method")
                shares_data = {}
                total_shares = 0.0
                
                # Process registered participants' shares
                for participant_id in selected_participants:
                    share_amount = request.form.get(f'share_{participant_id}')
                    if share_amount:
                        try:
                            share_value = float(share_amount)
                            if share_value < 0:
                                flash(f'Share amount cannot be negative', 'error')
                                return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                            shares_data[participant_id] = share_value
                            total_shares += share_value
                            print(f"Participant {participant_id} share: {share_value}")
                        except ValueError:
                            flash(f'Invalid share amount format', 'error')
                            return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                
                # Handle unregistered participants shares
                unregistered_shares = {}
                for name in selected_unregistered:
                    share_amount = request.form.get(f'share_unregistered_{name}')
                    if share_amount:
                        try:
                            share_value = float(share_amount)
                            if share_value < 0:
                                flash(f'Share amount cannot be negative', 'error')
                                return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                            unregistered_shares[name] = share_value
                            total_shares += share_value
                            print(f"Unregistered participant {name} share: {share_value}")
                        except ValueError:
                            flash(f'Invalid share amount format for {name}', 'error')
                            return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                
                # Validate total shares match expense amount (with small rounding tolerance)
                if abs(total_shares - amount) > 0.01:
                    print(f"Total shares ({total_shares}) does not match expense amount ({amount})")
                    flash(f'Total shares ({total_shares}) must equal the expense amount ({amount})', 'error')
                    return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                
                # Include unregistered shares in the shares_data dictionary with special keys
                # Use lowercase name to match how unregistered participants are stored
                for name, share_value in unregistered_shares.items():
                    # Use lowercase name to match how unregistered participants are stored in the trip
                    shares_data[f"unregistered_{name.lower()}"] = share_value
                
                expense.update_split('exact', selected_participants, shares_data=shares_data, 
                                   unregistered_participants=selected_unregistered)
            
            elif split_method == 'itemized':
                print("Using itemized split method")
                # Process items from form
                items_data = []
                item_count = int(request.form.get('item_count', 0))
                print(f"Processing {item_count} items")
                
                # Validate we have at least one item
                if item_count <= 0:
                    flash('Please add at least one item for itemized split', 'error')
                    return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                
                total_items_price = 0.0
                
                for i in range(item_count):
                    item_name = request.form.get(f'item_name_{i}')
                    item_price = request.form.get(f'item_price_{i}')
                    item_participants = request.form.getlist(f'item_participants_{i}')
                    item_unregistered = request.form.getlist(f'item_unregistered_{i}')
                    
                    print(f"Item {i}: {item_name}, {item_price}, participants: {item_participants}, unregistered: {item_unregistered}")
                    
                    # Validate item data
                    if not item_name or not item_price:
                        flash(f'Item {i+1} is missing name or price', 'error')
                        return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                        
                    # Validate that item has at least one participant
                    if not item_participants and not item_unregistered:
                        flash(f'Item "{item_name}" must have at least one participant', 'error')
                        return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                    
                    try:
                        price_value = float(item_price)
                        if price_value <= 0:
                            flash(f'Item "{item_name}" price must be greater than zero', 'error')
                            return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                            
                        total_items_price += price_value
                        
                        items_data.append({
                            'name': item_name,
                            'price': price_value,
                            'participants': item_participants,
                            'unregistered': item_unregistered
                        })
                    except ValueError:
                        flash(f'Invalid price format for item "{item_name}"', 'error')
                        return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                
                # Validate total items price matches expense amount (with small rounding tolerance)
                if abs(total_items_price - amount) > 0.01:
                    print(f"Total items price ({total_items_price}) does not match expense amount ({amount})")
                    flash(f'Total items price ({total_items_price}) must equal the expense amount ({amount})', 'error')
                    return redirect(url_for('expenses.add_expense', trip_id=trip_id))
                
                expense.update_split('itemized', selected_participants, items_data=items_data, 
                                   unregistered_participants=selected_unregistered)
        
            print("Saving expense to database...")
            db.session.add(expense)
            
            # Detailed debugging before commit
            print("Expense object created with the following details:")
            print(f"Expense description: {expense.description}")
            print(f"Expense amount: {expense.amount}")
            print(f"Expense date: {expense.date}")
            print(f"Expense split method: {expense.split_method}")
            print(f"Expense participants: {expense.participants}")
            print(f"Expense shares: {expense.shares}")
            print(f"Expense items: {expense.items if expense.items else 'No items'}")
            
            # Commit changes to the database
            db.session.commit()
            
            # Recalculate all balances to ensure consistency
            balances = trip.recalculate_all_balances()
            
            # Detailed debugging after successful save
            print("Expense saved successfully!")
            print(f"Expense ID: {expense.id}")
            print(f"Expense in database: {Expense.query.get(expense.id) is not None}")
            print("Database changes committed successfully")
            
            flash('Expense added successfully', 'success')
            return redirect(url_for('expenses.list_expenses', trip_id=trip_id))
        except Exception as e:
            db.session.rollback()
            print(f"Error saving expense: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            print(f"Form data received: {request.form}")
            import traceback
            traceback.print_exc()
            flash(f'Error saving expense: {str(e)}', 'error')
            return redirect(url_for('expenses.add_expense', trip_id=trip_id))
    
    # Get all trip participants for the form
    all_participants = []
    for p_id in trip.get_participants_list():
        try:
            user = User.query.get(int(p_id))
            if user:
                all_participants.append(user)
        except ValueError:
            # Skip invalid IDs
            pass
            
    # Add admin if not already in the list
    if trip.admin_id not in [p.id for p in all_participants]:
        admin = User.query.get(trip.admin_id)
        if admin:
            all_participants.append(admin)
            
    # Get unregistered participants (use display names)
    unregistered_names = trip.get_unregistered_participants_display()
    
    return render_template('expenses/add.html', 
                          trip=trip, 
                          participants=all_participants,
                          unregistered_participants=unregistered_names,
                          split_methods=Config.SPLIT_METHODS)

@bp.route('/<int:trip_id>/expenses/<int:expense_id>')
@login_required
def view_expense(trip_id, expense_id):
    trip = Trip.query.get_or_404(trip_id)
    expense = Expense.query.get_or_404(expense_id)
    
    # Check if expense belongs to trip
    if expense.trip_id != trip_id:
        flash('Expense not found in this trip', 'error')
        return redirect(url_for('expenses.list_expenses', trip_id=trip_id))
    
    # Check if user is a participant or admin
    participants = trip.get_participants_list()
    if str(current_user.id) not in participants and current_user.id != trip.admin_id:
        flash('You do not have access to this expense', 'error')
        return redirect(url_for('trips.list_trips'))
    
    # Get user names for display
    user_map = {str(user.id): user.name for user in User.query.all()}
    
    # Handle payer information
    payer_info = {}
    payer_id_str = str(expense.payer_id)
    if payer_id_str == 'group_everyone':
        # Special case for group payment
        payer_info = {'id': 'group_everyone', 'name': 'Everyone (Group Payment)', 'type': 'group'}
    elif payer_id_str.startswith('unregistered_'):
        name = payer_id_str.replace('unregistered_', '')
        # Check if this unregistered participant is linked to a registered user
        linked_participant = trip.unregistered_participants_list.filter_by(name=name.strip().lower()).first()
        if linked_participant and linked_participant.linked_user_id:
            # Use the registered user's name instead
            linked_user = User.query.get(linked_participant.linked_user_id)
            if linked_user:
                payer_info = {'id': str(linked_user.id), 'name': linked_user.name, 'type': 'registered'}
            else:
                # Fallback to display name if user not found
                display_name = name.title()
                payer_info = {'id': payer_id_str, 'name': display_name, 'type': 'unregistered'}
        else:
            # Display name in title case
            display_name = name.title()
            payer_info = {'id': payer_id_str, 'name': display_name, 'type': 'unregistered'}
    else:
        try:
            payer = User.query.get(int(expense.payer_id))
            if payer:
                payer_info = {'id': str(payer.id), 'name': payer.name, 'type': 'registered'}
            else:
                # Unknown user ID
                payer_info = {'id': payer_id_str, 'name': 'Unknown', 'type': 'unknown'}
        except (ValueError, TypeError):
            payer_info = {'id': payer_id_str, 'name': 'Unknown', 'type': 'unknown'}
    
    # Get expense participants (both registered and unregistered)
    participants = []
    expense_participant_ids = expense.get_participants_list()
    unregistered_participants = expense.get_unregistered_participants() or []
    
    # Add registered participants
    if expense_participant_ids:
        for p_id in expense_participant_ids:
            try:
                user = User.query.get(int(p_id))
                if user:
                    participants.append({
                        'id': str(user.id),
                        'name': user.name,
                        'type': 'registered'
                    })
            except (ValueError, TypeError):
                # Skip invalid IDs
                pass
    
    # Add unregistered participants
    for name in unregistered_participants:
        # Check if this unregistered participant is linked to a registered user
        linked_participant = trip.unregistered_participants_list.filter_by(name=name.strip().lower()).first()
        if linked_participant and linked_participant.linked_user_id:
            # Use the registered user instead
            linked_user = User.query.get(linked_participant.linked_user_id)
            if linked_user:
                participants.append({
                    'id': str(linked_user.id),
                    'name': linked_user.name,
                    'type': 'registered'
                })
            else:
                # Fallback to unregistered if user not found
                participants.append({
                    'id': f'unregistered_{name.lower()}',  # Use lowercase to match storage format
                    'name': name,
                    'type': 'unregistered'
                })
        else:
            participants.append({
                'id': f'unregistered_{name.lower()}',  # Use lowercase to match storage format
                'name': name,
                'type': 'unregistered'
            })
    
    # Get expense shares
    shares = []
    try:
        shares_data = expense.get_shares()
        for user_id, amount in shares_data.items():
            # Check if it's a registered or unregistered participant
            if user_id.startswith('unregistered_'):
                # Handle unregistered participant
                name = user_id.replace('unregistered_', '')
                # Check if this unregistered participant is linked to a registered user
                linked_participant = trip.unregistered_participants_list.filter_by(name=name.strip().lower()).first()
                if linked_participant and linked_participant.linked_user_id:
                    # Use the registered user's name and ID instead
                    linked_user = User.query.get(linked_participant.linked_user_id)
                    if linked_user:
                        shares.append({
                            'user_id': str(linked_user.id),
                            'name': linked_user.name,
                            'type': 'registered',
                            'amount': amount
                        })
                    else:
                        # Fallback to unregistered if user not found
                        shares.append({
                            'user_id': user_id,
                            'name': name,
                            'type': 'unregistered',
                            'amount': amount
                        })
                else:
                    shares.append({
                        'user_id': user_id,
                        'name': name,
                        'type': 'unregistered',
                        'amount': amount
                    })
            else:
                # Handle registered participant
                shares.append({
                    'user_id': user_id,
                    'name': user_map.get(user_id, 'Unknown'),
                    'type': 'registered',
                    'amount': amount
                })
    except Exception as e:
        print(f"Error parsing shares: {e}")
    
    # Get expense items
    items = []
    try:
        items_data = expense.get_items()
        if isinstance(items_data, dict) and 'items' in items_data:
            items = items_data['items']
        elif isinstance(items_data, list):
            items = items_data
    except Exception as e:
        print(f"Error parsing items: {e}")
    
    # Get unregistered participants
    unregistered_participants = []
    try:
        items_data = expense.get_items()
        if isinstance(items_data, dict) and 'unregistered_participants' in items_data:
            unregistered_participants = items_data['unregistered_participants']
    except Exception as e:
        print(f"Error parsing unregistered participants: {e}")
    
    return render_template('expenses/view.html', 
                          trip=trip, 
                          expense=expense, 
                          participants=participants,
                          shares=shares,
                          items=items,
                          unregistered_participants=unregistered_participants,
                          user_map=user_map,
                          payer_info=payer_info)

@bp.route('/<int:trip_id>/expenses/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense(trip_id, expense_id):
    trip = Trip.query.get_or_404(trip_id)
    expense = Expense.query.get_or_404(expense_id)
    
    # Check if expense belongs to trip
    if expense.trip_id != trip_id:
        flash('Expense not found in this trip', 'error')
        return redirect(url_for('expenses.list_expenses', trip_id=trip_id))
    
    # Check if user is the payer or trip admin
    is_payer = False
    try:
        # Check if current user is the payer (handle both string and int comparisons)
        if str(expense.payer_id) == str(current_user.id):
            is_payer = True
    except:
        pass
        
    if not is_payer and trip.admin_id != current_user.id:
        flash('You do not have permission to edit this expense', 'error')
        return redirect(url_for('expenses.view_expense', trip_id=trip_id, expense_id=expense_id))
    
    if request.method == 'POST':
        description = request.form.get('description')
        amount = request.form.get('amount')
        date_str = request.form.get('date')
        split_method = request.form.get('split_method')
        selected_participants = request.form.getlist('participants')
        selected_unregistered = request.form.getlist('unregistered_participants')
        category = request.form.get('category')
        
        # Validate input
        if not description or not amount or not date_str or not split_method:
            flash('All fields are required', 'error')
            return redirect(url_for('expenses.edit_expense', trip_id=trip_id, expense_id=expense_id))
        
        try:
            amount = float(amount)
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            flash('Invalid amount or date format', 'error')
            return redirect(url_for('expenses.edit_expense', trip_id=trip_id, expense_id=expense_id))
        
        # Get payer ID
        payer_id = request.form.get('payer_id')
        
        # Update expense
        expense.description = description
        expense.amount = amount
        expense.date = date
        expense.split_method = split_method
        expense.payer_id = payer_id
        expense.category = category
        
        # Handle different split methods
        if split_method == 'equal':
            expense.update_split('equal', selected_participants, unregistered_participants=selected_unregistered)
        
        elif split_method == 'exact':
            shares_data = {}
            for participant_id in selected_participants:
                share_amount = request.form.get(f'share_{participant_id}')
                if share_amount:
                    shares_data[participant_id] = float(share_amount)
            
            # Also process unregistered participants' shares if any
            for name in selected_unregistered:
                share_amount = request.form.get(f'share_unregistered_{name}')
                if share_amount:
                    # Use lowercase name to match how unregistered participants are stored
                    shares_data[f'unregistered_{name.lower()}'] = float(share_amount)
            
            expense.update_split('exact', selected_participants, shares_data=shares_data, unregistered_participants=selected_unregistered)
        
        elif split_method == 'itemized':
            # Process items from form
            items_data = []
            item_count = int(request.form.get('item_count', 0))
            
            for i in range(item_count):
                item_name = request.form.get(f'item_name_{i}')
                item_price = request.form.get(f'item_price_{i}')
                item_participants = request.form.getlist(f'item_participants_{i}')
                item_unregistered = request.form.getlist(f'item_unregistered_{i}')
                
                if item_name and item_price and (item_participants or item_unregistered):
                    items_data.append({
                        'name': item_name,
                        'price': float(item_price),
                        'participants': item_participants,
                        'unregistered': item_unregistered
                    })
            
            expense.update_split('itemized', selected_participants, items_data=items_data, unregistered_participants=selected_unregistered)
        
        db.session.commit()
        
        # Recalculate all balances to ensure consistency
        balances = trip.recalculate_all_balances()
        
        flash('Expense updated successfully', 'success')
        return redirect(url_for('expenses.view_expense', trip_id=trip_id, expense_id=expense_id))
    
    # Get all trip participants for the form
    all_participants = []
    for p_id in trip.get_participants_list():
        try:
            user = User.query.get(int(p_id))
            if user:
                all_participants.append(user)
        except (ValueError, TypeError):
            # Skip invalid IDs
            pass
    
    # Add admin if not already in the list
    if trip.admin_id not in [p.id for p in all_participants]:
        admin = User.query.get(trip.admin_id)
        if admin:
            all_participants.append(admin)
    
    # Get expense's current participants
    expense_participant_ids = expense.get_participants_list()
    expense_participant_ids = [str(pid) for pid in expense_participant_ids]  # Convert to strings for comparison
    
    # Get all unregistered participants from the trip (not just those in the expense)
    unregistered_participants = trip.get_unregistered_participants_display()
    
    return render_template('expenses/edit.html', 
                          trip=trip, 
                          expense=expense,
                          participants=all_participants,
                          expense_participant_ids=expense_participant_ids,
                          unregistered_participants=unregistered_participants,
                          split_methods=Config.SPLIT_METHODS)


@bp.route('/<int:trip_id>/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(trip_id, expense_id):
    trip = Trip.query.get_or_404(trip_id)
    expense = Expense.query.get_or_404(expense_id)
    
    # Check if expense belongs to trip
    if expense.trip_id != trip_id:
        flash('Expense not found in this trip', 'error')
        return redirect(url_for('expenses.list_expenses', trip_id=trip_id))
    
    # Check if user is the payer or trip admin
    is_payer = False
    try:
        # Check if current user is the payer (handle both string and int comparisons)
        if str(expense.payer_id) == str(current_user.id):
            is_payer = True
    except:
        pass
        
    if not is_payer and trip.admin_id != current_user.id:
        flash('You do not have permission to delete this expense', 'error')
        return redirect(url_for('expenses.view_expense', trip_id=trip_id, expense_id=expense_id))
    
    # Delete the expense
    db.session.delete(expense)
    db.session.commit()
    
    # Recalculate all balances to ensure consistency
    balances = trip.recalculate_all_balances()
    
    flash('Expense deleted successfully', 'success')
    return redirect(url_for('expenses.list_expenses', trip_id=trip_id))
