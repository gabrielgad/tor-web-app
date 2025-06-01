# Torrent Search Web Application

A privacy-focused torrent search and download web application with ProtonVPN integration for CachyOS.

## 🌟 Features

- **Web-based interface** for torrent searching and downloading
- **ProtonVPN integration** for complete privacy protection
- **User authentication** with secure login system
- **Real-time download tracking** with progress monitoring
- **File management** system for completed downloads
- **VPN kill switch** to prevent IP leakage
- **Server rotation** for enhanced privacy
- **Fish shell optimized** for CachyOS

## 🛡️ Privacy Protection

This application protects users by:
- Running all torrent activity on a VPN-protected server
- Users only make normal HTTP requests to the web application
- ISPs cannot detect torrent protocol traffic
- Complete isolation of P2P activity from end users

## 📋 Prerequisites

### CachyOS Requirements

```fish
# Install required packages
sudo pacman -Syu
sudo pacman -S docker docker-compose python python-pip curl unzip git

# Enable Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
# Logout and login again, or use: newgrp docker
```

### ProtonVPN Account

You'll need:
- ProtonVPN account (free or paid)
- OpenVPN configuration files for P2P servers
- ProtonVPN username and password

## 🚀 Quick Start

1. **Clone or download all files** to a directory:
```fish
mkdir ~/torrent-web-app
cd ~/torrent-web-app
# Copy all the provided files here
```

2. **Make setup script executable**:
```fish
chmod +x setup.fish
```

3. **Download ProtonVPN configs**:
   - Visit [account.protonvpn.com](https://account.protonvpn.com)
   - Go to Downloads → OpenVPN configuration files
   - Download P2P-optimized server configs
   - Save to a folder (e.g., `~/Downloads/protonvpn-configs/`)

4. **Run setup**:
```fish
./setup.fish
```

5. **Follow the prompts** to:
   - Configure ProtonVPN settings
   - Set up admin password
   - Choose VPN server

6. **Access the application**:
   - Web app: http://localhost:8080
   - Transmission UI: http://localhost:9091

## 🎛️ Fish Shell Commands

After setup, you'll have these commands available:

```fish
torrent-status     # Check application status
torrent-rotate     # Rotate VPN servers
torrent-logs webapp # View webapp logs
torrent-logs transmission # View transmission logs
vpn-check         # Verify VPN is working
torrent-clean     # Clean old downloads
```

## 👥 User Management

Manage users with the provided script:

```fish
python3 manage_users.py
```

Options:
1. Add user
2. Remove user
3. List users
4. Change password
5. Setup default admin

## 🔧 Configuration

### Server Rotation

Set up automatic VPN server rotation:

```fish
crontab -e
# Add: 0 */12 * * * /path/to/torrent-web-app/rotate-servers.fish
```

### Monitoring

Set up health monitoring:

```fish
crontab -e
# Add: 0 */6 * * * /path/to/torrent-web-app/health-check.fish >> ~/torrent-web-app/health.log
```

### Cleanup

Automatic file cleanup:

```fish
crontab -e
# Add: 0 3 * * * /path/to/torrent-web-app/torrent-clean
```

## 🐳 Docker Services

The application runs two main services:

1. **webapp**: Flask web application (port 8080)
2. **transmission**: Torrent client with VPN (port 9091)

### Useful Docker Commands

```fish
# Check container status
docker-compose ps

# View logs
docker-compose logs webapp
docker-compose logs transmission

# Restart services
docker-compose restart
docker-compose restart transmission

# Stop services
docker-compose down

# Start services
docker-compose up -d

# Update containers
docker-compose pull
docker-compose up -d
```

## 🔍 Troubleshooting

### VPN Connection Issues

```fish
# Check VPN IP
docker exec -it transmission-vpn curl ipinfo.io

# Check VPN logs
docker-compose logs transmission | grep -i "initialization sequence completed"

# Restart transmission container
docker-compose restart transmission
```

### Web Application Issues

```fish
# Check webapp logs
torrent-logs webapp

# Restart webapp
docker-compose restart webapp

# Check if containers are running
docker-compose ps
```

### Permission Issues

```fish
# If Docker permission errors:
sudo systemctl restart docker
newgrp docker

# If file permission errors:
sudo chown -R $USER:$USER downloads/ temp/ config/
```

## 📊 Monitoring and Maintenance

### Health Checks

```fish
# Manual health check
./health-check.fish

# Check disk usage
df -h downloads/

# Check system resources
htop
```

### Log Management

```fish
# View recent logs
tail -f health.log

# Clear old logs
docker system prune -f
```

## 🔐 Security Notes

- Change default admin password immediately
- Use strong passwords for all accounts
- Regularly update Docker images
- Monitor logs for suspicious activity
- Keep ProtonVPN credentials secure

## 📁 File Structure

```
torrent-web-app/
├── setup.fish              # Main setup script
├── app.py                  # Flask backend
├── docker-compose.yml      # Docker configuration
├── requirements.txt        # Python dependencies
├── manage_users.py         # User management
├── templates/
│   ├── index.html         # Main interface
│   └── login.html         # Login page
├── downloads/             # Downloaded files
├── config/               # Configuration files
└── users.json           # User accounts
```

## 🐟 CachyOS Fish Shell Features

This setup is optimized for CachyOS with fish shell:

- Fish-compatible scripts and functions
- CachyOS package manager integration
- Performance optimizations for Arch-based systems
- Fish abbreviations and autocompletion

## 📝 License

This project is for educational purposes. Ensure compliance with local laws regarding torrenting and VPN usage.

## ⚠️ Legal Disclaimer

- Only use for legally available content
- Respect copyright laws in your jurisdiction
- This tool does not endorse piracy
- Users are responsible for their own actions

## 🤝 Support

For issues:
1. Check the troubleshooting section
2. Review Docker logs
3. Ensure ProtonVPN is properly configured
4. Verify all dependencies are installed
