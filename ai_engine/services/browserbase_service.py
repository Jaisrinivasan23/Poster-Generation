"""
Browserbase Service

Provides cloud-based headless browser infrastructure for accurate DOM manipulation.
Uses Browserbase's managed browser sessions with Playwright integration.
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BrowserbaseService:
    """
    Wrapper for Browserbase cloud browser infrastructure.

    Provides:
    - Session management (create, connect, close)
    - DOM manipulation via Playwright
    - Screenshot capture for visual verification
    - Session replay URLs for debugging
    """

    def __init__(self):
        """Initialize Browserbase client with environment credentials."""
        self.api_key = os.environ.get("BROWSERBASE_API_KEY")
        self.project_id = os.environ.get("BROWSERBASE_PROJECT_ID")

        self._bb = None
        self._session = None
        self._playwright = None
        self._browser = None
        self._page = None

        # Only import if credentials are available
        if self.api_key and self.project_id:
            try:
                from browserbase import Browserbase
                self._bb = Browserbase(api_key=self.api_key)
                logger.info("Browserbase client initialized successfully")
            except ImportError:
                logger.warning("browserbase package not installed, Browserbase features disabled")
            except Exception as e:
                logger.error(f"Failed to initialize Browserbase client: {e}")
        else:
            logger.info("Browserbase credentials not found, service disabled")

    @property
    def is_available(self) -> bool:
        """Check if Browserbase is properly configured and available."""
        return self._bb is not None

    async def create_session(self) -> Optional[Any]:
        """
        Create a new Browserbase browser session.

        Returns:
            Session object with connect_url, or None if failed
        """
        if not self.is_available:
            logger.warning("Browserbase not available, cannot create session")
            return None

        try:
            self._session = self._bb.sessions.create(project_id=self.project_id)
            logger.info(f"Created Browserbase session: {self._session.id}")
            return self._session
        except Exception as e:
            logger.error(f"Failed to create Browserbase session: {e}")
            return None

    async def connect(self) -> Optional[Any]:
        """
        Connect Playwright to a Browserbase session.

        Creates a new session if one doesn't exist, then connects via CDP.

        Returns:
            Playwright page object, or None if failed
        """
        if not self.is_available:
            return None

        try:
            # Create session if needed
            if not self._session:
                await self.create_session()
                if not self._session:
                    return None

            # Import Playwright
            from playwright.async_api import async_playwright

            # Start Playwright and connect via CDP
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(
                self._session.connect_url
            )

            # Get the default context and page
            context = self._browser.contexts[0]
            self._page = context.pages[0] if context.pages else await context.new_page()

            logger.info(f"Connected to Browserbase session: {self._session.id}")
            return self._page

        except Exception as e:
            logger.error(f"Failed to connect to Browserbase: {e}")
            await self.close()
            return None

    async def load_html(self, html: str) -> bool:
        """
        Load HTML content into the browser page.

        Args:
            html: The HTML content to load

        Returns:
            True if successful, False otherwise
        """
        if not self._page:
            logger.error("No page available, call connect() first")
            return False

        try:
            await self._page.set_content(html, wait_until="domcontentloaded")
            logger.debug("HTML content loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load HTML content: {e}")
            return False

    async def execute_edit(
        self,
        selector: str,
        edit_type: str,
        value: str
    ) -> Dict[str, Any]:
        """
        Execute a DOM edit operation on the page.

        Args:
            selector: CSS selector for the target element
            edit_type: Type of edit ('text', 'class', 'style', 'attribute', 'html')
            value: The new value to apply

        Returns:
            Dict with 'success' and optional 'error' keys
        """
        if not self._page:
            return {"success": False, "error": "No page available"}

        try:
            result = await self._page.evaluate('''
                ({selector, editType, value}) => {
                    const el = document.querySelector(selector);
                    if (!el) {
                        return { success: false, error: 'Element not found: ' + selector };
                    }

                    try {
                        switch(editType) {
                            case 'text':
                                el.textContent = value;
                                break;
                            case 'class':
                                el.className = value;
                                break;
                            case 'addClass':
                                el.classList.add(value);
                                break;
                            case 'removeClass':
                                el.classList.remove(value);
                                break;
                            case 'replaceClass':
                                const [oldClass, newClass] = value.split('->');
                                el.classList.remove(oldClass.trim());
                                el.classList.add(newClass.trim());
                                break;
                            case 'style':
                                const styles = JSON.parse(value);
                                Object.assign(el.style, styles);
                                break;
                            case 'attribute':
                                const [attr, val] = value.split('=', 2);
                                el.setAttribute(attr.trim(), val ? val.trim() : '');
                                break;
                            case 'html':
                                el.innerHTML = value;
                                break;
                            case 'outerHtml':
                                el.outerHTML = value;
                                break;
                            default:
                                return { success: false, error: 'Unknown edit type: ' + editType };
                        }
                        return { success: true };
                    } catch (e) {
                        return { success: false, error: e.message };
                    }
                }
            ''', {'selector': selector, 'editType': edit_type, 'value': value})

            if result['success']:
                logger.debug(f"Edit applied: {edit_type} on {selector}")
            else:
                logger.warning(f"Edit failed: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"Failed to execute edit: {e}")
            return {"success": False, "error": str(e)}

    async def get_html(self) -> Optional[str]:
        """
        Get the current page HTML content.

        Returns:
            The page HTML as a string, or None if failed
        """
        if not self._page:
            return None

        try:
            return await self._page.content()
        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            return None

    async def screenshot(
        self,
        path: Optional[str] = None,
        full_page: bool = True,
        selector: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Capture a screenshot of the page or specific element.

        Args:
            path: Optional file path to save the screenshot
            full_page: Whether to capture the full page (default True)
            selector: Optional CSS selector to screenshot specific element

        Returns:
            Screenshot as bytes, or None if failed
        """
        if not self._page:
            return None

        try:
            if selector:
                element = await self._page.query_selector(selector)
                if element:
                    return await element.screenshot(path=path)
                else:
                    logger.warning(f"Element not found for screenshot: {selector}")
                    return None
            else:
                return await self._page.screenshot(path=path, full_page=full_page)
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    async def get_element_info(self, selector: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an element.

        Args:
            selector: CSS selector for the element

        Returns:
            Dict with element info (tag, classes, text, attributes, bounds)
        """
        if not self._page:
            return None

        try:
            return await self._page.evaluate('''
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return null;

                    const rect = el.getBoundingClientRect();
                    return {
                        tag: el.tagName.toLowerCase(),
                        id: el.id || null,
                        classes: Array.from(el.classList),
                        text: el.textContent?.substring(0, 200),
                        attributes: Object.fromEntries(
                            Array.from(el.attributes).map(a => [a.name, a.value])
                        ),
                        bounds: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }
                    };
                }
            ''', selector)
        except Exception as e:
            logger.error(f"Failed to get element info: {e}")
            return None

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._session.id if self._session else None

    def get_session_replay_url(self) -> Optional[str]:
        """
        Get the URL to view the session replay in Browserbase dashboard.

        Returns:
            URL string, or None if no session
        """
        if not self._session:
            return None
        return f"https://browserbase.com/sessions/{self._session.id}"

    async def close(self):
        """Close the browser and clean up resources."""
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
                self._page = None
                logger.debug("Browser closed")

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
                logger.debug("Playwright stopped")

            self._session = None

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance for reuse
_browserbase_service: Optional[BrowserbaseService] = None


def get_browserbase_service() -> BrowserbaseService:
    """
    Get or create the Browserbase service singleton.

    Returns:
        BrowserbaseService instance
    """
    global _browserbase_service
    if _browserbase_service is None:
        _browserbase_service = BrowserbaseService()
    return _browserbase_service
