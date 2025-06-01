"""
Transmission HTTP Client Module
Handles all communication with Transmission daemon
"""
import requests
import logging
import time
import os

logger = logging.getLogger(__name__)

class TransmissionHTTPClient:
    """Custom HTTP client for Transmission RPC"""
    
    def __init__(self, host=None, port=None, user=None, password=None):
        # Allow override from environment variables
        self.host = host or os.environ.get('TRANSMISSION_HOST', 'transmission')
        self.port = port or int(os.environ.get('TRANSMISSION_PORT', '9091'))
        self.user = user or os.environ.get('TRANSMISSION_USER', 'transmission')
        self.password = password or os.environ.get('TRANSMISSION_PASSWORD', 'transmission')
        
        self.url = f"http://{self.host}:{self.port}/transmission/rpc"
        self.session_id = None
        
        logger.info(f"Transmission client initialized: {self.host}:{self.port}")

    def _get_session_id(self):
        """Get the session ID from Transmission"""
        try:
            response = requests.post(self.url, auth=(self.user, self.password), timeout=10)
            if response.status_code == 409:
                self.session_id = response.headers.get('X-Transmission-Session-Id')
                logger.info(f"Got session ID: {self.session_id}")
                return self.session_id
            else:
                logger.error(f"Unexpected response getting session ID: {response.status_code}")
                raise Exception(f"Unexpected response: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to get session ID: {e}")
            raise Exception(f"Failed to get session ID: {e}")

    def _make_request(self, data, max_retries=3):
        """Make a request to Transmission with proper session handling"""
        for attempt in range(max_retries):
            try:
                if not self.session_id:
                    self._get_session_id()

                headers = {'X-Transmission-Session-Id': self.session_id}

                response = requests.post(
                    self.url,
                    json=data,
                    headers=headers,
                    auth=(self.user, self.password),
                    timeout=30
                )

                if response.status_code == 409:
                    # Session expired, get new one and retry
                    logger.info("Session expired, getting new session ID")
                    self._get_session_id()
                    headers['X-Transmission-Session-Id'] = self.session_id
                    response = requests.post(
                        self.url,
                        json=data,
                        headers=headers,
                        auth=(self.user, self.password),
                        timeout=30
                    )

                response.raise_for_status()
                return response.json()

            except Exception as e:
                logger.error(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise Exception(f"Request failed after {max_retries} attempts: {e}")
                time.sleep(1)  # Brief delay before retry

    def add_torrent(self, magnet_link, download_dir=None):
        """Add a torrent via magnet link"""
        data = {
            "method": "torrent-add",
            "arguments": {
                "filename": magnet_link
            }
        }

        if download_dir:
            data["arguments"]["download-dir"] = download_dir

        logger.info(f"Adding torrent: {magnet_link[:50]}... to {download_dir}")
        result = self._make_request(data)
        logger.info(f"Add torrent result: {result}")

        # Handle success cases
        if result.get("result") == "success":
            torrent_data = result.get("arguments", {})
            
            # New torrent added
            if "torrent-added" in torrent_data:
                return TransmissionTorrent(torrent_data["torrent-added"])
            
            # Torrent already exists
            elif "torrent-duplicate" in torrent_data:
                return TransmissionTorrent(torrent_data["torrent-duplicate"])

        # Handle error cases
        raise Exception(f"Failed to add torrent: {result}")

    def get_torrent(self, torrent_id):
        """Get torrent info by ID"""
        data = {
            "method": "torrent-get",
            "arguments": {
                "ids": [torrent_id],
                "fields": ["id", "name", "status", "percentDone", "downloadDir", "error", "errorString", "rateDownload", "rateUpload"]
            }
        }

        result = self._make_request(data)

        if result.get("result") == "success" and result.get("arguments", {}).get("torrents"):
            torrent_data = result["arguments"]["torrents"][0]
            return TransmissionTorrent(torrent_data)

        raise Exception(f"Torrent {torrent_id} not found")

    def list_torrents(self):
        """List all torrents"""
        data = {
            "method": "torrent-get",
            "arguments": {
                "fields": ["id", "name", "status", "percentDone", "downloadDir", "error", "errorString", "rateDownload", "rateUpload"]
            }
        }

        result = self._make_request(data)

        if result.get("result") == "success":
            torrents = result.get("arguments", {}).get("torrents", [])
            return [TransmissionTorrent(t) for t in torrents]

        return []

    def remove_torrent(self, torrent_id, delete_data=False):
        """Remove a torrent"""
        data = {
            "method": "torrent-remove",
            "arguments": {
                "ids": [torrent_id],
                "delete-local-data": delete_data
            }
        }

        logger.info(f"Removing torrent {torrent_id}, delete_data={delete_data}")
        result = self._make_request(data)
        
        if result.get("result") == "success":
            logger.info(f"Successfully removed torrent {torrent_id}")
            return True
        else:
            logger.error(f"Failed to remove torrent {torrent_id}: {result}")
            return False

    def start_torrent(self, torrent_id):
        """Start a torrent"""
        data = {
            "method": "torrent-start",
            "arguments": {
                "ids": [torrent_id]
            }
        }

        logger.info(f"Starting torrent {torrent_id}")
        result = self._make_request(data)
        
        if result.get("result") == "success":
            logger.info(f"Successfully started torrent {torrent_id}")
            return True
        else:
            logger.error(f"Failed to start torrent {torrent_id}: {result}")
            return False

    def stop_torrent(self, torrent_id):
        """Stop a torrent"""
        data = {
            "method": "torrent-stop",
            "arguments": {
                "ids": [torrent_id]
            }
        }

        logger.info(f"Stopping torrent {torrent_id}")
        result = self._make_request(data)
        
        if result.get("result") == "success":
            logger.info(f"Successfully stopped torrent {torrent_id}")
            return True
        else:
            logger.error(f"Failed to stop torrent {torrent_id}: {result}")
            return False

    def verify_torrent(self, torrent_id):
        """Verify a torrent's data"""
        data = {
            "method": "torrent-verify",
            "arguments": {
                "ids": [torrent_id]
            }
        }

        logger.info(f"Verifying torrent {torrent_id}")
        result = self._make_request(data)
        
        if result.get("result") == "success":
            logger.info(f"Successfully started verification for torrent {torrent_id}")
            return True
        else:
            logger.error(f"Failed to verify torrent {torrent_id}: {result}")
            return False

    def set_torrent_location(self, torrent_id, location, move=False):
        """Set torrent download location"""
        data = {
            "method": "torrent-set-location",
            "arguments": {
                "ids": [torrent_id],
                "location": location,
                "move": move
            }
        }

        logger.info(f"Setting torrent {torrent_id} location to {location}, move={move}")
        result = self._make_request(data)
        
        if result.get("result") == "success":
            logger.info(f"Successfully set location for torrent {torrent_id}")
            return True
        else:
            logger.error(f"Failed to set location for torrent {torrent_id}: {result}")
            return False

    def session_stats(self):
        """Get session statistics"""
        data = {"method": "session-stats"}
        result = self._make_request(data)
        
        if result.get("result") == "success":
            return result.get("arguments", {})
        
        raise Exception(f"Failed to get session stats: {result}")

    def session_get(self):
        """Get session configuration"""
        data = {"method": "session-get"}
        result = self._make_request(data)
        
        if result.get("result") == "success":
            return result.get("arguments", {})
        
        raise Exception(f"Failed to get session config: {result}")

    def test_connection(self):
        """Test if the connection to Transmission is working"""
        try:
            stats = self.session_stats()
            logger.info("Transmission connection test successful")
            return True, stats
        except Exception as e:
            logger.error(f"Transmission connection test failed: {e}")
            return False, str(e)


class TransmissionTorrent:
    """Simple torrent object to represent transmission torrent data"""
    
    def __init__(self, data):
        self.id = data.get("id")
        self.name = data.get("name", "")
        self.status = self._convert_status(data.get("status", 0))
        self.progress = data.get("percentDone", 0) * 100  # Convert to percentage
        self.download_dir = data.get("downloadDir", "")
        self.error = data.get("error", 0)
        self.error_string = data.get("errorString", "")
        self.download_rate = data.get("rateDownload", 0)
        self.upload_rate = data.get("rateUpload", 0)

    def _convert_status(self, status_code):
        """Convert numeric status to string"""
        status_map = {
            0: "stopped",
            1: "check pending",
            2: "checking",
            3: "download pending", 
            4: "downloading",
            5: "seed pending",
            6: "seeding"
        }
        return status_map.get(status_code, "unknown")

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "progress": round(self.progress, 2),
            "download_dir": self.download_dir,
            "error": self.error,
            "error_string": self.error_string,
            "download_rate": self.download_rate,
            "upload_rate": self.upload_rate
        }


def get_transmission_client():
    """Factory function to create transmission client"""
    try:
        client = TransmissionHTTPClient()
        success, result = client.test_connection()
        
        if success:
            logger.info("Successfully connected to Transmission")
            return client
        else:
            logger.error(f"Failed to connect to Transmission: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating transmission client: {e}")
        return None