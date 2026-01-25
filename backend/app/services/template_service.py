"""
Template Service
Utilities for placeholder extraction, replacement, and rendering
"""
import re
import base64
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio


def extract_dimensions(html: str) -> Dict[str, int]:
    """
    Extract width and height from HTML template
    
    Checks multiple sources in priority order:
    1. <body> inline style (style="width: 1080px; height: 1280px")
    2. CSS body rule in <style> tag
    3. First container div dimensions
    
    Args:
        html: HTML content
        
    Returns:
        Dict with 'width' and 'height' keys (defaults to 1080x1080 if not found)
        
    Example:
        >>> extract_dimensions('<body style="width: 1080px; height: 1280px;">')
        {'width': 1080, 'height': 1280}
    """
    default_dimensions = {'width': 1080, 'height': 1080}
    
    # Try 1: Extract from <body> inline style
    body_style_match = re.search(r'<body[^>]*style=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if body_style_match:
        style = body_style_match.group(1)
        width_match = re.search(r'width:\s*(\d+)px', style)
        height_match = re.search(r'height:\s*(\d+)px', style)
        if width_match and height_match:
            return {
                'width': int(width_match.group(1)),
                'height': int(height_match.group(1))
            }
    
    # Try 2: Extract from <style> tag CSS body rule
    style_tag_match = re.search(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    if style_tag_match:
        css = style_tag_match.group(1)
        body_rule_match = re.search(r'body\s*\{([^}]+)\}', css, re.IGNORECASE)
        if body_rule_match:
            body_css = body_rule_match.group(1)
            width_match = re.search(r'width:\s*(\d+)px', body_css)
            height_match = re.search(r'height:\s*(\d+)px', body_css)
            if width_match and height_match:
                return {
                    'width': int(width_match.group(1)),
                    'height': int(height_match.group(1))
                }
    
    # Try 3: Extract from first div with both width and height
    div_match = re.search(r'<div[^>]*style=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if div_match:
        style = div_match.group(1)
        width_match = re.search(r'width:\s*(\d+)px', style)
        height_match = re.search(r'height:\s*(\d+)px', style)
        if width_match and height_match:
            return {
                'width': int(width_match.group(1)),
                'height': int(height_match.group(1))
            }
    
    # Default fallback
    return default_dimensions


def extract_placeholders(html: str) -> List[str]:
    """
    Extract all {placeholder} from HTML

    Args:
        html: HTML content with {placeholder} syntax

    Returns:
        List of unique placeholder names

    Example:
        >>> extract_placeholders("<h1>{consumer_name}</h1><p>{consumer_message}</p>")
        ['consumer_name', 'consumer_message']
    """
    pattern = r'\{([a-zA-Z_][a-zA-Z0-9_.]*)\}'
    matches = re.findall(pattern, html)
    return list(set([m.strip() for m in matches]))


def replace_placeholders(html: str, data: Dict[str, Any]) -> str:
    """
    Replace {key} with value from data
    Supports nested keys like {overlay.fill_color}

    Args:
        html: HTML content with {placeholder} syntax
        data: Dictionary with placeholder values (supports nested dicts)

    Returns:
        HTML with placeholders replaced

    Example:
        >>> html = "<h1>{name}</h1><div style='background: {overlay.fill_color}'></div>"
        >>> replace_placeholders(html, {'name': 'John', 'overlay': {'fill_color': '#FF0000'}})
        '<h1>John</h1><div style='background: #FF0000'></div>'
    """
    result = html
    
    # Helper function to get nested value from dict
    def get_nested_value(obj: Any, path: str) -> str:
        keys = path.split('.')
        value = obj
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return f'{{{path}}}'  # Return original placeholder if not found
        return str(value)
    
    # Find all placeholders in HTML
    pattern = r'\{([a-zA-Z_][a-zA-Z0-9_.]*)\}'
    
    def replace_match(match):
        placeholder_key = match.group(1).strip()
        # Check if it's a nested key (contains dot)
        if '.' in placeholder_key:
            return get_nested_value(data, placeholder_key)
        # Simple key
        elif placeholder_key in data:
            return str(data[placeholder_key])
        else:
            return match.group(0)  # Return original if not found
    
    result = re.sub(pattern, replace_match, html)
    return result


async def render_html_to_image(html: str, css: Optional[str] = None, width: int = 1200, height: int = 630) -> bytes:
    """
    Render HTML to PNG using Playwright

    Args:
        html: HTML content to render
        css: Optional CSS styles
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        PNG image as bytes
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': width, 'height': height})

        # Build complete HTML document
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    width: {width}px;
                    height: {height}px;
                    overflow: hidden;
                }}
                {css or ''}
            </style>
        </head>
        <body>{html}</body>
        </html>
        """

        await page.set_content(full_html, wait_until='networkidle')

        # Wait a bit for any animations or fonts to load
        await page.wait_for_timeout(500)

        # Take screenshot
        screenshot = await page.screenshot(type='png', full_page=False)
        await browser.close()

        return screenshot


async def render_html_to_base64(html: str, css: Optional[str] = None, width: int = 1200, height: int = 630) -> str:
    """
    Render HTML and return as base64 data URL for preview

    Args:
        html: HTML content to render
        css: Optional CSS styles
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Base64 encoded PNG as data URL
    """
    screenshot = await render_html_to_image(html, css, width, height)
    b64 = base64.b64encode(screenshot).decode('utf-8')
    return f"data:image/png;base64,{b64}"


def get_next_version(section: str, current_max_version: Optional[int]) -> int:
    """
    Get next version number for a section

    Args:
        section: Template section
        current_max_version: Current maximum version number or None

    Returns:
        Next version number
    """
    if current_max_version is None:
        return 1
    return current_max_version + 1


def parse_template_id(template_id: str) -> str:
    """
    Parse template_id to extract section name

    Args:
        template_id: Template identifier (e.g., 'testimonial_latest')

    Returns:
        Section name (e.g., 'testimonial')

    Example:
        >>> parse_template_id('testimonial_latest')
        'testimonial'
        >>> parse_template_id('top_new_launch_latest')
        'top_new_launch'
    """
    return template_id.replace('_latest', '').strip()


def generate_s3_key(section: str, entity_id: str, timestamp: Optional[int] = None) -> str:
    """
    Generate S3 key for uploaded image

    Args:
        section: Template section (e.g., 'testimonial')
        entity_id: Entity identifier (e.g., testimonial_id)
        timestamp: Optional timestamp (defaults to current time)

    Returns:
        S3 key path

    Example:
        >>> generate_s3_key('testimonial', '12345', 1737554400)
        'templates/testimonial/12345_1737554400.png'
    """
    if timestamp is None:
        timestamp = int(datetime.now().timestamp())

    return f"templates/{section}/{entity_id}_{timestamp}.png"


def validate_placeholders(html: str, data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Validate that all placeholders in HTML are provided in data

    Args:
        html: HTML content with placeholders
        data: Data dictionary

    Returns:
        Dictionary with 'missing' and 'extra' keys
    """
    placeholders_in_html = set(extract_placeholders(html))
    placeholders_in_data = set(data.keys())

    missing = list(placeholders_in_html - placeholders_in_data)
    extra = list(placeholders_in_data - placeholders_in_html)

    return {
        'missing': missing,
        'extra': extra
    }
