"""
Main Flask Application - Docker Optimized
Torrent Search and Download Web Interface with File Browser
"""
import os
import json
import time
import threading
import logging
import secrets
import traceback
import urllib.parse

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

from .auth import user_manager
from .transmission_client import get_transmission_client
from .utils import (
    format_size, parse_size, create_magnet_link, sanitize_filename,
    get_file_list, search_torrents_json_api, search_torrents_html_scrape,
    validate_info_hash, get_default_trackers
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get paths - Docker environment
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_ROOT)

# Initialize Flask app with correct template folder
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

app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

logger.info(f"Flask app initialized with template folder: {app.template_folder}")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None

@login_manager.user_loader
def load_user(user_id):
    return user_manager.get_user_by_id(user_id)

# Configuration
CONFIG = {
    "download_dir": os.path.join(PROJECT_ROOT, "downloads"),
    "temp_dir": os.path.join(PROJECT_ROOT, "temp"),
    "transmission": {
        "host": os.environ.get('TRANSMISSION_HOST', 'transmission'),
        "port": int(os.environ.get('TRANSMISSION_PORT', '9091')),
        "user": os.environ.get('TRANSMISSION_USER', 'transmission'),
        "password": os.environ.get('TRANSMISSION_PASSWORD', 'transmission')
    },
    "torrent_site": {
        "search_url": "https://apibay.org/q.php?q={query}",
        "type": "json_api"
    }
}

# Create directories if they don't exist
os.makedirs(CONFIG["download_dir"], exist_ok=True)
os.makedirs(CONFIG["temp_dir"], exist_ok=True)

# Active downloads tracking
active_downloads = {}

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

    try:
        return render_template('login.html')
    except Exception as e:
        logger.error(f"Template error for login.html: {e}")
        # Fallback to inline template
        from flask import render_template_string
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Login - Torrent Search</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .login-form { max-width: 400px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h2 { text-align: center; color: #333; margin-bottom: 30px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .alert { background: #f8d7da; color: #721c24; padding: 10px; margin: 10px 0; border-radius: 4px; }
        .footer { text-align: center; margin-top: 20px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="login-form">
        <h2>Login</h2>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required autofocus>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        <div class="footer">
            <p>Default credentials: admin / admin123</p>
        </div>
    </div>
</body>
</html>''')

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
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Template error for index.html: {e}")
        # Return functional fallback template
        return get_fallback_index()

def get_fallback_index():
    from flask import render_template_string
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Torrent Search</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; }
        body { font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid #ddd; padding-bottom: 20px; }
        .search-box { margin: 20px 0; }
        input { padding: 12px; width: 400px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { padding: 12px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #0056b3; }
        .btn-secondary { background: #6c757d; }
        .btn-secondary:hover { background: #5a6268; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .btn-success { background: #28a745; }
        .section-title { font-size: 1.5rem; color: #2c3e50; margin: 30px 0 20px 0; padding-bottom: 10px; border-bottom: 1px solid #e9ecef; }
        .result-item, .download-item, .file-item { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 4px; background: #f9f9f9; }
        .result-name, .download-name, .file-name { font-weight: bold; margin-bottom: 8px; color: #333; }
        .result-details, .file-details { color: #666; font-size: 14px; margin-bottom: 10px; }
        .loading { text-align: center; padding: 20px; color: #007bff; }
        .empty-state { text-align: center; padding: 40px; color: #666; }
        .warning { background: #fff3cd; color: #856404; padding: 10px; border-radius: 4px; margin-bottom: 20px; }
        .progress-bar { width: 100%; height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.5s ease; }
        .progress-text { text-align: center; line-height: 20px; font-size: 12px; font-weight: bold; color: white; }
        .file-actions { display: flex; gap: 10px; margin-top: 10px; }
        .btn-small { padding: 6px 12px; font-size: 12px; }
        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
        .status-downloading { background: #d1ecf1; color: #0c5460; }
        .status-completed { background: #d4edda; color: #155724; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-stopped { background: #f8d7da; color: #721c24; }
        .status-seeding { background: #fff3cd; color: #856404; }
        .file-controls { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .file-count { color: #6c757d; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="warning">
            <strong>Note:</strong> Using fallback template. Check server logs for template issues.
        </div>
        
        <div class="header">
            <h1>Torrent Search & Download Manager</h1>
            <div>
                <button class="btn-secondary" onclick="testAPI()">Test API</button>
                <button class="btn-secondary" onclick="checkHealth()">Health Check</button>
                <button class="btn-secondary" onclick="refreshAll()">Refresh All</button>
                <a href="/logout" style="padding: 12px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 4px;">Logout</a>
            </div>
        </div>
        
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search for torrents..." autofocus>
            <button onclick="search()">Search</button>
        </div>
        
        <div id="results"></div>
        
        <div class="section-title">Active Downloads</div>
        <div id="downloads"></div>
        
        <div class="section-title">Downloaded Files</div>
        <div class="file-controls">
            <button class="btn-secondary" onclick="refreshFiles()">Refresh Files</button>
            <span id="file-count" class="file-count"></span>
        </div>
        <div id="files"></div>
    </div>
    
    <script>
        let downloadInterval;
        let isPolling = false;
        
        console.log('Fallback template JavaScript loaded');
        
        async function search() {
            console.log('Search function called');
            const query = document.getElementById("searchInput").value.trim();
            console.log('Search query:', query);
            
            if (!query) {
                console.log('Empty query, returning');
                return;
            }
            
            const resultsDiv = document.getElementById("results");
            resultsDiv.innerHTML = '<div class="loading">Searching...</div>';
            
            try {
                console.log('Making fetch request to:', `/api/search?q=${encodeURIComponent(query)}`);
                const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                console.log('Response status:', response.status);
                
                const data = await response.json();
                console.log('Response data:', data);
                
                if (data.results && data.results.length > 0) {
                    console.log('Displaying results:', data.results.length);
                    resultsDiv.innerHTML = `
                        <div class="section-title">Search Results (${data.results.length})</div>
                        ${data.results.map(result => `
                            <div class="result-item">
                                <div class="result-name">${escapeHtml(result.name)}</div>
                                <div class="result-details">
                                    Size: ${result.size} | Seeders: ${result.seeders} | Leechers: ${result.leechers} | Added: ${result.added}
                                </div>
                                <button onclick="download('${result.info_hash}', '${escapeHtml(result.name).replace(/'/g, "\\'")}')">Download</button>
                            </div>
                        `).join("")}
                    `;
                } else {
                    console.log('No results found');
                    resultsDiv.innerHTML = '<div class="empty-state">No results found</div>';
                }
            } catch (error) {
                console.error("Search error:", error);
                resultsDiv.innerHTML = '<div class="empty-state">Search failed: ' + error.message + '</div>';
            }
        }
        
        async function download(infoHash, name) {
            console.log('Download starting:', name, infoHash);
            const button = event.target;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Starting...";

            try {
                const response = await fetch("/api/download", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({info_hash: infoHash, name: name})
                });

                const data = await response.json();

                if (data.success) {
                    button.textContent = "Added!";
                    button.style.background = "#28a745";
                    refreshTorrents();
                    startDownloadPolling();
                } else {
                    throw new Error(data.error || "Unknown error");
                }
            } catch (error) {
                console.error("Download error:", error);
                button.disabled = false;
                button.textContent = originalText;
                alert("Download failed: " + error.message);
            }
        }
        
        async function refreshTorrents() {
            console.log('Refreshing torrents...');
            const downloadsDiv = document.getElementById("downloads");
            
            try {
                const response = await fetch("/api/current-torrents");
                const data = await response.json();
                console.log('Torrents API response:', data);
                
                if (data.torrents && data.torrents.length > 0) {
                    downloadsDiv.innerHTML = data.torrents.map(torrent => {
                        const statusClass = `status-${torrent.status.replace(/\\s+/g, '-')}`;
                        let statusText = torrent.status;
                        let progressColor = '#28a745';
                        
                        if (torrent.error > 0) {
                            statusText = `Error: ${torrent.error_string}`;
                            progressColor = '#dc3545';
                        }
                        
                        return `
                            <div class="download-item">
                                <div class="download-name">${escapeHtml(torrent.name)}</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${torrent.progress}%; background: ${progressColor};">
                                        <div class="progress-text">${torrent.progress.toFixed(1)}%</div>
                                    </div>
                                </div>
                                <div class="result-details">
                                    <span class="status-badge ${statusClass}">${statusText}</span>
                                    ${torrent.download_rate > 0 ? ` | Down: ${formatSpeed(torrent.download_rate)}` : ''}
                                    ${torrent.upload_rate > 0 ? ` | Up: ${formatSpeed(torrent.upload_rate)}` : ''}
                                    ${torrent.error > 0 ? '<br><strong>Issue:</strong> Check download directory permissions' : ''}
                                </div>
                                <div class="file-actions">
                                    <button class="btn-small btn-secondary" onclick="removeTorrent(${torrent.id})">Remove</button>
                                    ${torrent.status === 'stopped' ? `<button class="btn-small" onclick="startTorrent(${torrent.id})">Start</button>` : ''}
                                    ${torrent.status === 'downloading' || torrent.status === 'seeding' ? `<button class="btn-small btn-secondary" onclick="pauseTorrent(${torrent.id})">Pause</button>` : ''}
                                </div>
                            </div>
                        `;
                    }).join("");
                } else {
                    downloadsDiv.innerHTML = '<div class="empty-state">No active downloads</div>';
                }
            } catch (error) {
                console.error("Refresh error:", error);
                downloadsDiv.innerHTML = `<div class="empty-state">Failed to load downloads: ${error.message}</div>`;
            }
        }
        
        async function refreshFiles() {
            console.log('Refreshing files...');
            const filesDiv = document.getElementById("files");
            const fileCountSpan = document.getElementById("file-count");
            
            try {
                const response = await fetch("/api/files");
                const data = await response.json();
                console.log('Files API response:', data);

                if (data.files && data.files.length > 0) {
                    fileCountSpan.textContent = `${data.files.length} files (${formatTotalSize(data.files)})`;
                    
                    filesDiv.innerHTML = data.files.map(file => `
                        <div class="file-item">
                            <div class="file-name">${escapeHtml(file.name)}</div>
                            <div class="file-details">
                                Size: ${file.size} | Modified: ${file.modified}
                                ${file.folder !== '/' ? ` | Folder: ${file.folder}` : ''}
                            </div>
                            <div class="file-actions">
                                <a href="/download/${encodeURIComponent(file.path)}" 
                                   class="btn btn-small" 
                                   download="${file.name}">
                                    Download to Device
                                </a>
                                <button class="btn btn-small btn-secondary" 
                                        onclick="deleteFile('${file.path}', '${escapeHtml(file.name).replace(/'/g, "\\'")}')">
                                    Delete
                                </button>
                            </div>
                        </div>
                    `).join("");
                } else {
                    fileCountSpan.textContent = '0 files';
                    filesDiv.innerHTML = '<div class="empty-state">No downloaded files yet</div>';
                }
            } catch (error) {
                console.error("Files refresh error:", error);
                filesDiv.innerHTML = `<div class="empty-state">Failed to load files: ${error.message}</div>`;
                fileCountSpan.textContent = '';
            }
        }
        
        async function deleteFile(filepath, filename) {
            if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
                return;
            }
            
            try {
                const response = await fetch("/api/files/delete", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({filepath: filepath})
                });

                const data = await response.json();

                if (data.success) {
                    alert(`File "${filename}" deleted successfully`);
                    refreshFiles();
                } else {
                    throw new Error(data.error || "Unknown error");
                }
            } catch (error) {
                console.error("Delete error:", error);
                alert("Delete failed: " + error.message);
            }
        }
        
        async function removeTorrent(torrentId) {
            if (!confirm('Remove this torrent? (Files will be kept)')) return;
            
            try {
                const response = await fetch("/api/torrent/remove", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({torrent_id: torrentId})
                });
                
                const data = await response.json();
                if (data.success) {
                    refreshTorrents();
                } else {
                    alert("Failed to remove torrent: " + (data.error || "Unknown error"));
                }
            } catch (error) {
                alert("Failed to remove torrent: " + error.message);
            }
        }
        
        async function startTorrent(torrentId) {
            try {
                const response = await fetch("/api/torrent/start", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({torrent_id: torrentId})
                });
                
                const data = await response.json();
                if (data.success) {
                    refreshTorrents();
                } else {
                    alert("Failed to start torrent: " + (data.error || "Unknown error"));
                }
            } catch (error) {
                alert("Failed to start torrent: " + error.message);
            }
        }
        
        async function pauseTorrent(torrentId) {
            try {
                const response = await fetch("/api/torrent/pause", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({torrent_id: torrentId})
                });
                
                const data = await response.json();
                if (data.success) {
                    refreshTorrents();
                } else {
                    alert("Failed to pause torrent: " + (data.error || "Unknown error"));
                }
            } catch (error) {
                alert("Failed to pause torrent: " + error.message);
            }
        }
        
        function startDownloadPolling() {
            if (isPolling) return;
            console.log('Starting download polling...');
            isPolling = true;
            downloadInterval = setInterval(() => {
                refreshTorrents();
                refreshFiles();
            }, 5000);
        }

        function stopDownloadPolling() {
            if (downloadInterval) {
                console.log('Stopping download polling');
                clearInterval(downloadInterval);
                downloadInterval = null;
                isPolling = false;
            }
        }
        
        async function refreshAll() {
            refreshTorrents();
            refreshFiles();
        }
        
        async function testAPI() {
            try {
                const response = await fetch("/api/current-torrents");
                const data = await response.json();
                console.log('API Response:', data);
                alert(`API Test Results:\\nStatus: ${response.status}\\nTorrents: ${data.torrents ? data.torrents.length : 'none'}`);
            } catch (error) {
                console.error('API Test Error:', error);
                alert('API Test Failed: ' + error.message);
            }
        }
        
        async function checkHealth() {
            try {
                const response = await fetch("/api/health");
                const data = await response.json();
                alert(`Health Status: ${data.overall}\\nTransmission: ${data.transmission}\\nDownload Dir: ${data.download_dir}`);
            } catch (error) {
                alert('Health check failed: ' + error.message);
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function formatSpeed(bytesPerSecond) {
            if (bytesPerSecond === 0) return '0 B/s';
            const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
            let size = bytesPerSecond;
            let unitIndex = 0;
            
            while (size >= 1024 && unitIndex < units.length - 1) {
                size /= 1024;
                unitIndex++;
            }
            
            return `${size.toFixed(1)} ${units[unitIndex]}`;
        }
        
        function formatTotalSize(files) {
            const totalBytes = files.reduce((sum, file) => sum + file.size_bytes, 0);
            const units = ['B', 'KB', 'MB', 'GB', 'TB'];
            let size = totalBytes;
            let unitIndex = 0;
            
            while (size >= 1024 && unitIndex < units.length - 1) {
                size /= 1024;
                unitIndex++;
            }
            
            return `${size.toFixed(1)} ${units[unitIndex]}`;
        }
        
        document.getElementById("searchInput").addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                console.log('Enter key pressed, calling search');
                search();
            }
        });
        
        window.addEventListener('load', function() {
            console.log('Page loaded, loading all data...');
            refreshTorrents();
            refreshFiles();
            
            // Check if there are active downloads and start polling
            setTimeout(() => {
                const downloads = document.getElementById("downloads");
                if (downloads.innerHTML.includes("progress-")) {
                    startDownloadPolling();
                }
            }, 1000);
        });

        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                console.log('Page hidden, stopping polling');
                stopDownloadPolling();
            } else {
                console.log('Page visible, refreshing and restarting polling');
                refreshAll();
                setTimeout(() => {
                    const downloads = document.getElementById("downloads");
                    if (downloads.innerHTML.includes("progress-")) {
                        startDownloadPolling();
                    }
                }, 1000);
            }
        });
    </script>
</body>
</html>''')

# ============================================================================
# API Routes - Health and Status
# ============================================================================

@app.route('/api/health', methods=['GET'])
@login_required
def health_check():
    """Check the health of the application and its dependencies"""
    health_status = {
        "app": "healthy",
        "transmission": "unknown",
        "download_dir": "unknown",
        "timestamp": time.time()
    }
    
    # Check Transmission connection
    try:
        client = get_transmission_client()
        if client:
            success, result = client.test_connection()
            if success:
                health_status["transmission"] = "healthy"
                health_status["transmission_stats"] = result
            else:
                health_status["transmission"] = f"unhealthy: {result}"
            health_status["transmission_host"] = f"{CONFIG['transmission']['host']}:{CONFIG['transmission']['port']}"
        else:
            health_status["transmission"] = "connection failed"
    except Exception as e:
        health_status["transmission"] = f"error: {str(e)}"
    
    # Check download directory
    try:
        download_dir = CONFIG["download_dir"]
        if os.path.exists(download_dir) and os.access(download_dir, os.W_OK):
            health_status["download_dir"] = "healthy"
            health_status["download_dir_path"] = download_dir
        else:
            health_status["download_dir"] = "not accessible"
    except Exception as e:
        health_status["download_dir"] = f"error: {str(e)}"
    
    # Overall status
    if health_status["transmission"] == "healthy" and health_status["download_dir"] == "healthy":
        health_status["overall"] = "healthy"
    else:
        health_status["overall"] = "unhealthy"
    
    status_code = 200 if health_status["overall"] == "healthy" else 503
    return jsonify(health_status), status_code

# ============================================================================
# API Routes - Search
# ============================================================================

@app.route('/api/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        logger.info(f"Searching for: {query}")
        
        if CONFIG["torrent_site"]["type"] == "json_api":
            results = search_torrents_json_api(query, CONFIG["torrent_site"]["search_url"])
        else:
            return jsonify({"error": "Invalid search type configured"}), 500

        logger.info(f"Found {len(results)} results for query: {query}")
        return jsonify({"results": results, "query": query})

    except Exception as e:
        logger.error(f"Search error for query '{query}': {str(e)}")
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

# ============================================================================
# API Routes - Downloads & Torrents
# ============================================================================

@app.route('/api/download', methods=['POST'])
@login_required
def download_torrent():
    data = request.json
    logger.info(f"[DOWNLOAD] Received download request: {data}")

    if not data or 'info_hash' not in data or 'name' not in data:
        return jsonify({"error": "Missing required fields: info_hash and name"}), 400

    info_hash = data['info_hash'].strip()
    name = data['name'].strip()
    
    if not validate_info_hash(info_hash):
        return jsonify({"error": "Invalid info hash format"}), 400

    download_id = str(int(time.time() * 1000))

    try:
        client = get_transmission_client()
        if not client:
            logger.error("[DOWNLOAD] Failed to connect to torrent client")
            return jsonify({"error": "Failed to connect to torrent client."}), 500

        magnet_link = create_magnet_link(info_hash, name, get_default_trackers())
        logger.info(f"[DOWNLOAD] Created magnet link: {magnet_link[:100]}...")

        # Use the exact same download path that Transmission uses
        download_path = "/data/downloads"  # This is the path inside Transmission container
        
        active_downloads[download_id] = {
            "name": name,
            "info_hash": info_hash,
            "status": "starting",
            "progress": 0,
            "started_at": time.time(),
            "started_by": current_user.username
        }

        download_thread = threading.Thread(
            target=start_download_thread,
            args=(client, magnet_link, name, download_id, download_path),
            daemon=True
        )
        download_thread.start()

        return jsonify({
            "success": True,
            "download_id": download_id,
            "message": "Download started"
        })

    except Exception as e:
        logger.error(f"[DOWNLOAD] Download error: {str(e)}")
        return jsonify({"error": f"Failed to start download: {str(e)}"}), 500

def start_download_thread(client, magnet_link, name, download_id, download_path):
    """Background thread function to handle torrent download"""
    try:
        logger.info(f"[THREAD] Starting download for: {name} to {download_path}")
        torrent = client.add_torrent(magnet_link, download_dir=download_path)
        
        active_downloads[download_id].update({
            "torrent_id": torrent.id,
            "status": "downloading",
            "transmission_name": torrent.name
        })
        
        logger.info(f"[THREAD] Download tracked successfully: {download_id}")
        
    except Exception as e:
        logger.error(f"[THREAD] Error in download thread: {str(e)}")
        active_downloads[download_id].update({
            "status": "error",
            "error": str(e)
        })

@app.route('/api/current-torrents', methods=['GET'])
@login_required
def get_current_torrents():
    """Get all current torrents with their progress"""
    try:
        client = get_transmission_client()
        if not client:
            return jsonify({"error": "Failed to connect to torrent client"}), 500

        torrents = client.list_torrents()
        torrent_list = [torrent.to_dict() for torrent in torrents]
        
        # Sync with active_downloads
        for torrent in torrent_list:
            for download_id, active_download in active_downloads.items():
                if active_download.get("torrent_id") == torrent["id"]:
                    active_download["progress"] = torrent["progress"]
                    active_download["status"] = torrent["status"]
        
        logger.info(f"[API] Returning {len(torrent_list)} torrents")
        return jsonify({"torrents": torrent_list, "count": len(torrent_list)})

    except Exception as e:
        logger.error(f"[API] Error getting current torrents: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/torrent/remove', methods=['POST'])
@login_required
def remove_torrent():
    """Remove a torrent"""
    try:
        data = request.json
        if not data or 'torrent_id' not in data:
            return jsonify({"error": "torrent_id required"}), 400
            
        client = get_transmission_client()
        if not client:
            return jsonify({"error": "Failed to connect to torrent client"}), 500
            
        success = client.remove_torrent(data['torrent_id'], delete_data=False)
        
        if success:
            # Remove from active_downloads
            for download_id, active_download in list(active_downloads.items()):
                if active_download.get("torrent_id") == data['torrent_id']:
                    del active_downloads[download_id]
                    break
                    
            logger.info(f"Torrent {data['torrent_id']} removed by {current_user.username}")
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to remove torrent"}), 500
            
    except Exception as e:
        logger.error(f"Error removing torrent: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/torrent/start', methods=['POST'])
@login_required
def start_torrent():
    """Start a torrent"""
    try:
        data = request.json
        if not data or 'torrent_id' not in data:
            return jsonify({"error": "torrent_id required"}), 400
            
        client = get_transmission_client()
        if not client:
            return jsonify({"error": "Failed to connect to torrent client"}), 500
            
        success = client.start_torrent(data['torrent_id'])
        
        if success:
            logger.info(f"Torrent {data['torrent_id']} started by {current_user.username}")
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to start torrent"}), 500
            
    except Exception as e:
        logger.error(f"Error starting torrent: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/torrent/pause', methods=['POST'])
@login_required
def pause_torrent():
    """Pause a torrent"""
    try:
        data = request.json
        if not data or 'torrent_id' not in data:
            return jsonify({"error": "torrent_id required"}), 400
            
        client = get_transmission_client()
        if not client:
            return jsonify({"error": "Failed to connect to torrent client"}), 500
            
        success = client.stop_torrent(data['torrent_id'])
        
        if success:
            logger.info(f"Torrent {data['torrent_id']} paused by {current_user.username}")
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to pause torrent"}), 500
            
    except Exception as e:
        logger.error(f"Error pausing torrent: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# API Routes - File Management
# ============================================================================

@app.route('/api/files', methods=['GET'])
@login_required
def list_files():
    """List all downloaded files"""
    try:
        files = []
        download_dir = CONFIG["download_dir"]
        
        if not os.path.exists(download_dir):
            return jsonify({"files": [], "message": "Download directory not found"})
        
        for root, dirs, filenames in os.walk(download_dir):
            # Skip hidden directories and incomplete folders
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'incomplete']
            
            for filename in filenames:
                if filename.startswith('.') or filename == 'Thumbs.db' or filename.endswith('.part'):
                    continue
                    
                filepath = os.path.join(root, filename)
                relative_path = os.path.relpath(filepath, download_dir)
                
                try:
                    stat = os.stat(filepath)
                    files.append({
                        "name": filename,
                        "path": relative_path,
                        "size": format_size(stat.st_size),
                        "size_bytes": stat.st_size,
                        "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                        "folder": os.path.dirname(relative_path) if os.path.dirname(relative_path) else "/"
                    })
                except OSError:
                    continue
        
        # Sort by modification time, newest first
        files.sort(key=lambda x: x['size_bytes'], reverse=True)
        
        return jsonify({"files": files, "count": len(files)})
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<path:filepath>')
@login_required 
def download_file(filepath):
    """Download a file to the client"""
    try:
        # Security: ensure the path is within download directory
        safe_path = os.path.normpath(filepath)
        if '..' in safe_path or safe_path.startswith('/'):
            return "Invalid file path", 400
            
        full_path = os.path.join(CONFIG["download_dir"], safe_path)
        
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return "File not found", 404
            
        # Check if path is within download directory (security)
        if not full_path.startswith(os.path.abspath(CONFIG["download_dir"])):
            return "Access denied", 403
            
        logger.info(f"File download requested by {current_user.username}: {filepath}")
        return send_file(full_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error downloading file {filepath}: {e}")
        return f"Download failed: {str(e)}", 500

@app.route('/api/files/delete', methods=['POST'])
@login_required
def delete_file():
    """Delete a downloaded file"""
    try:
        data = request.json
        if not data or 'filepath' not in data:
            return jsonify({"error": "filepath required"}), 400
            
        filepath = data['filepath']
        safe_path = os.path.normpath(filepath)
        
        if '..' in safe_path or safe_path.startswith('/'):
            return jsonify({"error": "Invalid file path"}), 400
            
        full_path = os.path.join(CONFIG["download_dir"], safe_path)
        
        if not full_path.startswith(os.path.abspath(CONFIG["download_dir"])):
            return jsonify({"error": "Access denied"}), 403
            
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"File deleted by {current_user.username}: {filepath}")
            return jsonify({"success": True, "message": "File deleted"})
        else:
            return jsonify({"error": "File not found"}), 404
            
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/downloads', methods=['GET'])
@login_required
def debug_downloads():
    """Debug endpoint to see active downloads"""
    return jsonify({
        "active_downloads": active_downloads,
        "active_downloads_count": len(active_downloads),
        "timestamp": time.time(),
        "config_paths": {
            "app_root": APP_ROOT,
            "project_root": PROJECT_ROOT,
            "download_dir": CONFIG["download_dir"],
            "temp_dir": CONFIG["temp_dir"]
        }
    })

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found"}), 404
    return "<h1>404 - Page Not Found</h1><p>The page you're looking for doesn't exist.</p>", 404

@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal server error"}), 500
    return "<h1>500 - Internal Server Error</h1><p>Something went wrong.</p>", 500

# ============================================================================
# Application Factory
# ============================================================================

def create_app():
    """Application factory function"""
    logger.info("Creating Flask application for Docker...")
    logger.info(f"App root: {APP_ROOT}")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"Flask template folder: {app.template_folder}")
    logger.info(f"Template folder exists: {os.path.exists(app.template_folder)}")
    if os.path.exists(app.template_folder):
        try:
            template_files = os.listdir(app.template_folder)
            logger.info(f"Template files found: {template_files}")
        except Exception as e:
            logger.error(f"Error listing template files: {e}")
    logger.info(f"Transmission: {CONFIG['transmission']['host']}:{CONFIG['transmission']['port']}")
    logger.info(f"Download directory: {CONFIG['download_dir']}")
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False)