# Expense Tracker Backend

This is the backend component of the Expense Tracker application, a Flask-based web application for managing trip expenses among multiple participants, including both registered users and unregistered participants.

## Project Overview

The Expense Tracker allows users to:
- Create and manage trips with multiple participants
- Track expenses during trips with various splitting methods (equal, exact, itemized)
- Handle both registered users and unregistered participants
- Link unregistered participants to registered users
- Calculate settlements between participants
- Generate PDF reports of trip settlements
- Manage advance payments and general payments during trips

## Technology Stack

- **Framework**: Flask 2.0.1
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: Flask-Login
- **Frontend**: HTML, CSS, JavaScript with Jinja2 templating
- **PDF Generation**: ReportLab
- **Environment Management**: python-dotenv

## Project Structure

```
backend/
├── app.py              # Application entry point
├── app_factory.py      # Flask application factory
├── app_context.py      # Application initialization and configuration
├── config.py           # Configuration settings
├── database.py         # Database setup
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (not in version control)
├── app.db             # SQLite database file
│
├── models/            # Database models
│   ├── user.py
│   ├── trip.py
│   ├── expense.py
│   └── unregistered_participant.py
│
├── routes/            # Application routes/controllers
│   ├── auth.py        # Authentication routes
│   ├── main.py        # Main application routes
│   ├── trips.py       # Trip management routes
│   └── expenses.py    # Expense tracking routes
│
├── templates/         # HTML templates
│   ├── auth/          # Authentication templates
│   ├── main/          # Main page templates
│   ├── trips/         # Trip management templates
│   ├── expenses/      # Expense tracking templates
│   ├── pdf/           # PDF report templates
│   └── base.html      # Base template
│
├── static/            # Static assets
│   ├── css/           # Stylesheets
│   └── js/            # JavaScript files
│
├── utils/             # Utility functions
│   └── pdf_generator.py  # PDF report generation
│
└── migrations/        # Database migration scripts
```

## Key Features

### User Management
- User registration and authentication
- Profile management
- Password reset functionality
- Admin user support

### Trip Management
- Create and manage trips with start/end dates
- Add/remove participants (both registered and unregistered)
- Administrative controls for trip creators

### Expense Tracking
- Record expenses with descriptions, amounts, and dates
- Support for multiple currencies (default: INR)
- Three splitting methods:
  - **Equal**: Split evenly among all participants
  - **Exact**: Specify exact amounts for each participant
  - **Itemized**: Split by items consumed by each participant

### Participant Management
- Support for both registered users and unregistered participants
- Link unregistered participants to registered users
- Maintain data consistency when linking participants

### Financial Management
- Track advance payments
- Record general payments during trips
- Automatic balance calculation
- Settlement calculation between participants

### Reporting
- View detailed expense breakdowns
- Generate PDF settlement reports
- Visualize trip financials

## Database Schema

### User
- `id`: Primary key
- `email`: Unique email address
- `name`: User's name
- `password_hash`: Hashed password
- `created_at`: Account creation timestamp
- `last_seen`: Last login timestamp
- `is_admin`: Admin status flag
- `linked_unregistered_names`: JSON array of linked unregistered participant names

### Trip
- `id`: Primary key
- `name`: Trip name
- `description`: Trip description
- `start_date`: Trip start date
- `end_date`: Trip end date
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `admin_id`: Foreign key to User (trip creator)
- `participants`: JSON array of registered participant IDs
- `advances_json`: JSON object tracking advance payments
- `general_payments_json`: JSON array of general payments

### Expense
- `id`: Primary key
- `description`: Expense description
- `amount`: Expense amount
- `currency`: Currency code (default: INR)
- `category`: Expense category
- `date`: Expense date
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `split_method`: Splitting method ('equal', 'exact', 'itemized')
- `payer_id`: ID of payer (user ID or 'unregistered_name')
- `trip_id`: Foreign key to Trip
- `participants`: JSON array of participant IDs
- `shares`: JSON object mapping participants to their share amounts
- `items`: JSON array for itemized expenses

### UnregisteredParticipant
- `id`: Primary key
- `name`: Participant name (stored in lowercase)
- `trip_id`: Foreign key to Trip
- `linked_user_id`: Foreign key to User (when linked)
- `created_at`: Creation timestamp

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/logout` - User logout
- `GET /auth/profile` - User profile
- `POST /auth/profile/edit` - Edit profile
- `POST /auth/profile/change-password` - Change password
- `POST /auth/reset-password` - Reset password

### Main
- `GET /` - Application dashboard
- `GET /dashboard` - User dashboard

### Trips
- `GET /trips/` - List user's trips
- `POST /trips/add` - Create new trip
- `GET /trips/<trip_id>` - View trip details
- `POST /trips/<trip_id>/edit` - Edit trip
- `POST /trips/<trip_id>/delete` - Delete trip
- `POST /trips/<trip_id>/participants/add` - Add participant
- `POST /trips/<trip_id>/participants/remove` - Remove participant
- `GET /trips/<trip_id>/manage-participants` - Manage participants
- `POST /trips/<trip_id>/link-participant` - Link unregistered participant
- `GET /trips/<trip_id>/settlements` - View trip settlements
- `GET /trips/<trip_id>/pdf-report` - Generate PDF report

### Expenses
- `GET /trip/<trip_id>/expenses` - List trip expenses
- `POST /trip/<trip_id>/expenses/add` - Add expense
- `POST /trip/<trip_id>/expenses/<expense_id>/edit` - Edit expense
- `POST /trip/<trip_id>/expenses/<expense_id>/delete` - Delete expense

## Setup and Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables** (optional):
   Create a `.env` file with:
   ```
   SECRET_KEY=your-secret-key
   DATABASE_URL=sqlite:///app.db
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the application**:
   Open your browser to `http://localhost:5003`

## Development

### Running Tests
The application includes various test scripts for different functionalities:
- `test_*.py` files for unit testing
- Manual test scripts for specific features

### Database Migrations
Migration scripts are located in the [migrations/](migrations/) directory for updating the database schema.

### Debugging Tools
Several debugging scripts are available:
- `debug_*.py` files for troubleshooting specific issues
- `check_*.py` files for verifying data consistency

## Key Implementation Details

### Participant Linking
The system supports linking unregistered participants to registered users, automatically updating all related expense data to maintain consistency.

### Financial Consistency
Whenever financial data (expenses, advances, or general payments) is added, edited, or deleted, the system automatically recalculates all participant balances to ensure consistency.

### Data Migration
The system includes migration scripts to update the database schema and handle data consistency when new features are added.

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request

## License
This project is proprietary and intended for personal use.