#!/usr/bin/env python3
"""
Run the Torrent Search Application in Docker
"""
import os
import sys
import logging

# Configure logging for Docker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

# Get the application directory (should be /app in Docker)
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

# Import the Flask app
from app.main import create_app

def main():
    """Main application entry point"""
    logger.info("?? Starting Torrent Search Application in Docker...")
    logger.info(f"?? App directory: {APP_DIR}")
    
    # Verify critical paths exist
    template_dir = os.path.join(APP_DIR, 'templates')
    app_dir = os.path.join(APP_DIR, 'app')
    
    logger.info(f"?? Template directory: {template_dir}")
    logger.info(f"?? App directory: {app_dir}")
    
    if not os.path.exists(template_dir):
        logger.error(f"? Templates directory not found: {template_dir}")
        sys.exit(1)
    
    if not os.path.exists(app_dir):
        logger.error(f"? App directory not found: {app_dir}")
        sys.exit(1)
    
    # List template files for debugging
    try:
        template_files = os.listdir(template_dir)
        logger.info(f"?? Template files found: {template_files}")
    except Exception as e:
        logger.error(f"? Error listing template files: {e}")
    
    # Environment info
    transmission_host = os.environ.get('TRANSMISSION_HOST', 'transmission')
    transmission_port = os.environ.get('TRANSMISSION_PORT', '9091')
    logger.info(f"?? Transmission: {transmission_host}:{transmission_port}")
    
    # Create the Flask app
    try:
        app = create_app()
        logger.info("? Flask app created successfully")
        
        # Verify template folder
        logger.info(f"?? Flask template folder: {app.template_folder}")
        
        # Start the application
        logger.info("?? Starting Flask development server...")
        logger.info("?? Access the app at: http://localhost:8080")
        logger.info("?? Default login: admin / admin123")
        logger.info("-" * 50)
        
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # Set to False in production Docker
            use_reloader=False,  # Disable reloader in Docker
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"? Error starting application: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()