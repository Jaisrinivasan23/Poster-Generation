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
        # Lazy initialization if not already done
        if not self._browser:
            await self.initialize()

        page = None
        try:
            # Create new page with exact viewport
            page = await self._browser.new_page(
                viewport={'width': width, 'height': height},
                device_scale_factor=scale
            )

            # Set default timeout for this page
            page.set_default_timeout(timeout)

            # Wrap HTML to ensure it fills the viewport
            # This handles templates that have their own body/html with different dimensions
            wrapped_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width={width}, height={height}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{
            width: {width}px;
            height: {height}px;
            overflow: hidden;
            background: transparent;
        }}
        body {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        /* Scale content to fit viewport if it has fixed dimensions */
        body > * {{
            max-width: 100%;
            max-height: 100%;
        }}
    </style>
</head>
<body>
{html}
</body>
</html>"""

            # Check if html already has DOCTYPE or html tag - if so, use it directly
            html_lower = html.strip().lower()
            if html_lower.startswith('<!doctype') or html_lower.startswith('<html'):
                # Template already has full HTML structure - inject scaling CSS instead
                wrapped_html = html
                # Inject CSS to force viewport size
                if '<head>' in html.lower():
                    inject_css = f"""<style>
                        html, body {{ 
                            width: {width}px !important; 
                            height: {height}px !important; 
                            margin: 0 !important; 
                            padding: 0 !important;
                            overflow: hidden !important;
                        }}
                    </style>"""
                    # Insert after <head>
                    head_end_idx = html.lower().find('<head>') + 6
                    wrapped_html = html[:head_end_idx] + inject_css + html[head_end_idx:]

            # Set content and wait for network to be idle (ensures all resources loaded)
            await page.set_content(wrapped_html, wait_until='networkidle', timeout=timeout)

            # Wait for fonts to be ready (important for first batch)
            await page.evaluate('document.fonts.ready')

            # Additional wait to ensure everything is rendered properly
            await page.wait_for_timeout(1500)

            # Take screenshot with exact dimensions
            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=False,
                clip={
                    'x': 0,
                    'y': 0,
                    'width': width,
                    'height': height
                },
                timeout=timeout
            )

            print(f"[HTML2PNG] Screenshot captured: {len(screenshot_bytes)} bytes ({width}x{height})")

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
