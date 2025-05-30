#!/usr/bin/env python3
"""
Database initialization script for Yumi Sugoi Discord Bot API

This script creates the database tables and performs initial setup.
"""

import os
import sys
from datetime import datetime

# Add the parent directory to the path to import the app
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def init_database():
    """Initialize the database with all required tables"""
    try:
        from api.app import app, db, sync_personas_to_db
        
        print("🔧 Initializing database...")
        
        with app.app_context():
            # Create all database tables
            db.create_all()
            print("✓ Database tables created successfully")
            
            # Sync built-in personas to database
            sync_personas_to_db()
            print("✓ Built-in personas synchronized")
            
            # Create initial admin user if needed (optional)
            # You can uncomment and modify this section
            # from api.app import User
            # admin_user = User.query.filter_by(discord_id='YOUR_DISCORD_ID').first()
            # if not admin_user:
            #     admin_user = User(
            #         discord_id='YOUR_DISCORD_ID',
            #         username='Admin',
            #         created_at=datetime.utcnow()
            #     )
            #     db.session.add(admin_user)
            #     db.session.commit()
            #     print("✓ Initial admin user created")
            
            print("🎉 Database initialization completed successfully!")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)

def reset_database():
    """Reset the database (WARNING: This will delete all data!)"""
    try:
        from api.app import app, db
        
        print("⚠️  RESETTING DATABASE - ALL DATA WILL BE LOST!")
        confirm = input("Are you sure? Type 'YES' to confirm: ")
        
        if confirm != 'YES':
            print("❌ Database reset cancelled")
            return
        
        with app.app_context():
            # Drop all tables
            db.drop_all()
            print("✓ All tables dropped")
            
            # Recreate tables
            init_database()
            
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        sys.exit(1)

def check_database():
    """Check database status and show table information"""
    try:
        from api.app import app, db, User, ServerConfig, PersonaMode, QAPair
        
        with app.app_context():
            print("📊 Database Status:")
            print("=" * 40)
            
            # Check if tables exist and show counts
            try:
                user_count = User.query.count()
                print(f"Users: {user_count}")
            except Exception as e:
                print(f"Users table: ERROR - {e}")
            
            try:
                server_count = ServerConfig.query.count()
                print(f"Server Configs: {server_count}")
            except Exception as e:
                print(f"Server Configs table: ERROR - {e}")
            
            try:
                persona_count = PersonaMode.query.count()
                custom_persona_count = PersonaMode.query.filter_by(is_custom=True).count()
                print(f"Personas: {persona_count} (Custom: {custom_persona_count})")
            except Exception as e:
                print(f"Personas table: ERROR - {e}")
            
            try:
                qa_count = QAPair.query.count()
                print(f"Q&A Pairs: {qa_count}")
            except Exception as e:
                print(f"Q&A Pairs table: ERROR - {e}")
                
            print("=" * 40)
            
    except Exception as e:
        print(f"❌ Database check failed: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database management for Yumi Bot API")
    parser.add_argument('action', choices=['init', 'reset', 'check'], 
                       help='Action to perform: init (create tables), reset (drop and recreate), check (show status)')
    
    args = parser.parse_args()
    
    if args.action == 'init':
        init_database()
    elif args.action == 'reset':
        reset_database()
    elif args.action == 'check':
        check_database()
