#!/usr/bin/env python3
"""
Wait for services to be ready before starting the webapp
"""
import time
import socket
import requests
import subprocess
import sys
import os

def wait_for_port(host, port, timeout=300):
    """Wait for a port to be available"""
    print(f"? Waiting for {host}:{port} to be available...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                if result == 0:
                    print(f"? Port {host}:{port} is available!")
                    return True
        except socket.gaierror:
            pass
        except Exception as e:
            print(f"?? Checking {host}:{port} - {e}")
        
        time.sleep(2)
    
    print(f"? Timeout waiting for {host}:{port}")
    return False

def wait_for_transmission(host, port, username, password, timeout=300):
    """Wait for Transmission RPC to be ready"""
    print(f"? Waiting for Transmission RPC at {host}:{port}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Try to connect to Transmission RPC
            url = f"http://{host}:{port}/transmission/rpc"
            response = requests.post(
                url,
                auth=(username, password),
                timeout=10,
                json={"method": "session-get"}
            )
            
            # Transmission returns 409 with session ID on first request, which is normal
            if response.status_code in [200, 409]:
                print(f"? Transmission RPC is ready!")
                return True
                
        except requests.exceptions.RequestException as e:
            print(f"?? Checking Transmission RPC - {e}")
        except Exception as e:
            print(f"?? Checking Transmission RPC - {e}")
        
        time.sleep(5)
    
    print(f"? Timeout waiting for Transmission RPC")
    return False

def start_flask_app():
    """Start the Flask application"""
    print("?? Starting Flask application...")
    
    # Set environment variables
    os.environ['FLASK_APP'] = 'run.py'
    os.environ['FLASK_ENV'] = 'production'
    
    try:
        # Start the Flask app
        subprocess.run([
            "python", "-m", "flask", "run",
            "--host=0.0.0.0",
            "--port=5000"
        ], check=True)
    except KeyboardInterrupt:
        print("\n?? Application stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"? Flask app failed to start: {e}")
        sys.exit(1)

def main():
    print("?? Docker Webapp Starting...")
    print("=" * 50)
    
    # Configuration from environment
    transmission_host = os.environ.get('TRANSMISSION_HOST', 'transmission')
    transmission_port = int(os.environ.get('TRANSMISSION_PORT', '9091'))
    transmission_user = os.environ.get('TRANSMISSION_USER', 'transmission')
    transmission_password = os.environ.get('TRANSMISSION_PASSWORD', 'transmission')
    
    print(f"?? Transmission: {transmission_host}:{transmission_port}")
    print(f"?? Credentials: {transmission_user}/{transmission_password}")
    print("=" * 50)
    
    # Wait for transmission port to be available
    if not wait_for_port(transmission_host, transmission_port):
        print("? Failed to connect to Transmission port")
        sys.exit(1)
    
    # Wait for transmission RPC to be ready
    if not wait_for_transmission(transmission_host, transmission_port, transmission_user, transmission_password):
        print("? Failed to connect to Transmission RPC")
        sys.exit(1)
    
    print("? All services are ready!")
    print("=" * 50)
    
    # Start the Flask application
    start_flask_app()

if __name__ == "__main__":
    main()