/**
 * Torrent Search & Download Manager - Main JavaScript
 * Multi-site support with clean separation of concerns
 */

// ============================================================================
// Global Variables and Configuration
// ============================================================================

let downloadInterval;
let isPolling = false;
let selectedSite = 'piratebay'; // Default site

// Site configuration
const SITES = {
    'piratebay': {
        name: 'The Pirate Bay',
        type: 'json_api',
        color: '#007bff'
    },
    '1337x': {
        name: '1337x',
        type: 'html_scrape',
        color: '#28a745'
    },
    'gog-games': {
        name: 'GOG Games',
        type: 'html_scrape',
        color: '#6f42c1'
    },
    'fitgirl': {
        name: 'FitGirl Repacks',
        type: 'html_scrape',
        color: '#e83e8c'
    },
    'steamrip': {
        name: 'SteamRIP',
        type: 'html_scrape',
        color: '#fd7e14'
    }
};

console.log('Multi-Site Torrent Search & Download Manager loaded');

// ============================================================================
// Site Selection Functions
// ============================================================================

function selectSite(site) {
    console.log('Site selected:', site);
    selectedSite = site;
    
    // Update UI
    document.querySelectorAll('.site-option').forEach(option => {
        option.classList.remove('selected');
    });
    
    const selectedOption = document.querySelector(`[onclick="selectSite('${site}')"]`);
    if (selectedOption) {
        selectedOption.classList.add('selected');
        selectedOption.querySelector('input').checked = true;
    }
    
    // Update search status
    updateSearchStatus();
    
    // Clear previous results
    const resultsContainer = document.getElementById("search-results-container");
    resultsContainer.innerHTML = '';
}

function updateSearchStatus() {
    const statusEl = document.getElementById('search-status');
    const siteInfo = SITES[selectedSite];
    if (statusEl && siteInfo) {
        statusEl.textContent = `Searching ${siteInfo.name}`;
        statusEl.style.color = siteInfo.color;
    }
}

// ============================================================================
// Search Functions
// ============================================================================

async function search() {
    console.log('Search function called');
    const query = document.getElementById("searchInput").value.trim();
    console.log('Search query:', query, 'Site:', selectedSite);
    
    if (!query) {
        console.log('Empty query, returning');
        return;
    }

    const resultsContainer = document.getElementById("search-results-container");
    const siteInfo = SITES[selectedSite];
    
    resultsContainer.innerHTML = `
        <div class="search-results-header">
            <span>Searching ${siteInfo.name}...</span>
            <span class="search-site-info">${siteInfo.type.toUpperCase()}</span>
        </div>
        <div class="search-results-content">
            <div class="loading">Searching "${escapeHtml(query)}" on ${siteInfo.name}...</div>
        </div>
    `;

    try {
        console.log('Making fetch request to:', `/api/search?q=${encodeURIComponent(query)}&site=${selectedSite}`);
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&site=${selectedSite}`);
        console.log('Response status:', response.status);
        
        const data = await response.json();
        console.log('Response data:', data);

        if (data.results && data.results.length > 0) {
            console.log('Displaying results:', data.results.length);
            resultsContainer.innerHTML = `
                <div class="search-results-header">
                    <span>Search Results (${data.results.length} found for "${escapeHtml(query)}")</span>
                    <span class="search-site-info">${siteInfo.name}</span>
                </div>
                <div class="search-results-content">
                    ${data.results.map(result => `
                        <div class="result-item">
                            <div class="item-name">${escapeHtml(result.name)}</div>
                            <div class="item-details">
                                <div class="detail-item">Size: <strong>${result.size || 'Unknown'}</strong></div>
                                <div class="detail-item">Seeders: <strong>${result.seeders || 'N/A'}</strong></div>
                                <div class="detail-item">Leechers: <strong>${result.leechers || 'N/A'}</strong></div>
                                ${result.added ? `<div class="detail-item">Added: ${result.added}</div>` : ''}
                                ${result.category ? `<div class="detail-item">Category: ${result.category}</div>` : ''}
                            </div>
                            <div class="item-actions">
                                <button class="btn" onclick="download('${result.info_hash || result.magnet}', '${escapeHtml(result.name).replace(/'/g, "\\'")}')">
                                    Download
                                </button>
                                ${result.url ? `<a href="${result.url}" target="_blank" class="btn secondary btn-small">View Page</a>` : ''}
                            </div>
                        </div>
                    `).join("")}
                </div>
            `;
        } else {
            console.log('No results found');
            resultsContainer.innerHTML = `
                <div class="search-results-header">
                    <span>No Results</span>
                    <span class="search-site-info">${siteInfo.name}</span>
                </div>
                <div class="search-results-content">
                    <div class="empty-state">
                        No results found for "${escapeHtml(query)}" on ${siteInfo.name}
                        <br><small>Try a different search term or switch to another site</small>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error("Search error:", error);
        resultsContainer.innerHTML = `
            <div class="search-results-header">
                <span>Search Error</span>
                <span class="search-site-info">${siteInfo.name}</span>
            </div>
            <div class="search-results-content">
                <div class="empty-state">
                    Search failed on ${siteInfo.name}: ${error.message}
                    <br><small>Try switching to a different site or check your connection</small>
                </div>
            </div>
        `;
    }
}

// ============================================================================
// Download Functions
// ============================================================================

async function download(infoHashOrMagnet, name) {
    console.log('Download starting:', name, infoHashOrMagnet);
    const button = event.target;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Starting...";

    try {
        const response = await fetch("/api/download", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                info_hash: infoHashOrMagnet, 
                name: name,
                site: selectedSite
            })
        });

        const data = await response.json();

        if (data.success) {
            button.textContent = "Added!";
            button.classList.add('success');
            await refreshTorrents();
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

// ============================================================================
// Torrent Management Functions
// ============================================================================

async function refreshTorrents() {
    console.log('Refreshing torrents...');
    const downloadsDiv = document.getElementById("downloads");
    
    try {
        const response = await fetch("/api/current-torrents");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        console.log('Torrents API response:', data);

        if (data.torrents && data.torrents.length > 0) {
            console.log(`Displaying ${data.torrents.length} torrents`);
            downloadsDiv.innerHTML = data.torrents.map(torrent => {
                const statusClass = `status-${torrent.status.replace(/\s+/g, '-')}`;
                let statusDisplay = torrent.status;
                let progressColor = '#28a745';
                let errorInfo = '';
                
                if (torrent.error > 0) {
                    statusDisplay = 'Error';
                    progressColor = '#dc3545';
                    errorInfo = `
                        <div class="error-highlight">
                            <strong>Error:</strong> ${torrent.error_string}<br>
                            <small>Tip: This usually means a volume mounting issue. Check your docker-compose.yml file.</small>
                        </div>
                    `;
                }
                
                return `
                    <div class="download-item">
                        <div class="item-name">${escapeHtml(torrent.name)}</div>
                        <div class="download-progress">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${torrent.progress}%; background: ${progressColor};">
                                    <div class="progress-text">${torrent.progress.toFixed(1)}%</div>
                                </div>
                            </div>
                        </div>
                        <div class="status-info">
                            <div>
                                <span class="status-badge ${statusClass}">${statusDisplay}</span>
                                <div class="stats">
                                    ${torrent.download_rate > 0 ? `Down: ${formatSpeed(torrent.download_rate)}` : ''}
                                    ${torrent.upload_rate > 0 ? `Up: ${formatSpeed(torrent.upload_rate)}` : ''}
                                    ${torrent.download_rate === 0 && torrent.upload_rate === 0 ? 'Idle' : ''}
                                </div>
                            </div>
                            <div class="item-actions">
                                ${torrent.status === 'stopped' ? 
                                    `<button class="btn btn-small success" onclick="startTorrent(${torrent.id})">Start</button>` :
                                    `<button class="btn btn-small warning" onclick="pauseTorrent(${torrent.id})">Pause</button>`
                                }
                                <button class="btn btn-small secondary" onclick="removeTorrent(${torrent.id})">Remove</button>
                            </div>
                        </div>
                        ${errorInfo}
                    </div>
                `;
            }).join("");
        } else {
            console.log('No torrents found in API response');
            downloadsDiv.innerHTML = '<div class="empty-state">No active downloads</div>';
        }
    } catch (error) {
        console.error("Refresh error:", error);
        downloadsDiv.innerHTML = `<div class="empty-state">Failed to load downloads: ${error.message}</div>`;
    }
}

async function removeTorrent(torrentId) {
    if (!confirm('Remove this torrent from the download list?\n\n(Downloaded files will be kept)')) {
        return;
    }
    
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

// ============================================================================
// File Management Functions
// ============================================================================

async function refreshFiles() {
    console.log('Refreshing files...');
    const filesDiv = document.getElementById("files");
    const fileCountSpan = document.getElementById("file-count");
    
    try {
        const response = await fetch("/api/files");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        console.log('Files API response:', data);

        if (data.files && data.files.length > 0) {
            const totalSize = formatTotalSize(data.files);
            fileCountSpan.textContent = `${data.files.length} files (${totalSize})`;
            
            filesDiv.innerHTML = data.files.map(file => `
                <div class="file-item">
                    <div class="item-name">${escapeHtml(file.name)}</div>
                    <div class="item-details">
                        <div class="detail-item">Size: <strong>${file.size}</strong></div>
                        <div class="detail-item">Modified: ${file.modified}</div>
                        ${file.folder !== '/' ? `<div class="detail-item">Folder: ${file.folder}</div>` : ''}
                    </div>
                    <div class="item-actions">
                        <a href="/download/${encodeURIComponent(file.path)}" 
                           class="btn btn-small" 
                           download="${file.name}">
                            Download to Device
                        </a>
                        <button class="btn btn-small danger" 
                                onclick="deleteFile('${file.path}', '${escapeHtml(file.name).replace(/'/g, "\\'")}')">
                            Delete
                        </button>
                    </div>
                </div>
            `).join("");
        } else {
            console.log('No files found');
            fileCountSpan.textContent = '0 files';
            filesDiv.innerHTML = '<div class="empty-state">No downloaded files yet. Complete some torrents to see files here!</div>';
        }
    } catch (error) {
        console.error("Files refresh error:", error);
        filesDiv.innerHTML = `<div class="empty-state">Failed to load files: ${error.message}</div>`;
        fileCountSpan.textContent = '';
    }
}

async function deleteFile(filepath, filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?\n\nThis action cannot be undone.`)) {
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

// ============================================================================
// Polling and Auto-Refresh Functions
// ============================================================================

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
    console.log('Refreshing all data...');
    await Promise.all([refreshTorrents(), refreshFiles()]);
}

// ============================================================================
// Utility Functions
// ============================================================================

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

// ============================================================================
// Event Listeners and Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, setting up event listeners...');
    
    // Search input enter key handler
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                console.log('Enter key pressed, calling search');
                search();
            }
        });
    }
    
    // Initialize UI
    updateSearchStatus();
    
    console.log('Event listeners set up successfully');
});

// Page lifecycle handlers
window.addEventListener('load', function() {
    console.log('Page loaded, initializing...');
    refreshAll();
    
    // Check if there are active downloads and start polling
    setTimeout(() => {
        const downloads = document.getElementById("downloads");
        if (downloads && downloads.innerHTML.includes("progress-bar")) {
            startDownloadPolling();
        }
    }, 2000);
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
            if (downloads && downloads.innerHTML.includes("progress-bar")) {
                startDownloadPolling();
            }
        }, 1000);
    }
});

console.log('Multi-Site Torrent Search & Download Manager fully loaded!');
