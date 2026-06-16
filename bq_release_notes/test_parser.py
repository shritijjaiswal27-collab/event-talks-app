import os
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

def test_parse_content():
    # Path to the downloaded XML feed file
    feed_path = "/Users/shritijjaiswal/.gemini/antigravity/brain/87e4e601-700f-4e90-aa30-9af2715020cc/.system_generated/steps/8/content.md"
    
    if not os.path.exists(feed_path):
        print(f"Error: Feed file not found at {feed_path}")
        return
        
    with open(feed_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
        
    # Find start of XML
    xml_start_idx = file_content.find("<?xml")
    if xml_start_idx == -1:
        print("Error: Could not find XML start token")
        return
        
    xml_content = file_content[xml_start_idx:]
    
    root = ET.fromstring(xml_content.encode('utf-8'))
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    entries = []
    entry_nodes = root.findall('atom:entry', ns)
    print(f"Found {len(entry_nodes)} entry nodes.")
    
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
            text_content = soup.get_text().strip()
            text_content_clean = re.sub(r'\s+', ' ', text_content)
            entries.append({
                'id': f"entry-{entry_idx}-0",
                'date': date_str,
                'updated': updated_str,
                'type': 'Update',
                'content_html': content_html,
                'text_preview': text_content_clean[:180] + '...',
                'full_text': text_content_clean,
                'link': link_href
            })
        else:
            for h3_idx, h3 in enumerate(h3_tags):
                update_type = h3.get_text().strip()
                siblings = []
                for sibling in h3.next_siblings:
                    if sibling.name == 'h3':
                        break
                    siblings.append(str(sibling))
                
                sub_content_html = ''.join(siblings).strip()
                sub_soup = BeautifulSoup(sub_content_html, 'html.parser')
                text_content = sub_soup.get_text().strip()
                text_content_clean = re.sub(r'\s+', ' ', text_content)
                
                if not text_content_clean:
                    continue
                    
                entries.append({
                    'id': f"entry-{entry_idx}-{h3_idx}",
                    'date': date_str,
                    'updated': updated_str,
                    'type': update_type.capitalize(),
                    'content_html': sub_content_html,
                    'text_preview': text_content_clean[:180] + '...',
                    'full_text': text_content_clean,
                    'link': link_href
                })
                
    print(f"Successfully parsed {len(entries)} granular updates.")
    print("Example entry 0:")
    if entries:
        print(f"  ID: {entries[0]['id']}")
        print(f"  Date: {entries[0]['date']}")
        print(f"  Type: {entries[0]['type']}")
        print(f"  Preview: {entries[0]['text_preview']}")
        print(f"  Link: {entries[0]['link']}")
        
    print("\nCheck if types are extracted successfully:")
    types = set(e['type'] for e in entries)
    print(f"  Found types: {types}")
    
    assert len(entries) > 0, "No entries parsed!"
    assert 'Feature' in types, "Features type missing!"
    print("\nParser test PASSED!")

if __name__ == '__main__':
    test_parse_content()
