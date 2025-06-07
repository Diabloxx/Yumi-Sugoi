"""
Test suite for Yumi Sugoi package entry points and core functionality.
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for testing
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestPackageImports:
    """Test that package imports work correctly."""
    
    def test_bot_core_import(self):
        """Test that bot_core package can be imported."""
        import bot_core
        assert hasattr(bot_core, '__version__')
        assert hasattr(bot_core, 'main')
    
    def test_api_import(self):
        """Test that api package can be imported."""
        import api
        assert hasattr(api, '__version__')
        assert hasattr(api, 'main')
    
    def test_version_consistency(self):
        """Test that both packages have consistent version numbers."""
        import bot_core
        import api
        assert bot_core.__version__ == api.__version__


class TestEntryPoints:
    """Test package entry points."""
    
    @patch.dict(os.environ, {'DISCORD_TOKEN': 'test_token'})
    @patch('bot_core.main.run')
    def test_bot_main_function(self, mock_run):
        """Test that bot main function exists and can be called."""
        from bot_core import main
        main()
        mock_run.assert_called_once()
    
    @patch('api.app_unified.app')
    def test_api_main_function(self, mock_app):
        """Test that API main function exists and can be called."""
        mock_app.run = MagicMock()
        from api import main
        
        # This should not raise an exception
        # We can't easily test the actual function due to Flask's blocking nature
        assert callable(main)


class TestPackageMetadata:
    """Test package metadata and configuration."""
    
    def test_bot_core_metadata(self):
        """Test bot_core package metadata."""
        import bot_core
        assert bot_core.__author__ == "Yumi Sugoi Team"
        assert bot_core.__license__ == "MIT"
        assert bot_core.get_version() == bot_core.__version__
    
    def test_api_metadata(self):
        """Test api package metadata."""
        import api
        assert api.__author__ == "Yumi Sugoi Team"
        assert api.__license__ == "MIT"
        assert api.get_version() == api.__version__


@pytest.mark.integration
class TestModuleIntegration:
    """Test integration between modules."""
    
    def test_persona_module_import(self):
        """Test that persona module can be imported and used."""
        from bot_core import persona
        assert hasattr(persona, 'get_persona_prompt')
        assert hasattr(persona, 'set_persona_mode')
    
    def test_api_routes_import(self):
        """Test that API routes can be imported."""
        from api import app_unified
        assert hasattr(app_unified, 'app')
        # Test that Flask app is configured
        app = app_unified.app
        assert app.config is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
