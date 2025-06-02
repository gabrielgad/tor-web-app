"""
API Routes for Torrent Search and Download Manager
Separated from main Flask application for better organization
"""
import os
import time
import threading
import logging
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user

# Import your existing utility functions
try:
    from .transmission_client import get_transmission_client  # Your existing HTTP client
    from .utils import (
        format_size, create_magnet_link, validate_info_hash, 
        get_default_trackers, get_file_list, search_torrents_json_api,
        search_torrents_html_scrape, extract_info_hash_from_link,
        safe_int, parse_size, sanitize_filename
    )
except ImportError:
    # Handle relative imports when running directly
    from transmission_client import get_transmission_client  # Your existing HTTP client
    from utils import (
        format_size, create_magnet_link, validate_info_hash, 
        get_default_trackers, get_file_list, search_torrents_json_api,
        search_torrents_html_scrape, extract_info_hash_from_link,
        safe_int, parse_size, sanitize_filename
    )

# Set up logging
logger = logging.getLogger(__name__)

# Create Blueprint for API routes
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Store active downloads (this could be moved to a database later)
active_downloads = {}

# Site configurations for multi-site support
TORRENT_SITES = {
    'piratebay': {
        'name': 'The Pirate Bay',
        'search_url': 'https://apibay.org/q.php?q={query}',
        'type': 'json_api',
        'enabled': True
    },
    '1337x': {
        'name': '1337x',
        'search_url': 'https://1337x.to/search/{query}/1/',
        'type': 'html_scrape',
        'enabled': True
    },
    'gog-games': {
        'name': 'GOG Games',
        'search_url': 'https://gog-games.to/search?query={query}',
        'type': 'html_scrape',
        'enabled': True
    },
    'fitgirl': {
        'name': 'FitGirl Repacks',
        'search_url': 'https://fitgirl-repacks.site/?s={query}',
        'type': 'html_scrape',
        'enabled': True
    },
    'steamrip': {
        'name': 'SteamRIP',
        'search_url': 'https://steamrip.com/?s={query}',
        'type': 'html_scrape',
        'enabled': True
    }
}

# ============================================================================
# Health and Status API
# ============================================================================

@api_bp.route('/health', methods=['GET'])
@login_required
def health_check():
    """Check the health of the application and its dependencies"""
    health_status = {
        "app": "healthy",
        "transmission": "unknown",
        "download_dir": "unknown",
        "timestamp": time.time()
    }
    
    # Get config from main app
    config = current_app.config.get('TORRENT_CONFIG', {})
    
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
            health_status["transmission_host"] = f"{config.get('transmission', {}).get('host', 'unknown')}:{config.get('transmission', {}).get('port', 'unknown')}"
        else:
            health_status["transmission"] = "connection failed"
    except Exception as e:
        health_status["transmission"] = f"error: {str(e)}"
    
    # Check download directory
    try:
        download_dir = config.get("download_dir", "")
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
# Search API - Multi-Site Support
# ============================================================================

@api_bp.route('/search', methods=['GET'])
@login_required
def search():
    """Search torrents across multiple sites"""
    query = request.args.get('q', '').strip()
    site = request.args.get('site', 'piratebay').strip()
    
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    if site not in TORRENT_SITES:
        return jsonify({"error": f"Unsupported site: {site}"}), 400
    
    site_config = TORRENT_SITES[site]
    if not site_config.get('enabled', False):
        return jsonify({"error": f"Site {site} is currently disabled"}), 400

    try:
        logger.info(f"Searching {site_config['name']} for: {query}")
        
        # Route to appropriate search function based on site type
        if site_config['type'] == 'json_api':
            results = search_json_api(query, site_config['search_url'])
        elif site_config['type'] == 'html_scrape':
            results = search_html_scrape(query, site, site_config['search_url'])
        else:
            return jsonify({"error": f"Invalid search type for site: {site}"}), 500

        logger.info(f"Found {len(results)} results on {site_config['name']} for query: {query}")
        return jsonify({
            "results": results, 
            "query": query, 
            "site": site,
            "site_name": site_config['name']
        })

    except Exception as e:
        logger.error(f"Search error for query '{query}' on {site}: {str(e)}")
        return jsonify({"error": f"Search failed on {site_config['name']}: {str(e)}"}), 500

def search_json_api(query, search_url):
    """Search using JSON API (PirateBay) - uses existing utils function"""
    try:
        results = search_torrents_json_api(query, search_url)
        
        # Convert to expected format for multi-site compatibility
        formatted_results = []
        for item in results:
            formatted_results.append({
                'name': item.get('name', 'Unknown'),
                'size': item.get('size', 'Unknown'),
                'seeders': str(item.get('seeders', 0)),
                'leechers': str(item.get('leechers', 0)),
                'info_hash': item.get('info_hash', ''),
                'magnet': create_magnet_link(item.get('info_hash', ''), item.get('name', ''), get_default_trackers()),
                'added': item.get('added', 'Unknown'),
                'category': get_category_name(item.get('category', '0'))
            })
        
        return formatted_results
    except Exception as e:
        logger.error(f"JSON API search error: {e}")
        return []

def get_category_name(category_id):
    """Convert PirateBay category ID to name"""
    categories = {
        '100': 'Audio',
        '200': 'Video', 
        '300': 'Applications',
        '400': 'Games',
        '500': 'Porn',
        '600': 'Other'
    }
    return categories.get(str(category_id), 'Other')

def search_html_scrape(query, site, search_url):
    """Search using HTML scraping for various sites"""
    import requests
    from bs4 import BeautifulSoup
    import urllib.parse
    import time
    
    try:
        # Format the search URL
        formatted_url = search_url.format(query=urllib.parse.quote_plus(query))
        logger.info(f"Scraping URL: {formatted_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        # Add small delay to be respectful
        time.sleep(1)
        
        response = requests.get(formatted_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Site-specific parsing
        if site == '1337x':
            return parse_1337x(soup, formatted_url)
        elif site == 'gog-games':
            return parse_gog_games(soup, formatted_url)
        elif site == 'fitgirl':
            return parse_fitgirl(soup, formatted_url)
        elif site == 'steamrip':
            return parse_steamrip(soup, formatted_url)
        else:
            return []
            
    except Exception as e:
        logger.error(f"HTML scraping error for {site}: {str(e)}")
        return []

def parse_1337x(soup, base_url):
    """Parse 1337x search results"""
    results = []
    try:
        logger.info("Parsing 1337x search results")
        
        # Find the results table - 1337x has a specific table structure
        table = soup.find('table', class_='table-list') or soup.find('table')
        if not table:
            logger.warning("No results table found on 1337x")
            return results
        
        rows = table.find_all('tr')[1:]  # Skip header row
        logger.info(f"Found {len(rows)} rows in 1337x table")
        
        for row in rows[:15]:  # Limit to first 15 results
            try:
                cells = row.find_all('td')
                if len(cells) < 5:
                    continue
                
                # 1337x table structure: name, seeders, leechers, date, size, uploader
                name_cell = cells[0]
                seeders_cell = cells[1] if len(cells) > 1 else None
                leechers_cell = cells[2] if len(cells) > 2 else None
                date_cell = cells[3] if len(cells) > 3 else None
                size_cell = cells[4] if len(cells) > 4 else None
                
                # Extract name and detail URL
                name_links = name_cell.find_all('a')
                detail_link = None
                name = "Unknown"
                
                for link in name_links:
                    if link.get('href', '').startswith('/torrent/'):
                        detail_link = link
                        name = link.get_text(strip=True)
                        break
                
                if not detail_link or not name:
                    continue
                
                detail_url = f"https://1337x.to{detail_link['href']}"
                
                # Extract other details
                seeders = seeders_cell.get_text(strip=True) if seeders_cell else '0'
                leechers = leechers_cell.get_text(strip=True) if leechers_cell else '0'
                size = size_cell.get_text(strip=True) if size_cell else 'Unknown'
                added = date_cell.get_text(strip=True) if date_cell else 'Unknown'
                
                # Clean up extracted data
                try:
                    seeders = int(seeders) if seeders.isdigit() else 0
                    leechers = int(leechers) if leechers.isdigit() else 0
                except:
                    seeders = 0
                    leechers = 0
                
                # Try to extract magnet link from detail page
                magnet = extract_1337x_magnet(detail_url)
                
                if magnet:
                    results.append({
                        'name': name,
                        'size': size,
                        'seeders': str(seeders),
                        'leechers': str(leechers),
                        'magnet': magnet,
                        'info_hash': extract_info_hash_from_link(magnet),
                        'url': detail_url,
                        'added': added,
                        'category': 'General'
                    })
                    
            except Exception as e:
                logger.warning(f"Error parsing 1337x row: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error parsing 1337x results: {e}")
    
    logger.info(f"Successfully parsed {len(results)} results from 1337x")
    return results

def parse_gog_games(soup, base_url):
    """Parse GOG Games search results"""
    results = []
    try:
        logger.info("Parsing GOG Games search results")
        
        # GOG Games typically uses article/post structure
        # Look for common game post selectors
        game_items = (
            soup.find_all('article') or 
            soup.find_all('div', class_=['post', 'game-item', 'entry', 'product']) or
            soup.find_all('div', attrs={'class': lambda x: x and 'game' in x.lower()}) or
            soup.find_all('h2') or soup.find_all('h3')
        )
        
        logger.info(f"Found {len(game_items)} potential game items on GOG Games")
        
        for item in game_items[:10]:  # Limit to first 10 results
            try:
                # Try different ways to find the title and link
                title_elem = None
                link_url = None
                
                # Method 1: Direct link in the item
                if item.name in ['h2', 'h3']:
                    title_elem = item
                    link_elem = item.find('a')
                    if link_elem:
                        link_url = link_elem.get('href')
                else:
                    # Method 2: Find title within the item
                    title_elem = (
                        item.find('h2') or item.find('h3') or item.find('h1') or
                        item.find('a', class_=['title', 'game-title', 'entry-title']) or
                        item.find('a')
                    )
                    
                    if title_elem and title_elem.get('href'):
                        link_url = title_elem.get('href')
                    elif title_elem:
                        link_elem = title_elem.find('a')
                        if link_elem:
                            link_url = link_elem.get('href')
                
                if not title_elem:
                    continue
                    
                name = title_elem.get_text(strip=True)
                if not name or len(name) < 3:
                    continue
                
                # Clean up the name
                name = name.replace('Download', '').replace('Free', '').strip()
                
                # Ensure we have a full URL
                if link_url:
                    if link_url.startswith('/'):
                        link_url = f"https://gog-games.to{link_url}"
                    elif not link_url.startswith('http'):
                        link_url = f"https://gog-games.to/{link_url}"
                
                # Try to extract magnet from the post/detail page
                magnet = None
                if link_url:
                    magnet = extract_gog_magnet(link_url)
                
                # If we found a magnet, add the result
                if magnet:
                    results.append({
                        'name': name,
                        'size': 'Varies',
                        'seeders': 'N/A',
                        'leechers': 'N/A',
                        'magnet': magnet,
                        'info_hash': extract_info_hash_from_link(magnet),
                        'url': link_url,
                        'category': 'Games',
                        'added': 'Recent'
                    })
                    
            except Exception as e:
                logger.warning(f"Error parsing GOG Games item: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error parsing GOG Games results: {e}")
    
    logger.info(f"Successfully parsed {len(results)} results from GOG Games")
    return results

def parse_fitgirl(soup, base_url):
    """Parse FitGirl Repacks search results"""
    results = []
    try:
        logger.info("Parsing FitGirl Repacks search results")
        
        # FitGirl uses WordPress structure - look for posts
        posts = (
            soup.find_all('article') or 
            soup.find_all('div', class_=['post', 'entry', 'hentry']) or
            soup.find_all('div', attrs={'class': lambda x: x and 'post' in x.lower()})
        )
        
        # If no articles found, try alternative selectors
        if not posts:
            posts = soup.find_all('h2') + soup.find_all('h3')
        
        logger.info(f"Found {len(posts)} potential posts on FitGirl")
        
        for post in posts[:8]:  # Limit to first 8 results
            try:
                # Find title and link
                title_elem = None
                post_url = None
                
                if post.name in ['h2', 'h3']:
                    title_elem = post
                    link_elem = post.find('a')
                    if link_elem:
                        post_url = link_elem.get('href')
                        title_elem = link_elem
                else:
                    # Look for title within post
                    title_elem = (
                        post.find('h2') or post.find('h3') or post.find('h1') or
                        post.find('a', class_=['post-title', 'entry-title'])
                    )
                    
                    if title_elem:
                        link_elem = title_elem.find('a') if title_elem.name != 'a' else title_elem
                        if link_elem:
                            post_url = link_elem.get('href')
                
                if not title_elem:
                    continue
                    
                name = title_elem.get_text(strip=True)
                if not name or len(name) < 5:
                    continue
                
                # Clean up the title (remove common prefixes/suffixes)
                name = name.replace('FitGirl Repack', '').replace('Repack', '').strip()
                name = name.replace('Download', '').replace('Free', '').strip()
                
                # Skip if it doesn't look like a game title
                if any(skip in name.lower() for skip in ['page', 'comment', 'reply', 'search']):
                    continue
                
                # Ensure full URL
                if post_url:
                    if post_url.startswith('/'):
                        post_url = f"https://fitgirl-repacks.site{post_url}"
                    elif not post_url.startswith('http'):
                        post_url = f"https://fitgirl-repacks.site/{post_url}"
                
                # Try to extract magnet from post content
                magnet = None
                if post_url:
                    magnet = extract_fitgirl_magnet(post_url)
                
                # Also try to find magnet in current page content
                if not magnet:
                    magnet_links = post.find_all('a', href=lambda x: x and x.startswith('magnet:'))
                    if magnet_links:
                        magnet = magnet_links[0]['href']
                
                if magnet:
                    results.append({
                        'name': name,
                        'size': 'Compressed',
                        'seeders': 'N/A',
                        'leechers': 'N/A',
                        'magnet': magnet,
                        'info_hash': extract_info_hash_from_link(magnet),
                        'url': post_url,
                        'category': 'Repacks',
                        'added': 'Recent'
                    })
                    
            except Exception as e:
                logger.warning(f"Error parsing FitGirl post: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error parsing FitGirl results: {e}")
    
    logger.info(f"Successfully parsed {len(results)} results from FitGirl")
    return results

def parse_steamrip(soup, base_url):
    """Parse SteamRIP search results"""
    results = []
    try:
        logger.info("Parsing SteamRIP search results")
        
        # SteamRIP structure - look for game posts
        game_posts = (
            soup.find_all('article') or 
            soup.find_all('div', class_=['post', 'game', 'entry', 'product']) or
            soup.find_all('div', attrs={'class': lambda x: x and ('game' in x.lower() or 'post' in x.lower())})
        )
        
        # Alternative: look for title headers
        if not game_posts:
            game_posts = soup.find_all('h2') + soup.find_all('h3')
        
        logger.info(f"Found {len(game_posts)} potential posts on SteamRIP")
        
        for post in game_posts[:8]:  # Limit to first 8 results
            try:
                # Find title and link
                title_elem = None
                post_url = None
                
                if post.name in ['h2', 'h3']:
                    title_elem = post
                    link_elem = post.find('a')
                    if link_elem:
                        post_url = link_elem.get('href')
                        title_elem = link_elem
                else:
                    # Look for title within post
                    title_elem = (
                        post.find('h2') or post.find('h3') or post.find('h1') or
                        post.find('a', class_=['title', 'game-title', 'entry-title', 'post-title'])
                    )
                    
                    if title_elem:
                        link_elem = title_elem.find('a') if title_elem.name != 'a' else title_elem
                        if link_elem:
                            post_url = link_elem.get('href')
                
                if not title_elem:
                    continue
                    
                name = title_elem.get_text(strip=True)
                if not name or len(name) < 5:
                    continue
                
                # Clean up the title
                name = name.replace('SteamRIP', '').replace('Download', '').replace('Free', '').strip()
                name = name.replace('Game', '').replace('PC', '').strip()
                
                # Skip non-game content
                if any(skip in name.lower() for skip in ['page', 'comment', 'reply', 'search', 'home']):
                    continue
                
                # Ensure full URL
                if post_url:
                    if post_url.startswith('/'):
                        post_url = f"https://steamrip.com{post_url}"
                    elif not post_url.startswith('http'):
                        post_url = f"https://steamrip.com/{post_url}"
                
                # Try to extract magnet from post
                magnet = None
                if post_url:
                    magnet = extract_steamrip_magnet(post_url)
                
                # Also try to find magnet in current page content
                if not magnet:
                    magnet_links = post.find_all('a', href=lambda x: x and x.startswith('magnet:'))
                    if magnet_links:
                        magnet = magnet_links[0]['href']
                
                if magnet:
                    results.append({
                        'name': name,
                        'size': 'Varies',
                        'seeders': 'N/A',
                        'leechers': 'N/A',
                        'magnet': magnet,
                        'info_hash': extract_info_hash_from_link(magnet),
                        'url': post_url,
                        'category': 'Games',
                        'added': 'Recent'
                    })
                    
            except Exception as e:
                logger.warning(f"Error parsing SteamRIP post: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error parsing SteamRIP results: {e}")
    
    logger.info(f"Successfully parsed {len(results)} results from SteamRIP")
    return results

# Helper functions for magnet extraction
def extract_1337x_magnet(detail_url):
    """Extract magnet link from 1337x detail page"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        import time
        
        logger.info(f"Extracting magnet from 1337x: {detail_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://1337x.to/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        # Add delay to avoid being blocked
        time.sleep(2)
        
        response = requests.get(detail_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Method 1: Look for magnet link in HTML
        magnet_match = re.search(r'magnet:\?[^"\'<>\s]+', response.text)
        if magnet_match:
            magnet = magnet_match.group(0)
            logger.info(f"Found magnet via regex: {magnet[:50]}...")
            return magnet
        
        # Method 2: Parse HTML and look for magnet links
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for direct magnet links
        magnet_links = soup.find_all('a', href=lambda x: x and x.startswith('magnet:'))
        if magnet_links:
            magnet = magnet_links[0]['href']
            logger.info(f"Found magnet via soup: {magnet[:50]}...")
            return magnet
        
        # Method 3: Look for download buttons/links that might contain magnet
        download_links = soup.find_all('a', class_=['btn', 'download', 'magnet'])
        for link in download_links:
            href = link.get('href', '')
            if href.startswith('magnet:'):
                logger.info(f"Found magnet via download button: {href[:50]}...")
                return href
        
        # Method 4: Look in JavaScript or hidden elements
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                magnet_match = re.search(r'magnet:\?[^"\'<>\s]+', script.string)
                if magnet_match:
                    magnet = magnet_match.group(0)
                    logger.info(f"Found magnet in script: {magnet[:50]}...")
                    return magnet
        
        logger.warning(f"No magnet found for 1337x URL: {detail_url}")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting 1337x magnet from {detail_url}: {e}")
        return None

def extract_gog_magnet(detail_url):
    """Extract magnet from GOG Games detail page"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        import time
        
        if not detail_url:
            return None
            
        logger.info(f"Extracting magnet from GOG Games: {detail_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        time.sleep(1)
        
        response = requests.get(detail_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Method 1: Direct regex search
        magnet_match = re.search(r'magnet:\?[^"\'<>\s]+', response.text)
        if magnet_match:
            magnet = magnet_match.group(0)
            logger.info(f"Found GOG magnet via regex: {magnet[:50]}...")
            return magnet
        
        # Method 2: Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for magnet links
        magnet_links = soup.find_all('a', href=lambda x: x and x.startswith('magnet:'))
        if magnet_links:
            magnet = magnet_links[0]['href']
            logger.info(f"Found GOG magnet via soup: {magnet[:50]}...")
            return magnet
        
        # Method 3: Look for download sections
        download_sections = soup.find_all(['div', 'section', 'p'], 
                                        attrs={'class': lambda x: x and any(term in x.lower() for term in ['download', 'torrent', 'magnet'])})
        
        for section in download_sections:
            links = section.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                if href.startswith('magnet:'):
                    logger.info(f"Found GOG magnet in download section: {href[:50]}...")
                    return href
        
        logger.warning(f"No magnet found for GOG Games URL: {detail_url}")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting GOG magnet from {detail_url}: {e}")
        return None

def extract_fitgirl_magnet(detail_url):
    """Extract magnet from FitGirl post"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        import time
        
        if not detail_url:
            return None
            
        logger.info(f"Extracting magnet from FitGirl: {detail_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        time.sleep(1)
        
        response = requests.get(detail_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Method 1: Direct regex search
        magnet_match = re.search(r'magnet:\?[^"\'<>\s]+', response.text)
        if magnet_match:
            magnet = magnet_match.group(0)
            logger.info(f"Found FitGirl magnet via regex: {magnet[:50]}...")
            return magnet
        
        # Method 2: Parse HTML and look for post content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for magnet links
        magnet_links = soup.find_all('a', href=lambda x: x and x.startswith('magnet:'))
        if magnet_links:
            magnet = magnet_links[0]['href']
            logger.info(f"Found FitGirl magnet via soup: {magnet[:50]}...")
            return magnet
        
        # Method 3: Look in post content areas
        content_areas = soup.find_all(['div', 'article', 'section'], 
                                    attrs={'class': lambda x: x and any(term in x.lower() for term in ['content', 'post', 'entry', 'article'])})
        
        for area in content_areas:
            # Look for text that might contain encoded magnets or download info
            text_content = area.get_text()
            magnet_match = re.search(r'magnet:\?[^"\'<>\s]+', text_content)
            if magnet_match:
                magnet = magnet_match.group(0)
                logger.info(f"Found FitGirl magnet in content: {magnet[:50]}...")
                return magnet
        
        logger.warning(f"No magnet found for FitGirl URL: {detail_url}")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting FitGirl magnet from {detail_url}: {e}")
        return None

def extract_steamrip_magnet(detail_url):
    """Extract magnet from SteamRIP post"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        import time
        
        if not detail_url:
            return None
            
        logger.info(f"Extracting magnet from SteamRIP: {detail_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        time.sleep(1)
        
        response = requests.get(detail_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Method 1: Direct regex search
        magnet_match = re.search(r'magnet:\?[^"\'<>\s]+', response.text)
        if magnet_match:
            magnet = magnet_match.group(0)
            logger.info(f"Found SteamRIP magnet via regex: {magnet[:50]}...")
            return magnet
        
        # Method 2: Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for magnet links
        magnet_links = soup.find_all('a', href=lambda x: x and x.startswith('magnet:'))
        if magnet_links:
            magnet = magnet_links[0]['href']
            logger.info(f"Found SteamRIP magnet via soup: {magnet[:50]}...")
            return magnet
        
        # Method 3: Look for download areas
        download_areas = soup.find_all(['div', 'section', 'p'], 
                                     attrs={'class': lambda x: x and any(term in x.lower() for term in ['download', 'link', 'torrent'])})
        
        for area in download_areas:
            links = area.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                if href.startswith('magnet:'):
                    logger.info(f"Found SteamRIP magnet in download area: {href[:50]}...")
                    return href
        
        # Method 4: Look in all text content
        all_text = soup.get_text()
        magnet_match = re.search(r'magnet:\?[^"\'<>\s]+', all_text)
        if magnet_match:
            magnet = magnet_match.group(0)
            logger.info(f"Found SteamRIP magnet in text: {magnet[:50]}...")
            return magnet
        
        logger.warning(f"No magnet found for SteamRIP URL: {detail_url}")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting SteamRIP magnet from {detail_url}: {e}")
        return None

def extract_hash_from_magnet(magnet_link):
    """Extract info hash from magnet link"""
    if not magnet_link or 'magnet:' not in magnet_link:
        return None
    try:
        import re
        # Look for xt=urn:btih: followed by 32 or 40 character hash
        hash_match = re.search(r'xt=urn:btih:([a-fA-F0-9]{32,40})', magnet_link)
        if hash_match:
            return hash_match.group(1).lower()
        
        # Alternative pattern without urn:btih:
        hash_match = re.search(r'btih:([a-fA-F0-9]{32,40})', magnet_link)
        if hash_match:
            return hash_match.group(1).lower()
            
        return None
    except Exception as e:
        logger.error(f"Error extracting hash from magnet: {e}")
        return None

def search_torrents_json_api(query, search_url):
    """Search torrents using JSON API (for PirateBay)"""
    import requests
    import time
    
    try:
        # Format URL and make request
        formatted_url = search_url.format(query=query)
        logger.info(f"Searching JSON API: {formatted_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(formatted_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        # PirateBay API response format
        if isinstance(data, list):
            for item in data[:20]:  # Limit to 20 results
                try:
                    if item.get('name') and item.get('info_hash'):
                        # Convert size from bytes to human readable
                        size = format_size_bytes(int(item.get('size', 0)))
                        
                        # Format date
                        added_date = 'Unknown'
                        if item.get('added'):
                            try:
                                added_timestamp = int(item.get('added'))
                                added_date = time.strftime('%Y-%m-%d', time.localtime(added_timestamp))
                            except:
                                pass
                        
                        results.append({
                            'name': item['name'],
                            'size': size,
                            'seeders': str(item.get('seeders', 0)),
                            'leechers': str(item.get('leechers', 0)),
                            'info_hash': item['info_hash'],
                            'magnet': create_magnet_link(item['info_hash'], item['name']),
                            'added': added_date,
                            'category': get_category_name(item.get('category', '0'))
                        })
                except Exception as e:
                    logger.warning(f"Error parsing PirateBay result: {e}")
                    continue
        
        logger.info(f"Successfully parsed {len(results)} results from JSON API")
        return results
        
    except Exception as e:
        logger.error(f"JSON API search error: {e}")
        return []

def format_size_bytes(size_bytes):
    """Convert bytes to human readable format"""
    if not size_bytes:
        return "Unknown"
    
    try:
        size_bytes = int(size_bytes)
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    except:
        return "Unknown"

def get_category_name(category_id):
    """Convert PirateBay category ID to name"""
    categories = {
        '100': 'Audio',
        '200': 'Video', 
        '300': 'Applications',
        '400': 'Games',
        '500': 'Porn',
        '600': 'Other'
    }
    return categories.get(str(category_id), 'Other')

def create_magnet_link(info_hash, name, trackers=None):
    """Create a magnet link from info hash and name"""
    if not info_hash or not name:
        return None
        
    try:
        import urllib.parse
        encoded_name = urllib.parse.quote(name)
        magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_name}"
        
        # Add default trackers if not provided
        if not trackers:
            trackers = get_default_trackers()
        
        for tracker in trackers:
            magnet += f"&tr={urllib.parse.quote(tracker)}"
        
        return magnet
    except Exception as e:
        logger.error(f"Error creating magnet link: {e}")
        return None

def get_default_trackers():
    """Get list of default torrent trackers"""
    return [
        'udp://tracker.openbittorrent.com:80',
        'udp://tracker.publicbt.com:80',
        'udp://tracker.istole.it:6969',
        'udp://open.demonii.com:1337',
        'udp://tracker.coppersurfer.tk:6969',
        'udp://exodus.desync.com:6969'
    ]

def validate_info_hash(info_hash):
    """Validate if a string is a valid info hash"""
    if not info_hash:
        return False
    try:
        import re
        # Should be 32 or 40 character hex string
        return bool(re.match(r'^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}

# ============================================================================
# Downloads & Torrents API
# ============================================================================

@api_bp.route('/download', methods=['POST'])
@login_required
def download_torrent():
    """Add a torrent for download"""
    data = request.json
    logger.info(f"[DOWNLOAD] Received download request: {data}")

    if not data or 'info_hash' not in data or 'name' not in data:
        return jsonify({"error": "Missing required fields: info_hash and name"}), 400

    info_hash_or_magnet = data['info_hash'].strip()
    name = data['name'].strip()
    site = data.get('site', 'unknown')
    
    # Handle both info hashes and full magnet links
    if info_hash_or_magnet.startswith('magnet:'):
        magnet_link = info_hash_or_magnet
        info_hash = extract_hash_from_magnet(magnet_link)
    else:
        info_hash = info_hash_or_magnet
        if not validate_info_hash(info_hash):
            return jsonify({"error": "Invalid info hash format"}), 400
        magnet_link = create_magnet_link(info_hash, name, get_default_trackers())

    download_id = str(int(time.time() * 1000))

    try:
        client = get_transmission_client()
        if not client:
            logger.error("[DOWNLOAD] Failed to connect to torrent client")
            return jsonify({"error": "Failed to connect to torrent client."}), 500

        logger.info(f"[DOWNLOAD] Created magnet link: {magnet_link[:100]}...")

        # Use the exact same download path that Transmission uses
        download_path = "/data/downloads"  # This is the path inside Transmission container
        
        active_downloads[download_id] = {
            "name": name,
            "info_hash": info_hash,
            "status": "starting",
            "progress": 0,
            "started_at": time.time(),
            "started_by": current_user.username,
            "site": site
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

@api_bp.route('/current-torrents', methods=['GET'])
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

@api_bp.route('/torrent/remove', methods=['POST'])
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

@api_bp.route('/torrent/start', methods=['POST'])
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

@api_bp.route('/torrent/pause', methods=['POST'])
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
# File Management API
# ============================================================================

@api_bp.route('/files', methods=['GET'])
@login_required
def list_files():
    """List all downloaded files"""
    try:
        files = []
        config = current_app.config.get('TORRENT_CONFIG', {})
        download_dir = config.get("download_dir", "")
        
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

@api_bp.route('/files/delete', methods=['POST'])
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
        
        config = current_app.config.get('TORRENT_CONFIG', {})
        download_dir = config.get("download_dir", "")
        full_path = os.path.join(download_dir, safe_path)
        
        if not full_path.startswith(os.path.abspath(download_dir)):
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

# ============================================================================
# Debug and Utility API
# ============================================================================

@api_bp.route('/debug/downloads', methods=['GET'])
@login_required
def debug_downloads():
    """Debug endpoint to see active downloads"""
    config = current_app.config.get('TORRENT_CONFIG', {})
    return jsonify({
        "active_downloads": active_downloads,
        "active_downloads_count": len(active_downloads),
        "timestamp": time.time(),
        "supported_sites": list(TORRENT_SITES.keys()),
        "config_paths": {
            "download_dir": config.get("download_dir", ""),
            "temp_dir": config.get("temp_dir", "")
        }
    })

@api_bp.route('/sites', methods=['GET'])
@login_required
def get_sites():
    """Get available torrent sites"""
    return jsonify({
        "sites": TORRENT_SITES,
        "default": "piratebay"
    })
, info_hash))
    except:
        return False

# ============================================================================
# Downloads & Torrents API
# ============================================================================

@api_bp.route('/download', methods=['POST'])
@login_required
def download_torrent():
    """Add a torrent for download"""
    data = request.json
    logger.info(f"[DOWNLOAD] Received download request: {data}")

    if not data or 'info_hash' not in data or 'name' not in data:
        return jsonify({"error": "Missing required fields: info_hash and name"}), 400

    info_hash_or_magnet = data['info_hash'].strip()
    name = data['name'].strip()
    site = data.get('site', 'unknown')
    
    # Handle both info hashes and full magnet links
    if info_hash_or_magnet.startswith('magnet:'):
        magnet_link = info_hash_or_magnet
        info_hash = extract_hash_from_magnet(magnet_link)
    else:
        info_hash = info_hash_or_magnet
        if not validate_info_hash(info_hash):
            return jsonify({"error": "Invalid info hash format"}), 400
        magnet_link = create_magnet_link(info_hash, name, get_default_trackers())

    download_id = str(int(time.time() * 1000))

    try:
        client = get_transmission_client()
        if not client:
            logger.error("[DOWNLOAD] Failed to connect to torrent client")
            return jsonify({"error": "Failed to connect to torrent client."}), 500

        logger.info(f"[DOWNLOAD] Created magnet link: {magnet_link[:100]}...")

        # Use the exact same download path that Transmission uses
        download_path = "/data/downloads"  # This is the path inside Transmission container
        
        active_downloads[download_id] = {
            "name": name,
            "info_hash": info_hash,
            "status": "starting",
            "progress": 0,
            "started_at": time.time(),
            "started_by": current_user.username,
            "site": site
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

@api_bp.route('/current-torrents', methods=['GET'])
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

@api_bp.route('/torrent/remove', methods=['POST'])
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

@api_bp.route('/torrent/start', methods=['POST'])
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

@api_bp.route('/torrent/pause', methods=['POST'])
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
# File Management API
# ============================================================================

@api_bp.route('/files', methods=['GET'])
@login_required
def list_files():
    """List all downloaded files"""
    try:
        files = []
        config = current_app.config.get('TORRENT_CONFIG', {})
        download_dir = config.get("download_dir", "")
        
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

@api_bp.route('/files/delete', methods=['POST'])
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
        
        config = current_app.config.get('TORRENT_CONFIG', {})
        download_dir = config.get("download_dir", "")
        full_path = os.path.join(download_dir, safe_path)
        
        if not full_path.startswith(os.path.abspath(download_dir)):
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

# ============================================================================
# Debug and Utility API
# ============================================================================

@api_bp.route('/debug/downloads', methods=['GET'])
@login_required
def debug_downloads():
    """Debug endpoint to see active downloads"""
    config = current_app.config.get('TORRENT_CONFIG', {})
    return jsonify({
        "active_downloads": active_downloads,
        "active_downloads_count": len(active_downloads),
        "timestamp": time.time(),
        "supported_sites": list(TORRENT_SITES.keys()),
        "config_paths": {
            "download_dir": config.get("download_dir", ""),
            "temp_dir": config.get("temp_dir", "")
        }
    })

@api_bp.route('/sites', methods=['GET'])
@login_required
def get_sites():
    """Get available torrent sites"""
    return jsonify({
        "sites": TORRENT_SITES,
        "default": "piratebay"
    })