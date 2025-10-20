from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import current_user, login_required
from datetime import date, timedelta, datetime
from backend.models.trip import Trip
from backend.models.expense import Expense
from backend.models.user import User
from backend.database import db

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("main/index.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    # Get all trips for the user and sort by start date (most recent first)
    trips = sorted(current_user.get_trips(), key=lambda t: t.start_date, reverse=True)
    trip_ids = [trip.id for trip in trips]

    # Get recent trips (for display in the trips section) - sorted by start date (most recent first)
    recent_trips = sorted(trips, key=lambda t: t.start_date, reverse=True)[:5]

    # Get older trips (completed trips that are more than 30 days old)
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    older_trips = []
    for trip in trips:
        if trip.end_date.date() < today and trip.end_date.date() < thirty_days_ago:
            older_trips.append(trip)
    # Sort older trips by end date (oldest first)
    older_trips = sorted(older_trips, key=lambda t: t.end_date, reverse=True)

    # Get total number of trips
    total_trips = len(trips)

    # Get total balance across all trips
    total_balance = current_user.get_total_balance()

    # Calculate total amount of user's share of expenses
    total_spent = 0
    if trip_ids:
        all_user_expenses = Expense.query.filter(Expense.trip_id.in_(trip_ids)).all()
        for expense in all_user_expenses:
            shares = expense.get_shares()
            user_share = shares.get(str(current_user.id))
            if user_share:
                total_spent += user_share

    # Get the 10 most recent expenses paid by the user across all their trips
    paid_expenses_query = []
    if trip_ids:
        paid_expenses_query = (
            Expense.query.filter(
                Expense.trip_id.in_(trip_ids), Expense.payer_id == current_user.id
            )
            .order_by(Expense.date.desc())
            .limit(10)
            .all()
        )

    # Create a dictionary to quickly map trip_id to trip object
    trips_by_id = {trip.id: trip for trip in trips}

    user_paid_expenses = []
    for expense in paid_expenses_query:
        trip_for_expense = trips_by_id.get(expense.trip_id)
        if trip_for_expense:
            user_paid_expenses.append(
                {
                    "expense": expense,
                    "trip": trip_for_expense,
                    "payer_name": current_user.name,
                }
            )

    # Prepare month filter data from actual expenses
    months_for_filter = []
    if trip_ids:
        distinct_months = (
            db.session.query(db.func.strftime("%Y-%m", Expense.date))
            .filter(Expense.trip_id.in_(trip_ids))
            .distinct()
            .order_by(db.func.strftime("%Y-%m", Expense.date).desc())
            .all()
        )

        for (month_str,) in distinct_months:
            year, month = map(int, month_str.split("-"))
            month_name = datetime(year, month, 1).strftime("%B %Y")
            months_for_filter.append({"value": month_str, "text": month_name})

        # Add current month if not in the list
        current_month_str = datetime.now().strftime("%Y-%m")
        if not any(m["value"] == current_month_str for m in months_for_filter):
            current_month_name = datetime.now().strftime("%B %Y")
            months_for_filter.insert(
                0, {"value": current_month_str, "text": current_month_name}
            )

    # --- Chart Data Preparation ---
    category_labels = []
    category_values = []
    line_chart_labels = []
    line_chart_values = []

    if trip_ids:
        base_query = Expense.query.filter(Expense.trip_id.in_(trip_ids))

        # 1. Spending by Category (Pie Chart) - based on user's share
        expenses = base_query.all()
        category_spending = {}
        for expense in expenses:
            shares = expense.get_shares()
            user_share = shares.get(str(current_user.id))

            if user_share:
                category = expense.category or 'Uncategorized'
                if category not in category_spending:
                    category_spending[category] = 0
                category_spending[category] += user_share

        # Sort categories by spending
        sorted_categories = sorted(category_spending.items(), key=lambda item: item[1], reverse=True)

        category_labels = [item[0] for item in sorted_categories]
        category_values = [float(item[1]) for item in sorted_categories]

        # 2. Spending Over Time (Line Chart for last 12 months) - based on user's share
        spending_data_map = {}
        date_format_str = '%Y-%m'
        twelve_months_ago = (datetime.utcnow().replace(day=1) - timedelta(days=365)).replace(day=1)

        for expense in expenses:
            if expense.date >= twelve_months_ago:
                shares = expense.get_shares()
                user_share = shares.get(str(current_user.id))
                if user_share:
                    month_key = expense.date.strftime(date_format_str)
                    if month_key not in spending_data_map:
                        spending_data_map[month_key] = 0
                    spending_data_map[month_key] += user_share

        line_chart_labels = [((datetime.utcnow() - timedelta(days=30*i)).strftime(date_format_str)) for i in range(11, -1, -1)]
        line_chart_values = [spending_data_map.get(month_label, 0) for month_label in line_chart_labels]
    else:
        # Provide default data for charts when no trips exist
        category_labels = ['Food', 'Transportation', 'Accommodation', 'Activities', 'Other']
        category_values = [0, 0, 0, 0, 0]
        
        # Generate last 12 months for line chart
        line_chart_labels = [((datetime.utcnow() - timedelta(days=30*i)).strftime('%Y-%m')) for i in range(11, -1, -1)]
        line_chart_values = [0 for _ in range(12)]

    return render_template('main/dashboard.html',
                            trips=trips,
                            recent_trips=recent_trips,
                            recent_expenses=user_paid_expenses,
                            total_balance=total_balance,
                            total_trips=total_trips,
                            total_spent=total_spent,
                            today=today,
                            older_trips=older_trips,
                            months_for_filter=months_for_filter,
                            category_labels=category_labels,
                            category_values=category_values,
                            line_chart_labels=line_chart_labels,
                            line_chart_values=line_chart_values)


@bp.route("/api/months_for_trip/<int:trip_id>")
@login_required
def api_months_for_trip(trip_id):
    user_trips = current_user.get_trips()
    trip_ids = [trip.id for trip in user_trips]

    if trip_id not in trip_ids:
        return jsonify({"error": "Unauthorized"}), 403

    distinct_months = (
        db.session.query(db.func.strftime("%Y-%m", Expense.date))
        .filter(Expense.trip_id == trip_id)
        .distinct()
        .order_by(db.func.strftime("%Y-%m", Expense.date).desc())
        .all()
    )

    months = []
    for (month_str,) in distinct_months:
        year, month = map(int, month_str.split("-"))
        month_name = datetime(year, month, 1).strftime("%B %Y")
        months.append({"value": month_str, "text": month_name})

    return jsonify(months)


@bp.route("/api/all_months")
@login_required
def api_all_months():
    user_trips = current_user.get_trips()
    trip_ids = [trip.id for trip in user_trips]

    if not trip_ids:
        return jsonify([])

    distinct_months = (
        db.session.query(db.func.strftime("%Y-%m", Expense.date))
        .filter(Expense.trip_id.in_(trip_ids))
        .distinct()
        .order_by(db.func.strftime("%Y-%m", Expense.date).desc())
        .all()
    )

    months = []
    for (month_str,) in distinct_months:
        year, month = map(int, month_str.split("-"))
        month_name = datetime(year, month, 1).strftime("%B %Y")
        months.append({"value": month_str, "text": month_name})

    return jsonify(months)


# Add the missing spending_history endpoint
@bp.route("/api/spending_history")
@login_required
def api_spending_history():
    month = request.args.get("month")  # YYYY-MM format

    # Base query for user's expenses
    user_trips = current_user.get_trips()
    trip_ids = [trip.id for trip in user_trips]

    if not trip_ids:
        return jsonify({"line_chart_labels": [], "line_chart_values": []})

    # --- Main Query for all expenses to be filtered ---
    base_query = Expense.query.filter(Expense.trip_id.in_(trip_ids))

    # Initialize date variables
    start_date = None
    end_date = None

    if month:
        try:
            year, month_num = map(int, month.split("-"))
            start_date = datetime(year, month_num, 1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(
                days=1
            )
            base_query = base_query.filter(
                Expense.date >= start_date, Expense.date <= end_date
            )
        except ValueError:
            return jsonify({"error": "Invalid month format. Use YYYY-MM"}), 400

    # Spending Over Time (Line Chart) - based on user's share
    expenses = base_query.all()
    spending_data_map = {}

    if month and start_date and end_date:  # If month is selected, show weekly spending
        # Group expenses by week
        weekly_spending = {}
        
        for expense in expenses:
            shares = expense.get_shares()
            user_share = shares.get(str(current_user.id))
            if user_share:
                # Calculate week number (1-5) within the month
                day_of_month = expense.date.day
                week_number = ((day_of_month - 1) // 7) + 1
                
                # Create a label for the week (e.g., "Sep 1-7")
                week_start = ((week_number - 1) * 7) + 1
                week_end = min(week_number * 7, end_date.day)
                
                # Format the label with actual dates
                week_label = f"{start_date.strftime('%b')} {week_start}-{week_end}"
                
                if week_label not in weekly_spending:
                    weekly_spending[week_label] = 0
                weekly_spending[week_label] += user_share

        # Create sorted labels and values
        line_chart_labels = []
        line_chart_values = []
        
        # Create week labels in order (1st through 5th week)
        week_labels = []
        for week_num in range(1, 6):  # Weeks 1-5
            week_start = ((week_num - 1) * 7) + 1
            if week_start <= end_date.day:
                week_end = min(week_num * 7, end_date.day)
                week_label = f"{start_date.strftime('%b')} {week_start}-{week_end}"
                week_labels.append(week_label)
        
        # Now populate the chart data in week order
        for week_label in week_labels:
            line_chart_labels.append(week_label)
            line_chart_values.append(weekly_spending.get(week_label, 0))

    else:  # If no filters, show monthly spending for last 12 months across all trips
        date_format_str = "%Y-%m"
        for expense in expenses:
            shares = expense.get_shares()
            user_share = shares.get(str(current_user.id))
            if user_share:
                month_key = expense.date.strftime(date_format_str)
                if month_key not in spending_data_map:
                    spending_data_map[month_key] = 0
                spending_data_map[month_key] += user_share

        line_chart_labels = [
            ((datetime.utcnow() - timedelta(days=30 * i)).strftime(date_format_str))
            for i in range(11, -1, -1)
        ]
        line_chart_values = [
            spending_data_map.get(month_label, 0) for month_label in line_chart_labels
        ]

    return jsonify(
        {"line_chart_labels": line_chart_labels, "line_chart_values": line_chart_values}
    )


@bp.route("/api/dashboard_data")
@login_required
def api_dashboard_data():
    trip_id = request.args.get("trip_id", type=int)
    month = request.args.get("month")  # YYYY-MM format

    # Base query for user's expenses
    user_trips = current_user.get_trips()
    trip_ids = [trip.id for trip in user_trips]

    if not trip_ids:
        return jsonify({})

    # --- Main Query for all expenses to be filtered ---
    base_query = Expense.query.filter(Expense.trip_id.in_(trip_ids))

    if trip_id:
        if trip_id in trip_ids:  # Security check
            base_query = base_query.filter(Expense.trip_id == trip_id)
        else:
            return jsonify({"error": "Invalid trip_id"}), 403

    if month:
        try:
            year, month_num = map(int, month.split("-"))
            start_date = datetime(year, month_num, 1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(
                days=1
            )
            base_query = base_query.filter(
                Expense.date >= start_date, Expense.date <= end_date
            )
        except ValueError:
            return jsonify({"error": "Invalid month format. Use YYYY-MM"}), 400

    # 1. Spending by Category (Pie Chart) - based on user's share
    expenses = base_query.all()
    category_spending = {}
    for expense in expenses:
        shares = expense.get_shares()
        user_share = shares.get(str(current_user.id))

        if user_share:
            category = expense.category or "Uncategorized"
            if category not in category_spending:
                category_spending[category] = 0
            category_spending[category] += user_share

    # Sort categories by spending
    sorted_categories = sorted(
        category_spending.items(), key=lambda item: item[1], reverse=True
    )

    category_labels = [item[0] for item in sorted_categories]
    category_values = [float(item[1]) for item in sorted_categories]

    # 2. Spending Over Time (Line Chart) - based on user's share
    spending_data_map = {}
    if trip_id or month:  # If any filter is applied, show daily spending
        date_format_str = "%Y-%m-%d"
        for expense in expenses:
            shares = expense.get_shares()
            user_share = shares.get(str(current_user.id))
            if user_share:
                day = expense.date.strftime(date_format_str)
                if day not in spending_data_map:
                    spending_data_map[day] = 0
                spending_data_map[day] += user_share

        if spending_data_map:
            min_date_str = min(spending_data_map.keys())
            max_date_str = max(spending_data_map.keys())
            min_date = datetime.strptime(min_date_str, "%Y-%m-%d").date()
            max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()

            # Initialize date variables
            start_date = None
            end_date = None

            if month:
                try:
                    year, month_num = map(int, month.split("-"))
                    start_date = datetime(year, month_num, 1)
                    end_date = (start_date + timedelta(days=32)).replace(
                        day=1
                    ) - timedelta(days=1)
                except ValueError:
                    pass

            if start_date and end_date:
                # If month is selected, use the month's start and end for the x-axis
                line_chart_labels = [
                    (start_date.date() + timedelta(days=i)).strftime(date_format_str)
                    for i in range((end_date.date() - start_date.date()).days + 1)
                ]
            else:
                # Otherwise, use the range of expenses in the trip
                line_chart_labels = [
                    (min_date + timedelta(days=i)).strftime(date_format_str)
                    for i in range((max_date - min_date).days + 1)
                ]

            line_chart_values = [
                spending_data_map.get(day, 0) for day in line_chart_labels
            ]
        else:
            line_chart_labels = []
            line_chart_values = []

    else:  # If no filters, show monthly spending for last 12 months across all trips
        date_format_str = "%Y-%m"
        for expense in expenses:
            shares = expense.get_shares()
            user_share = shares.get(str(current_user.id))
            if user_share:
                month_key = expense.date.strftime(date_format_str)
                if month_key not in spending_data_map:
                    spending_data_map[month_key] = 0
                spending_data_map[month_key] += user_share

        line_chart_labels = [
            ((datetime.utcnow() - timedelta(days=30 * i)).strftime(date_format_str))
            for i in range(11, -1, -1)
        ]
        line_chart_values = [
            spending_data_map.get(month_label, 0) for month_label in line_chart_labels
        ]

    return jsonify(
        {
            "category_labels": category_labels,
            "category_values": category_values,
            "line_chart_labels": line_chart_labels,
            "line_chart_values": line_chart_values,
        }
    )


@bp.route("/api/sync", methods=["POST"])
@login_required
def api_sync():
    """API endpoint to manually sync/refresh all user data and balances"""
    try:
        # Get all trips for the user
        user_trips = current_user.get_trips()
        
        # Recalculate balances for each trip
        sync_count = 0
        for trip in user_trips:
            try:
                # Recalculate all balances for this trip
                balances = trip.recalculate_all_balances()
                sync_count += 1
            except Exception as e:
                print(f"Error syncing trip {trip.id}: {str(e)}")
                # Continue with other trips even if one fails
        
        # Update user's last seen timestamp
        current_user.update_last_seen()
        
        return jsonify({
            "success": True, 
            "message": f"Successfully synchronized {sync_count} trips", 
            "sync_count": sync_count
        })
        
    except Exception as e:
        print(f"Error during synchronization: {str(e)}")
        return jsonify({
            "success": False, 
            "message": f"Error during synchronization: {str(e)}"
        }), 500
