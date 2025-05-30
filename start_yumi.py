#!/usr/bin/env python3
"""
Yumi Bot Complete Startup Script
This script handles the complete startup of both the API and bot
"""

import os
import sys
import time
import subprocess
import signal
from datetime import datetime

def print_banner():
    """Print startup banner"""
    print("""
🌸 =============================================== 🌸
   ___  ___ ___  ___    ___      ___  ___      _ 
  \\  \\/  /| __|/ _ \\  / _ \\    / _ \\/ _ \\    | |
   \\    / | _|| (_) || (_) |  | (_) | (_) |   | |
    |__|  |___||\\___/  \\___/    \\___/ \\___/    |_|
                                                  
         Yumi Sugoi Discord Bot v1.0.0
         🤖 Advanced AI Companion System
🌸 =============================================== 🌸
""")

def check_environment():
    """Check if environment is properly set up"""
    print("🔍 Checking environment...")
    
    # Check if database exists
    db_path = os.path.join(os.path.dirname(__file__), 'api', 'yumi_bot.db')
    if os.path.exists(db_path):
        print("✅ Database found")
    else:
        print("❌ Database not found - run fix_database_clean.py first")
        return False
    
    # Check if .env file exists
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        print("✅ Environment file found")
    else:
        print("⚠️  No .env file found - creating template")
        create_env_template()
    
    # Check Redis
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        client.ping()
        print("✅ Redis server connected")
    except:
        print("⚠️  Redis not available - some features may be limited")
    
    return True

def create_env_template():
    """Create a template .env file"""
    env_content = """# Yumi Bot Configuration
# Copy this file and add your actual tokens

# Discord Bot Token (required)
DISCORD_TOKEN=your_discord_bot_token_here

# API Configuration
FLASK_SECRET_KEY=your-flask-secret-key-here
JWT_SECRET=your-jwt-secret-here
API_KEY=your-api-key-here

# Database (SQLite is default)
DATABASE_URL=sqlite:///api/yumi_bot.db

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Environment
FLASK_ENV=development
DEBUG=true

# AI/LLM Configuration
OLLAMA_HOST=http://10.0.0.28:11434
DEFAULT_MODEL=mistralrp

# Optional: OpenAI API (if using GPT instead of Ollama)
# OPENAI_API_KEY=your_openai_api_key_here
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("📝 Created .env template - please add your Discord token")

def start_api_server():
    """Start the API server"""
    print("\n🚀 Starting API server...")
    
    api_script = os.path.join(os.path.dirname(__file__), 'api', 'app_fixed.py')
    
    if not os.path.exists(api_script):
        print("❌ API server script not found")
        return None
    
    try:
        # Start API server in background
        process = subprocess.Popen([
            sys.executable, api_script
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a moment for server to start
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ API server started successfully")
            return process
        else:
            print("❌ API server failed to start")
            stdout, stderr = process.communicate()
            print(f"Error: {stderr.decode()}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start API server: {e}")
        return None

def start_bot():
    """Start the Discord bot"""
    print("\n🤖 Starting Discord bot...")
    
    bot_script = os.path.join(os.path.dirname(__file__), 'run_bot.py')
    
    if not os.path.exists(bot_script):
        print("❌ Bot script not found")
        return None
    
    # Check if Discord token is set
    from dotenv import load_dotenv
    load_dotenv()
    
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token or discord_token == 'your_discord_bot_token_here':
        print("❌ Discord token not configured in .env file")
        print("Please add your Discord bot token to .env file")
        return None
    
    try:
        # Start bot
        process = subprocess.Popen([
            sys.executable, bot_script
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print("✅ Discord bot starting...")
        return process
        
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        return None

def monitor_processes(api_process, bot_process):
    """Monitor running processes"""
    print("\n📊 Monitoring services...")
    print("Press Ctrl+C to stop all services")
    
    try:
        while True:
            time.sleep(5)
            
            # Check API process
            if api_process and api_process.poll() is not None:
                print("⚠️  API server stopped unexpectedly")
                break
            
            # Check bot process
            if bot_process and bot_process.poll() is not None:
                print("⚠️  Discord bot stopped unexpectedly")
                break
            
            print(f"🟢 Services running... {datetime.now().strftime('%H:%M:%S')}")
            
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested...")
        
        # Gracefully stop processes
        if api_process:
            api_process.terminate()
            print("🔄 Stopping API server...")
            
        if bot_process:
            bot_process.terminate()
            print("🔄 Stopping Discord bot...")
        
        # Wait for processes to stop
        time.sleep(2)
        
        print("✅ All services stopped")

def main():
    """Main startup function"""
    print_banner()
    print(f"🕐 Startup time: {datetime.now().isoformat()}")
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please fix issues and try again.")
        return
    
    # Start API server
    api_process = start_api_server()
    
    # Start bot (optional - only if token is configured)
    bot_process = start_bot()
    
    if api_process:
        print("\n🎉 Services started successfully!")
        print("\n📋 Service URLs:")
        print("   API Server: http://localhost:5000")
        print("   Health Check: http://localhost:5000/api/health")
        print("   Dashboard: http://localhost:3000 (if frontend is running)")
        
        # Monitor processes
        monitor_processes(api_process, bot_process)
    else:
        print("\n❌ Failed to start required services")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
