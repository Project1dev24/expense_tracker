"""
Migration script to add the advances column to the trip table
"""
import sqlite3
import os
from pathlib import Path

def run_migration():
    # Get the database path
    base_dir = Path(__file__).resolve().parent.parent.parent
    db_path = os.path.join(base_dir, 'instance', 'app.db')
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
        
        if 'advances_json' not in column_names:
            # Add the advances_json column to the trip table
            cursor.execute("ALTER TABLE trip ADD COLUMN advances_json TEXT DEFAULT '{}'")
            print("Added 'advances_json' column to trip table")
        else:
            print("Column 'advances_json' already exists in trip table")
        
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
