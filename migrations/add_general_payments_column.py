"""
Migration script to add the general_payments_json column to the trip table
"""
import sqlite3
import os
from pathlib import Path

def run_migration():
    # Get the database path
    base_dir = Path(__file__).resolve().parent.parent.parent
    # First try the app.db in the root directory
    db_path = os.path.join(base_dir, 'app.db')
    
    # If not found, check in the instance folder
    if not os.path.exists(db_path):
        db_path = os.path.join(base_dir, 'instance', 'app.db')
        
    # If still not found, check in the expense_tracker directory
    if not os.path.exists(db_path):
        db_path = os.path.join(base_dir, 'expense_tracker', 'app.db')
        
    # If still not found, check for expense_tracker.db in the root
    if not os.path.exists(db_path):
        db_path = os.path.join(base_dir, 'expense_tracker.db')
        
    if not os.path.exists(db_path):
        print(f"Error: Could not find the database file. Tried multiple locations.")
        return
        
    print(f"Using database at: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # First, check if the trip table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trip'")
        if not cursor.fetchone():
            print("Error: 'trip' table does not exist")
            return
            
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(trip)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'general_payments_json' not in column_names:
            # Add the general_payments_json column to the trip table
            cursor.execute("ALTER TABLE trip ADD COLUMN general_payments_json TEXT DEFAULT '[]'")
            print("Added 'general_payments_json' column to trip table")
        else:
            print("Column 'general_payments_json' already exists in trip table")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
