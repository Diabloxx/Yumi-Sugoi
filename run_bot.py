import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from bot_core.main import run

if __name__ == "__main__":
    run()
