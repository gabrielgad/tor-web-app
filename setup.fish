#!/usr/bin/env fish

# Fixed setup script for torrent web app
set GREEN '\033[0;32m'
set YELLOW '\033[1;33m'
set RED '\033[0;31m'
set NC '\033[0m'

echo -e $GREEN
echo "===================================="
echo "  Torrent Web App Setup (Fixed)"
echo "  CachyOS + Fish Shell Edition"  
echo "===================================="
echo -e $NC

# Install Python dependencies
echo -e $YELLOW"Installing Python dependencies..."$NC
pip install --user flask flask-login werkzeug

# Create users.json with admin user
echo -e $YELLOW"Setting up admin user..."$NC
echo -e $YELLOW"Enter admin password for web interface:"$NC
read -s admin_password

python3 -c "
import json
from werkzeug.security import generate_password_hash

users = {
    'admin': {
        'id': '1',
        'username': 'admin',
        'password_hash': generate_password_hash('$admin_password')
    }
}

with open('users.json', 'w') as f:
    json.dump(users, f, indent=2)

print('✅ Admin user created')
"

# Create basic template files
echo -e $YELLOW"Creating template files..."$NC

# Create index.html
echo '<!DOCTYPE html>
<html>
<head>
    <title>Torrent Search</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .search-box { display: flex; gap: 10px; margin-bottom: 20px; }
        .search-box input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        .btn { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #0056b3; }
        .results { margin-top: 20px; }
        .result-item { padding: 15px; border: 1px solid #ddd; margin-bottom: 10px; border-radius: 4px; }
        .result-name { font-weight: bold; margin-bottom: 5px; }
        .result-details { color: #666; font-size: 14px; }
        .logout { background: #dc3545; }
        .logout:hover { background: #c82333; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Torrent Search</h1>
            <a href="/logout" class="btn logout">Logout</a>
        </div>
        
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search for torrents...">
            <button class="btn" onclick="search()">Search</button>
        </div>
        
        <div id="results" class="results"></div>
    </div>

    <script>
        function search() {
            const query = document.getElementById("searchInput").value;
            if (!query) return;
            
            fetch(`/api/search?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    const resultsDiv = document.getElementById("results");
                    if (data.results && data.results.length > 0) {
                        resultsDiv.innerHTML = data.results.map(result => `
                            <div class="result-item">
                                <div class="result-name">${result.name}</div>
                                <div class="result-details">
                                    Size: ${result.size} | Seeders: ${result.seeders} | Leechers: ${result.leechers}
                                </div>
                                <button class="btn" onclick="download(\'${result.info_hash}\', \'${result.name.replace(/\'/g, "\\\'").replace(/"/g, "&quot;")}\')">Download</button>
                            </div>
                        `).join("");
                    } else {
                        resultsDiv.innerHTML = "<p>No results found</p>";
                    }
                })
                .catch(error => {
                    console.error("Search error:", error);
                    document.getElementById("results").innerHTML = "<p>Search failed</p>";
                });
        }
        
        function download(infoHash, name) {
            fetch("/api/download", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({info_hash: infoHash, name: name})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("Download started!");
                } else {
                    alert("Download failed: " + (data.error || "Unknown error"));
                }
            })
            .catch(error => {
                console.error("Download error:", error);
                alert("Download failed");
            });
        }
        
        document.getElementById("searchInput").addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                search();
            }
        });
    </script>
</body>
</html>' > templates/index.html

# Create login.html
echo '<!DOCTYPE html>
<html>
<head>
    <title>Login - Torrent App</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .login-container { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
        .login-header { text-align: center; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"] { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        .btn { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .btn:hover { background: #0056b3; }
        .error { color: #dc3545; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h2>🔐 Torrent App Login</h2>
        </div>
        
        <form method="POST">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" class="btn">Login</button>
        </form>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="error">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>
</body>
</html>' > templates/login.html

echo -e $GREEN"✅ Template files created"$NC

# Start containers
echo -e $YELLOW"Starting Docker containers..."$NC
docker-compose up -d --build

# Wait and check status
echo -e $YELLOW"Waiting for containers to start..."$NC
sleep 10

echo -e $YELLOW"Container status:"$NC
docker-compose ps

echo
echo -e $GREEN"🎉 Setup complete!"$NC
echo "=============================="
echo -e $YELLOW"Web app:"$NC $GREEN"http://localhost:8080"$NC
echo -e $YELLOW"Transmission:"$NC $GREEN"http://localhost:9091"$NC
echo -e $YELLOW"Login:"$NC $GREEN"admin / [your password]"$NC
