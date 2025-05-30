#!/usr/bin/env python3
"""
Database migration and management script for Yumi Sugoi Discord Bot API

This script handles database initialization, migrations, and management tasks.
"""

import os
import sys
import logging
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade, init, migrate as flask_migrate

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create Flask app for migrations"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', 
        'sqlite:///yumi_bot.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    return app

def init_db():
    """Initialize the database and migration repository"""
    try:
        app = create_app()
        
        # Import models to ensure they're registered
        from api.app import db, User, ServerConfig, PersonaMode, QAPair
        
        with app.app_context():
            db.init_app(app)
            migrate = Migrate(app, db)
            
            # Initialize migration repository if it doesn't exist
            migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
            if not os.path.exists(migrations_dir):
                logger.info("Initializing migration repository...")
                init()
                logger.info("✓ Migration repository initialized")
            
            # Create all tables
            logger.info("Creating database tables...")
            db.create_all()
            logger.info("✓ Database tables created")
            
            # Create initial migration if needed
            try:
                logger.info("Creating initial migration...")
                flask_migrate(message='Initial migration')
                logger.info("✓ Initial migration created")
            except Exception as e:
                logger.warning(f"Migration creation skipped: {e}")
            
            # Apply migrations
            logger.info("Applying migrations...")
            upgrade()
            logger.info("✓ Migrations applied")
            
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def upgrade_db():
    """Upgrade database to latest migration"""
    try:
        app = create_app()
        
        with app.app_context():
            from api.app import db
            db.init_app(app)
            migrate = Migrate(app, db)
            
            logger.info("Upgrading database...")
            upgrade()
            logger.info("✓ Database upgraded successfully")
            
        return True
        
    except Exception as e:
        logger.error(f"Database upgrade failed: {e}")
        return False

def create_migration(message):
    """Create a new migration"""
    try:
        app = create_app()
        
        with app.app_context():
            from api.app import db
            db.init_app(app)
            migrate = Migrate(app, db)
            
            logger.info(f"Creating migration: {message}")
            flask_migrate(message=message)
            logger.info("✓ Migration created successfully")
            
        return True
        
    except Exception as e:
        logger.error(f"Migration creation failed: {e}")
        return False

def seed_data():
    """Seed the database with initial data"""
    try:
        app = create_app()
        
        with app.app_context():
            from api.app import db, User, ServerConfig, PersonaMode
            db.init_app(app)
            
            logger.info("Seeding database with initial data...")
            
            # Create default persona modes
            default_personas = [
                {'name': 'normal', 'description': 'Default balanced personality', 'is_default': True},
                {'name': 'kawaii', 'description': 'Cute and playful personality', 'is_default': False},
                {'name': 'serious', 'description': 'Professional and formal personality', 'is_default': False},
                {'name': 'playful', 'description': 'Fun and energetic personality', 'is_default': False},
                {'name': 'helpful', 'description': 'Focused on being helpful and informative', 'is_default': False},
            ]
            
            for persona_data in default_personas:
                existing = PersonaMode.query.filter_by(name=persona_data['name']).first()
                if not existing:
                    persona = PersonaMode(
                        name=persona_data['name'],
                        description=persona_data['description'],
                        is_default=persona_data['is_default'],
                        created_by='system'
                    )
                    db.session.add(persona)
            
            db.session.commit()
            logger.info("✓ Database seeded successfully")
            
        return True
        
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        return False

def backup_db():
    """Create a backup of the database"""
    try:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///yumi_bot.db')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if database_url.startswith('sqlite'):
            # SQLite backup
            import shutil
            db_path = database_url.replace('sqlite:///', '')
            backup_path = f"{db_path}.backup_{timestamp}"
            shutil.copy2(db_path, backup_path)
            logger.info(f"✓ SQLite backup created: {backup_path}")
            
        elif database_url.startswith('postgresql'):
            # PostgreSQL backup
            import subprocess
            backup_file = f"yumi_bot_backup_{timestamp}.sql"
            
            # Extract connection details from URL
            # postgresql://user:password@host:port/database
            url_parts = database_url.replace('postgresql://', '').split('/')
            connection_part = url_parts[0]
            database = url_parts[1] if len(url_parts) > 1 else 'yumi_bot'
            
            user_pass, host_port = connection_part.split('@')
            user, password = user_pass.split(':')
            host, port = host_port.split(':') if ':' in host_port else (host_port, '5432')
            
            # Set environment variable for password
            env = os.environ.copy()
            env['PGPASSWORD'] = password
            
            # Run pg_dump
            cmd = [
                'pg_dump',
                '-h', host,
                '-p', port,
                '-U', user,
                '-d', database,
                '-f', backup_file
            ]
            
            subprocess.run(cmd, env=env, check=True)
            logger.info(f"✓ PostgreSQL backup created: {backup_file}")
            
        return True
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return False

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python migrate.py <command>")
        print("Commands:")
        print("  init     - Initialize database and migrations")
        print("  upgrade  - Upgrade database to latest migration")
        print("  migrate  - Create a new migration")
        print("  seed     - Seed database with initial data")
        print("  backup   - Create database backup")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'init':
        success = init_db()
    elif command == 'upgrade':
        success = upgrade_db()
    elif command == 'migrate':
        message = sys.argv[2] if len(sys.argv) > 2 else f"Migration {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        success = create_migration(message)
    elif command == 'seed':
        success = seed_data()
    elif command == 'backup':
        success = backup_db()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    if success:
        logger.info(f"✓ Command '{command}' completed successfully")
        sys.exit(0)
    else:
        logger.error(f"✗ Command '{command}' failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
