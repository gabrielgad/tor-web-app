"""
Utility Functions
Common helper functions used across the application
"""
import os
import time
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup


def format_size(size_bytes):
    """Convert bytes to human-readable format"""
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1

    return f"{size_bytes:.2f} {units[i]}"


def parse_size(size_str):
    """Convert a human-readable size string to bytes"""
    try:
        size_str = size_str.upper().replace(" ", "")
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
            'TB': 1024 * 1024 * 1024 * 1024
        }
        
        for unit, multiplier in multipliers.items():
            if unit in size_str:
                size_value = float(size_str.replace(unit, ""))
                return int(size_value * multiplier)
        
        # If no unit found, assume bytes
        return int(float(size_str))
        
    except (ValueError, TypeError):
        return 0


def create_magnet_link(info_hash, name, trackers=None):
    """Create a magnet link from info hash and name"""
    encoded_name = urllib.parse.quote(name)
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_name}"
    
    if trackers:
        for tracker in trackers:
            magnet_link += f"&tr={urllib.parse.quote(tracker)}"
    
    return magnet_link


def sanitize_filename(filename):
    """Sanitize filename for safe file system operations"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename


def get_file_list(directory):
    """Get list of files in directory with metadata"""
    try:
        files = []
        if not os.path.exists(directory):
            return files
            
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                file_stats = os.stat(file_path)
                files.append({
                    "name": filename,
                    "size": format_size(file_stats.st_size),
                    "size_bytes": file_stats.st_size,
                    "created": time.ctime(file_stats.st_ctime),
                    "modified": time.ctime(file_stats.st_mtime),
                    "path": file_path
                })
        
        # Sort by modification time, newest first
        files.sort(key=lambda x: x['size_bytes'], reverse=True)
        return files
        
    except Exception as e:
        print(f"Error listing files in {directory}: {e}")
        return []


def search_torrents_json_api(query, search_url):
    """Search torrents using JSON API (like ThePirateBay API)"""
    try:
        encoded_query = urllib.parse.quote(query)
        url = search_url.format(query=encoded_query)
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        results = response.json()
        processed_results = []
        
        for item in results:
            # Skip invalid results
            if not isinstance(item, dict) or item.get("id") == "0":
                continue
                
            processed_results.append({
                "id": item.get("id"),
                "name": item.get("name", "Unknown"),
                "info_hash": item.get("info_hash", ""),
                "size": format_size(int(item.get("size", 0))),
                "size_bytes": int(item.get("size", 0)),
                "seeders": int(item.get("seeders", 0)),
                "leechers": int(item.get("leechers", 0)),
                "added": item.get("added", "Unknown"),
                "category": item.get("category", "Unknown")
            })
        
        return processed_results
        
    except Exception as e:
        raise Exception(f"JSON API search failed: {str(e)}")


def search_torrents_html_scrape(query, search_url):
    """Search torrents using HTML scraping (generic implementation)"""
    try:
        encoded_query = urllib.parse.quote(query)
        url = search_url.format(query=encoded_query)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        processed_results = []
        
        # This is a generic example - would need customization for each site
        for row in soup.select('table tr'):
            columns = row.select('td')
            if len(columns) >= 4:
                name_link = columns[1].select_one('a')
                if name_link:
                    processed_results.append({
                        "id": len(processed_results) + 1,
                        "name": name_link.get_text().strip(),
                        "info_hash": extract_info_hash_from_link(name_link.get('href', '')),
                        "size": columns[2].get_text().strip(),
                        "size_bytes": parse_size(columns[2].get_text().strip()),
                        "seeders": safe_int(columns[3].get_text().strip()),
                        "leechers": safe_int(columns[4].get_text().strip()) if len(columns) > 4 else 0,
                        "added": columns[5].get_text().strip() if len(columns) > 5 else "Unknown"
                    })
        
        return processed_results
        
    except Exception as e:
        raise Exception(f"HTML scraping search failed: {str(e)}")


def extract_info_hash_from_link(url):
    """Extract info hash from magnet or torrent link"""
    try:
        if 'magnet:' in url:
            # Extract from magnet link
            match = re.search(r'btih:([a-fA-F0-9]{40})', url)
            if match:
                return match.group(1).upper()
        
        # Could add more extraction methods here
        return ""
    except:
        return ""


def safe_int(value, default=0):
    """Safely convert value to integer"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def validate_info_hash(info_hash):
    """Validate that info hash is a valid 40-character hex string"""
    if not info_hash:
        return False
    
    # Remove any whitespace and convert to uppercase
    info_hash = info_hash.strip().upper()
    
    # Check if it's exactly 40 characters and all hex
    if len(info_hash) != 40:
        return False
    
    try:
        int(info_hash, 16)  # Try to parse as hex
        return True
    except ValueError:
        return False


def get_default_trackers():
    """Get list of default torrent trackers"""
    return [
        "udp://tracker.openbittorrent.com:6969/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://9.rarbg.to:2710/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.cyberia.is:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.tiny-vps.com:6969/announce",
        "udp://retracker.lanta-net.ru:2710/announce"
    ]