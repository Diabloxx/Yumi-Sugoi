"""
Test configuration and utilities for Yumi Sugoi test suite.
"""
import os
import tempfile
import pytest
from unittest.mock import MagicMock

# Test configuration
TEST_CONFIG = {
    'DISCORD_TOKEN': 'test_discord_token_12345',
    'OLLAMA_URL': 'http://localhost:11434/api/generate',
    'OLLAMA_MODEL': 'test_model',
    'API_SECRET_KEY': 'test_secret_key',
    'DATABASE_URL': 'sqlite:///:memory:',
    'REDIS_URL': 'redis://localhost:6379/15',  # Use test database
}


@pytest.fixture
def temp_env():
    """Provide temporary environment variables for testing."""
    original_env = os.environ.copy()
    os.environ.update(TEST_CONFIG)
    yield TEST_CONFIG
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_db():
    """Provide temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def mock_discord_client():
    """Provide a mock Discord client for testing."""
    mock_client = MagicMock()
    mock_client.user.name = "TestBot"
    mock_client.user.id = 12345
    mock_client.guilds = []
    return mock_client


@pytest.fixture
def mock_ollama_response():
    """Provide a mock Ollama API response."""
    return {
        'response': 'This is a test response from the mock LLM.',
        'done': True,
        'context': [123, 456, 789],
        'total_duration': 1000000,
        'load_duration': 500000,
        'prompt_eval_count': 10,
        'eval_count': 20
    }


class TestUtils:
    """Utility functions for testing."""
    
    @staticmethod
    def create_mock_message(content="test message", author_id=67890, channel_id=11111):
        """Create a mock Discord message object."""
        mock_message = MagicMock()
        mock_message.content = content
        mock_message.author.id = author_id
        mock_message.author.name = "TestUser"
        mock_message.channel.id = channel_id
        mock_message.guild.id = 99999
        return mock_message
    
    @staticmethod
    def create_mock_api_response(status_code=200, json_data=None):
        """Create a mock API response object."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {}
        return mock_response
