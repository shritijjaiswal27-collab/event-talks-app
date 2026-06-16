import os
import re
import time
import logging
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Simple in-memory cache
cache = {
    "data": None,
    "last_updated": 0,
    "ttl": 600 # 10 minutes cache TTL
}

def fetch_and_parse_feed():
    """Fetches the Google BigQuery Release notes feed and parses it into granular, individual updates."""
    url = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    logger.info(f"Fetching RSS feed from: {url}")
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    # Parse XML
    root = ET.fromstring(response.content)
    
    # Atom namespace definition
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    entries = []
    
    # Find all atom:entry nodes
    entry_nodes = root.findall('atom:entry', ns)
    logger.info(f"Found {len(entry_nodes)} entries in the feed XML.")
    
    for entry_idx, entry in enumerate(entry_nodes):
        title_elem = entry.find('atom:title', ns)
        updated_elem = entry.find('atom:updated', ns)
        link_elem = entry.find("atom:link[@rel='alternate']", ns)
        if link_elem is None:
            link_elem = entry.find("atom:link", ns)
        content_elem = entry.find('atom:content', ns)
        
        date_str = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        updated_str = updated_elem.text.strip() if updated_elem is not None and updated_elem.text else ""
        link_href = link_elem.attrib.get('href', '') if link_elem is not None else ""
        content_html = content_elem.text if content_elem is not None and content_elem.text else ""
        
        if not content_html:
            continue
            
        soup = BeautifulSoup(content_html, 'html.parser')
        h3_tags = soup.find_all('h3')
        
        if not h3_tags:
            # Fallback if no h3 tags: treat whole content as one entry
            text_content = soup.get_text().strip()
            text_content_clean = re.sub(r'\s+', ' ', text_content)
            entries.append({
                'id': f"entry-{entry_idx}-0",
                'date': date_str,
                'updated': updated_str,
                'type': 'Update',
                'content_html': content_html,
                'text_preview': text_content_clean[:180] + '...' if len(text_content_clean) > 180 else text_content_clean,
                'full_text': text_content_clean,
                'link': link_href
            })
        else:
            # Parse individual updates marked by h3 tags
            for h3_idx, h3 in enumerate(h3_tags):
                update_type = h3.get_text().strip()
                
                # Gather sibling nodes until the next h3 tag
                siblings = []
                for sibling in h3.next_siblings:
                    if sibling.name == 'h3':
                        break
                    siblings.append(str(sibling))
                
                sub_content_html = ''.join(siblings).strip()
                sub_soup = BeautifulSoup(sub_content_html, 'html.parser')
                text_content = sub_soup.get_text().strip()
                text_content_clean = re.sub(r'\s+', ' ', text_content)
                
                # Assign a unique id for easy frontend manipulation (e.g. selection)
                entry_id = f"entry-{entry_idx}-{h3_idx}"
                
                # Clean up empty sub contents if any
                if not text_content_clean:
                    continue
                    
                # Format type (e.g., standardizing capitalization)
                formatted_type = update_type.capitalize()
                
                entries.append({
                    'id': entry_id,
                    'date': date_str,
                    'updated': updated_str,
                    'type': formatted_type,
                    'content_html': sub_content_html,
                    'text_preview': text_content_clean[:180] + '...' if len(text_content_clean) > 180 else text_content_clean,
                    'full_text': text_content_clean,
                    'link': link_href
                })
                
    logger.info(f"Successfully processed {len(entries)} individual updates.")
    return entries

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/release-notes')
def get_release_notes():
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    current_time = time.time()
    
    # Check if cache is expired or if refresh is forced
    if force_refresh or cache["data"] is None or (current_time - cache["last_updated"] > cache["ttl"]):
        try:
            logger.info("Fetching and updating release notes cache...")
            parsed_data = fetch_and_parse_feed()
            cache["data"] = parsed_data
            cache["last_updated"] = current_time
        except Exception as e:
            logger.error(f"Error fetching release notes: {str(e)}", exc_info=True)
            # If fetch fails but cache has data, serve stale data as fallback
            if cache["data"] is not None:
                return jsonify({
                    "status": "warning",
                    "message": f"Failed to refresh feed ({str(e)}). Serving cached data.",
                    "last_updated": cache["last_updated"],
                    "data": cache["data"]
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": f"Failed to fetch release notes: {str(e)}"
                }), 500
                
    return jsonify({
        "status": "success",
        "last_updated": cache["last_updated"],
        "data": cache["data"]
    })

if __name__ == '__main__':
    # Flask app is ready for local run
    app.run(host='0.0.0.0', port=5001, debug=True)
