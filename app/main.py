"""
Main Flask Application - Docker Optimized
Torrent Search and Download Web Interface with File Browser
APIs separated into api.py for better organization
"""
import os
import secrets
import logging

from flask import Flask, request, render_template, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

from .auth import user_manager
from .api import api_bp  # Import the API blueprint

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get paths - Docker environment
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_ROOT)

def create_app():
    """Application factory function"""
    
    # Initialize Flask app with correct template folder
    template_dir = find_template_directory()
    app = Flask(__name__, template_folder=template_dir)
    app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

    # Configuration
    app.config['TORRENT_CONFIG'] = {
        "download_dir": os.path.join(PROJECT_ROOT, "downloads"),
        "temp_dir": os.path.join(PROJECT_ROOT, "temp"),
        "transmission": {
            "host": os.environ.get('TRANSMISSION_HOST', 'transmission'),
            "port": int(os.environ.get('TRANSMISSION_PORT', '9091')),
            "user": os.environ.get('TRANSMISSION_USER', 'transmission'),
            "password": os.environ.get('TRANSMISSION_PASSWORD', 'transmission')
        }
    }

    # Create directories if they don't exist
    os.makedirs(app.config['TORRENT_CONFIG']["download_dir"], exist_ok=True)
    os.makedirs(app.config['TORRENT_CONFIG']["temp_dir"], exist_ok=True)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = None

    @login_manager.user_loader
    def load_user(user_id):
        return user_manager.get_user_by_id(user_id)

    # Register API Blueprint
    app.register_blueprint(api_bp)

    # ============================================================================
    # Authentication Routes
    # ============================================================================

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            user = user_manager.authenticate_user(username, password)
            if user:
                login_user(user)
                next_page = request.args.get('next')
                logger.info(f"User {username} logged in successfully")
                return redirect(next_page or url_for('index'))
            else:
                flash('Invalid username or password')
                logger.warning(f"Failed login attempt for username: {username}")

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        username = current_user.username
        logout_user()
        logger.info(f"User {username} logged out")
        return redirect(url_for('login'))

    # ============================================================================
    # Main Routes
    # ============================================================================

    @app.route('/')
    @login_required
    def index():
        return render_template('index.html')

    # ============================================================================
    # File Download Route (separate from API)
    # ============================================================================

    @app.route('/download/<path:filepath>')
    @login_required 
    def download_file(filepath):
        """Download a file to the client"""
        try:
            # Security: ensure the path is within download directory
            safe_path = os.path.normpath(filepath)
            if '..' in safe_path or safe_path.startswith('/'):
                return "Invalid file path", 400
                
            full_path = os.path.join(app.config['TORRENT_CONFIG']["download_dir"], safe_path)
            
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                return "File not found", 404
                
            # Check if path is within download directory (security)
            if not full_path.startswith(os.path.abspath(app.config['TORRENT_CONFIG']["download_dir"])):
                return "Access denied", 403
                
            logger.info(f"File download requested by {current_user.username}: {filepath}")
            return send_file(full_path, as_attachment=True)
            
        except Exception as e:
            logger.error(f"Error downloading file {filepath}: {e}")
            return f"Download failed: {str(e)}", 500

    # ============================================================================
    # Error Handlers
    # ============================================================================

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            from flask import jsonify
            return jsonify({"error": "Not found"}), 404
        return "<h1>404 - Page Not Found</h1><p>The page you're looking for doesn't exist.</p>", 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith('/api/'):
            from flask import jsonify
            return jsonify({"error": "Internal server error"}), 500
        return "<h1>500 - Internal Server Error</h1><p>Something went wrong.</p>", 500

    # Log initialization info
    logger.info("Flask application created successfully")
    logger.info(f"App root: {APP_ROOT}")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"Template folder: {app.template_folder}")
    logger.info(f"Download directory: {app.config['TORRENT_CONFIG']['download_dir']}")
    logger.info(f"Transmission: {app.config['TORRENT_CONFIG']['transmission']['host']}:{app.config['TORRENT_CONFIG']['transmission']['port']}")

    return app

def find_template_directory():
    """Find the templates directory"""
    possible_template_dirs = [
        os.path.join(PROJECT_ROOT, 'templates'),
        os.path.join(APP_ROOT, '..', 'templates'),
        os.path.join(os.path.dirname(APP_ROOT), 'templates'),
        'templates',
        '../templates'
    ]

    template_dir = None
    for tdir in possible_template_dirs:
        abs_path = os.path.abspath(tdir)
        if os.path.exists(abs_path):
            template_dir = abs_path
            logger.info(f"Found templates at: {template_dir}")
            break

    if template_dir is None:
        logger.error("Could not find templates directory!")
        template_dir = os.path.join(PROJECT_ROOT, 'templates')
        os.makedirs(template_dir, exist_ok=True)
        logger.info(f"Created template directory: {template_dir}")

    return template_dir

# For direct execution
if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False)
