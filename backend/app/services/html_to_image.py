"""
HTML to Image Conversion Service
Converts HTML to PNG using Playwright (async API)
"""
import asyncio
import base64
from typing import Dict
from playwright.async_api import async_playwright


class HTMLToImageConverter:
    """Singleton class to manage Playwright browser instance"""

    _instance = None
    _browser = None
    _playwright = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HTMLToImageConverter, cls).__new__(cls)
        return cls._instance

    async def initialize(self):
        """Initialize Playwright browser"""
        if self._browser is None:
            print("[HTML2PNG] Initializing Playwright browser...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu'
                ]
            )
            print("[HTML2PNG] Playwright browser initialized successfully")

    async def close(self):
        """Close Playwright browser"""
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()
            self._browser = None
            self._playwright = None
            print("[HTML2PNG] Playwright browser closed")

    async def html_to_png(
        self,
        html: str,
        width: int,
        height: int,
        scale: float = 1.0,
        timeout: int = 60000
    ) -> bytes:
        """
        Convert HTML to PNG using Playwright

        Args:
            html: HTML string
            width: Image width in pixels
            height: Image height in pixels
            scale: Device scale factor (1.0 = standard, 2.0 = high-res)
            timeout: Timeout in milliseconds (default: 60000ms = 60 seconds)

        Returns:
            PNG image as bytes
        """
        import re
        
        # Lazy initialization if not already done
        if not self._browser:
            await self.initialize()

        page = None
        try:
            # Check if html already has DOCTYPE or html tag
            html_lower = html.strip().lower()
            is_complete_html = html_lower.startswith('<!doctype') or html_lower.startswith('<html')
            
            # For complete HTML templates, try to extract dimensions from CSS
            actual_width = width
            actual_height = height
            
            if is_complete_html:
                # Look for poster-container or similar with fixed dimensions
                # Pattern: width: XXXpx and height: XXXpx in CSS
                width_match = re.search(r'\.poster-container[^}]*width:\s*(\d+)px', html, re.IGNORECASE | re.DOTALL)
                height_match = re.search(r'\.poster-container[^}]*height:\s*(\d+)px', html, re.IGNORECASE | re.DOTALL)
                
                if width_match and height_match:
                    actual_width = int(width_match.group(1))
                    actual_height = int(height_match.group(1))
                    print(f"[HTML2PNG] Extracted dimensions from template: {actual_width}x{actual_height}")
                else:
                    # Try to find any container with fixed dimensions
                    width_match = re.search(r'width:\s*(\d+)px', html)
                    height_match = re.search(r'height:\s*(\d+)px', html)
                    if width_match and height_match:
                        extracted_w = int(width_match.group(1))
                        extracted_h = int(height_match.group(1))
                        # Only use if they look like poster dimensions (> 500px)
                        if extracted_w >= 500 and extracted_h >= 500:
                            actual_width = extracted_w
                            actual_height = extracted_h
                            print(f"[HTML2PNG] Using extracted dimensions: {actual_width}x{actual_height}")

            # Create new page with the appropriate viewport
            page = await self._browser.new_page(
                viewport={'width': actual_width, 'height': actual_height},
                device_scale_factor=scale
            )

            # Set default timeout for this page
            page.set_default_timeout(timeout)

            # Prepare HTML content
            if is_complete_html:
                # Use template as-is without any CSS injection
                final_html = html
                print(f"[HTML2PNG] Using complete HTML template as-is")
            else:
                # Wrap simple HTML fragments in a proper document
                final_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{
            width: {actual_width}px;
            height: {actual_height}px;
            overflow: hidden;
        }}
    </style>
</head>
<body>
{html}
</body>
</html>"""
                print(f"[HTML2PNG] Wrapped HTML fragment in document")

            # Set content and wait for network to be idle (ensures all resources loaded)
            await page.set_content(final_html, wait_until='networkidle', timeout=timeout)

            # Wait for fonts to be ready (important for first batch)
            await page.evaluate('document.fonts.ready')

            # Additional wait to ensure everything is rendered properly
            await page.wait_for_timeout(1500)

            # Take screenshot with exact dimensions matching the actual viewport
            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=False,
                clip={
                    'x': 0,
                    'y': 0,
                    'width': actual_width,
                    'height': actual_height
                },
                timeout=timeout
            )

            print(f"[HTML2PNG] Screenshot captured: {len(screenshot_bytes)} bytes ({actual_width}x{actual_height})")

            return screenshot_bytes

        except Exception as e:
            import traceback
            print(f"[HTML2PNG] Conversion failed: {e}")
            print(f"[HTML2PNG] Traceback: {traceback.format_exc()}")
            raise Exception(f"HTML to PNG conversion failed: {str(e)}")
        finally:
            # Always close page
            if page:
                try:
                    await page.close()
                except:
                    pass


# Global converter instance
_converter = HTMLToImageConverter()


async def convert_html_to_png(
    html: str,
    dimensions: Dict[str, int],
    scale: float = 1.0,
    timeout: int = 60000
) -> bytes:
    """
    Convert HTML to PNG (convenience function)

    Args:
        html: HTML string
        dimensions: Dict with 'width' and 'height' keys
        scale: Device scale factor (1.0 = standard, 2.0 = high-res)
        timeout: Timeout in milliseconds (default: 60000ms)

    Returns:
        PNG image as bytes

    Example:
        >>> html = "<!DOCTYPE html><html>...</html>"
        >>> image_bytes = await convert_html_to_png(html, {"width": 1080, "height": 1080})
    """
    return await _converter.html_to_png(
        html=html,
        width=dimensions['width'],
        height=dimensions['height'],
        scale=scale,
        timeout=timeout
    )


async def initialize_converter():
    """Initialize the converter at app startup"""
    await _converter.initialize()


async def close_converter():
    """Close the converter at app shutdown"""
    await _converter.close()


# Batch conversion for multiple HTMLs
async def convert_html_batch(
    html_list: list[str],
    dimensions: Dict[str, int],
    scale: float = 1.0,
    timeout: int = 60000
) -> list[bytes]:
    """
    Convert multiple HTMLs to PNG in parallel

    Args:
        html_list: List of HTML strings
        dimensions: Image dimensions
        scale: Device scale factor
        timeout: Timeout in milliseconds

    Returns:
        List of PNG bytes
    """
    tasks = [
        convert_html_to_png(html, dimensions, scale, timeout)
        for html in html_list
    ]
    return await asyncio.gather(*tasks)
