"""
Editing Agent using Anthropic API for intelligent website editing.

This agent can:
- Understand the current HTML structure
- Make targeted edits using tools
- Iterate and refine edits autonomously
- Handle complex multi-step editing tasks
- Maintain design consistency using design context
- Use Browserbase for cloud browser automation with visual verification
- Use screenshots as visual context to make accurate edits without asking questions
"""
from typing import List, Dict, Any, Optional
import json
import base64
import httpx
import anthropic
from logging_config import logger
from config import settings
from services.editing_system_prompt import (
    build_editing_system_prompt,
    build_user_prompt
)
from services.browserbase_service import get_browserbase_service, BrowserbaseService
from services.visual_verification import get_visual_verification_service, VisualVerificationService


class EditingAgent:
    """
    Intelligent editing agent with tool use for website modifications.
    Uses Anthropic API for AI capabilities.
    """

    SYSTEM_PROMPT = """You are an expert website editor agent. Your job is to make precise,
high-quality edits to HTML websites based on user instructions.

You have access to tools that let you:
1. Analyze the DOM structure
2. Edit specific elements by selector
3. Change text content
4. Modify styles
5. Add or remove sections

IMPORTANT GUIDELINES:
- Always analyze the HTML first to understand the structure
- Make minimal, targeted changes - don't rewrite entire sections unnecessarily
- Preserve the existing design and styling when making content changes
- Use CSS selectors precisely to target the right elements
- After making changes, verify the edit was successful
- If an edit fails, try an alternative approach

When you receive an editing instruction:
1. First, understand what needs to be changed
2. Identify the target element(s) using selectors
3. Apply the edit using the appropriate tool
4. Return the modified HTML

Always return valid, complete HTML."""

    # Tool definitions for the agent
    EDITING_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "analyze_dom",
                "description": "Analyze the HTML DOM structure to understand the page layout and find elements. Use this first to understand what elements exist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "The HTML to analyze"
                        }
                    },
                    "required": ["html"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "edit_text",
                "description": "Change the text content of an element. Use a CSS selector to target the element.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "The current HTML"
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the element (e.g., 'h1', '.hero-title', '#main-heading')"
                        },
                        "new_text": {
                            "type": "string",
                            "description": "The new text content"
                        }
                    },
                    "required": ["html", "selector", "new_text"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "edit_style",
                "description": "Change CSS styles of an element. Use a CSS selector to target the element.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "The current HTML"
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the element"
                        },
                        "styles": {
                            "type": "object",
                            "description": "Object of CSS properties to change (e.g., {\"backgroundColor\": \"blue\", \"color\": \"white\"})"
                        }
                    },
                    "required": ["html", "selector", "styles"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "edit_attribute",
                "description": "Change an attribute of an element (href, src, alt, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "The current HTML"
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the element"
                        },
                        "attribute": {
                            "type": "string",
                            "description": "The attribute name (e.g., 'href', 'src', 'alt')"
                        },
                        "value": {
                            "type": "string",
                            "description": "The new attribute value"
                        }
                    },
                    "required": ["html", "selector", "attribute", "value"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "replace_element",
                "description": "Replace an entire element's HTML. Use for more complex changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "The current HTML"
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the element"
                        },
                        "new_html": {
                            "type": "string",
                            "description": "The new HTML to replace with"
                        }
                    },
                    "required": ["html", "selector", "new_html"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "modify_class",
                "description": "Replace a CSS class on a SPECIFIC element (not globally). Use the selector from the TARGET ELEMENT section to change only that element's classes. ALWAYS provide a selector to avoid changing other elements.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the specific element (e.g., 'h1.hero-title', 'button.cta-primary:nth-of-type(1)'). Use the selector from TARGET ELEMENT section."
                        },
                        "old_class": {
                            "type": "string",
                            "description": "The class to replace on this element (e.g., 'bg-blue-500', 'text-white')"
                        },
                        "new_class": {
                            "type": "string",
                            "description": "The new class to use (e.g., 'bg-green-500', 'text-red-500')"
                        }
                    },
                    "required": ["old_class", "new_class"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_and_replace",
                "description": "Find and replace text/HTML directly in the source. Use for targeted changes when selectors don't work.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "find": {
                            "type": "string",
                            "description": "The exact text or HTML to find"
                        },
                        "replace": {
                            "type": "string",
                            "description": "The text or HTML to replace it with"
                        }
                    },
                    "required": ["find", "replace"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "finalize_edit",
                "description": "Call this when you're done editing. The system will use the HTML from your previous edit tools automatically. Just provide a summary of what you changed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Brief summary of changes made (e.g., 'Changed header color from blue to green')"
                        }
                    },
                    "required": ["summary"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_element",
                "description": "Add a new HTML element to the page. Use this to add new sections, components, or elements.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_selector": {
                            "type": "string",
                            "description": "CSS selector for the parent element to add to (e.g., 'main', 'body', 'section.hero')"
                        },
                        "html": {
                            "type": "string",
                            "description": "The HTML to add (can be a complete section or element)"
                        },
                        "position": {
                            "type": "string",
                            "enum": ["before_begin", "after_begin", "before_end", "after_end"],
                            "description": "Where to insert: before_begin (before parent), after_begin (first child), before_end (last child), after_end (after parent)"
                        }
                    },
                    "required": ["parent_selector", "html", "position"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "remove_element",
                "description": "Remove an element from the page. Use this when user asks to delete or remove something.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for the element to remove"
                        }
                    },
                    "required": ["selector"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "capture_screenshot",
                "description": "Capture a screenshot of the current page state or a specific element. Use this to visually verify your changes or see the current state of the page. The screenshot will be shown to you.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "Optional CSS selector to capture just a specific element. Leave empty for full page."
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why you're capturing this screenshot (e.g., 'verify color change', 'check layout')"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_element_visual_info",
                "description": "Get visual information about the selected element including its current colors, computed styles, and position on the page. Useful for understanding what color to change from.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for the element. If empty, uses the currently selected element."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_reference_url",
                "description": "Fetch an external website URL to use as a design reference. This captures a screenshot and extracts design elements (colors, fonts, layout patterns) that you can then apply to the current page. Use this when the user says 'make it look like [URL]' or 'take reference from [URL]'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The full URL to fetch (e.g., 'https://example.com')"
                        },
                        "focus_area": {
                            "type": "string",
                            "description": "Optional: specific area to focus on (e.g., 'hero section', 'navigation', 'footer', 'color scheme', 'typography')"
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    ]

    def __init__(self, model: str = None):
        """Initialize the editing agent."""
        # Use OpenRouter API with Claude Sonnet 4
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = model or "anthropic/claude-sonnet-4"  # Claude Sonnet 4 via OpenRouter
        self.playwright_url = settings.PLAYWRIGHT_SERVICE_URL
        self.current_html = ""
        self.selected_element = None  # Store for auto-injection in tools
        self.max_iterations = 15  # Increased for complex multi-step edits
        self.temperature = 0.3  # Higher for creative and complex edits

        # Browserbase integration (cloud browser)
        self.browserbase: BrowserbaseService = get_browserbase_service()
        self.visual_verifier: VisualVerificationService = get_visual_verification_service()
        self.use_browserbase = self.browserbase.is_available
        self.screenshots: List[bytes] = []  # Store screenshots for verification
        self.session_replay_url: Optional[str] = None
        self.reference_screenshot: Optional[bytes] = None  # Store reference URL screenshot

        logger.info(f"Initialized EditingAgent with model: {self.model}")
        logger.info(f"Browserbase available: {self.use_browserbase}")

    def _convert_tools_to_anthropic_format(self) -> List[Dict[str, Any]]:
        """Convert OpenRouter tool format to Anthropic format."""
        anthropic_tools = []
        for tool in self.EDITING_TOOLS:
            func = tool.get("function", {})
            anthropic_tools.append({
                "name": func.get("name"),
                "description": func.get("description"),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}})
            })
        return anthropic_tools

    def _convert_messages_to_anthropic_format(self, messages: List[Dict]) -> List[Dict]:
        """Convert messages to Anthropic format, handling initial user message properly."""
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "user":
                # Handle different content types
                if isinstance(content, str):
                    anthropic_messages.append({"role": "user", "content": content})
                elif isinstance(content, list):
                    # Already in block format
                    anthropic_messages.append({"role": "user", "content": content})
                else:
                    anthropic_messages.append(msg)
            elif role == "assistant":
                anthropic_messages.append(msg)
            else:
                anthropic_messages.append(msg)

        return anthropic_messages

    def _build_message_with_visual_context(
        self,
        user_prompt: str,
        screenshot: Optional[bytes] = None
    ) -> Any:
        """
        Build a message with visual context from screenshot.

        If a screenshot is available, creates a multi-part message with both
        text and image content. This gives the AI visual context so it can
        make accurate edits without asking questions.

        Args:
            user_prompt: The text prompt with edit instruction and HTML
            screenshot: Optional screenshot bytes from Browserbase

        Returns:
            String (text only) or list (multi-part with image)
        """
        if not screenshot:
            return user_prompt

        try:
            # Encode screenshot as base64
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            # Create multi-part message with image and text
            # Note: Claude models support vision through OpenRouter
            return [
                {
                    "type": "text",
                    "text": f"""## VISUAL CONTEXT
I've captured a screenshot of the current page. Use this to understand:
- What the page looks like visually
- Where elements are positioned
- Current colors, fonts, and styling
- The overall design aesthetic

DO NOT ask questions about the design - you can SEE it in the screenshot.
Make your best judgment based on this visual context.

{user_prompt}"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{screenshot_b64}"
                    }
                }
            ]
        except Exception as e:
            logger.warning(f"Failed to encode screenshot: {e}")
            return user_prompt

    async def edit(
        self,
        html: str,
        instruction: str,
        max_iterations: int = 15,
        design_context: Optional[Dict[str, Any]] = None,
        selected_element: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Edit HTML based on user instruction using tool-based agent.

        Args:
            html: Current HTML content
            instruction: User's edit instruction
            max_iterations: Max tool use iterations (default 15 for complex edits)
            design_context: Extracted design metadata (fonts, colors, sections)
            selected_element: Currently selected element info (selector, tag, classes)

        Returns:
            Edited HTML and metadata
        """
        try:
            logger.info(f"EditingAgent: Starting edit - {instruction[:50]}...")
            if design_context:
                logger.info(f"EditingAgent: Using design context with template: {design_context.get('template_id', 'unknown')}")
            if selected_element:
                logger.info(f"EditingAgent: Target element: {selected_element.get('selector', 'none')}")

            self.current_html = html
            self.selected_element = selected_element  # Store for auto-injection in tools
            self.current_instruction = instruction  # Store for safeguard checks
            self.screenshots = []  # Reset screenshots for this edit session
            self.session_replay_url = None
            self.reference_screenshot = None  # Reset reference screenshot for this edit session

            # Capture initial screenshot via local Playwright (fast, no cloud latency)
            initial_screenshot = await self._capture_local_screenshot(html)
            if initial_screenshot:
                self.screenshots.append(initial_screenshot)
                logger.info("EditingAgent: Captured initial screenshot via local Playwright")

            # Log what we received
            logger.info(f"EditingAgent: Instruction = '{instruction}'")
            if selected_element:
                logger.info(f"EditingAgent: Selected element selector = '{selected_element.get('selector', 'NONE')}'")
                logger.info(f"EditingAgent: Selected element tag = '{selected_element.get('tag', 'NONE')}'")
                logger.info(f"EditingAgent: Selected element classes = '{selected_element.get('classes', [])}'")
            else:
                logger.warning("EditingAgent: NO SELECTED ELEMENT - will edit globally!")

            # Build context-aware system prompt
            system_prompt = build_editing_system_prompt(
                design_context=design_context,
                selected_element=selected_element
            )

            # Build user prompt with HTML and selected element
            user_prompt = build_user_prompt(
                instruction=instruction,
                html=html,
                design_context=design_context,
                selected_element=selected_element
            )

            # Build the initial message with visual context if screenshot available
            initial_message_content = self._build_message_with_visual_context(
                user_prompt=user_prompt,
                screenshot=self.screenshots[0] if self.screenshots else None
            )

            # Run agent with tools
            messages = [{"role": "user", "content": initial_message_content}]
            iteration = 0
            final_html = html
            edit_summary = ""

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"EditingAgent: Iteration {iteration}")

                # Call OpenRouter API with tools
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": "https://topmate.io",
                                "X-Title": "AI Website Builder"
                            },
                            json={
                                "model": self.model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    *messages
                                ],
                                "tools": self.EDITING_TOOLS,
                                "max_tokens": 4096,
                                "temperature": self.temperature
                            }
                        )

                        if response.status_code != 200:
                            error_text = response.text
                            logger.error(f"OpenRouter API error: {response.status_code} - {error_text}")
                            return {
                                "success": False,
                                "error": f"API error: {response.status_code}",
                                "html": html
                            }

                        result = response.json()
                except Exception as e:
                    logger.error(f"OpenRouter API error: {e}")
                    return {
                        "success": False,
                        "error": f"API error: {str(e)}",
                        "html": html
                    }

                # Get the assistant's response
                choice = result.get("choices", [{}])[0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "")

                # Check if we're done (no tool calls)
                if finish_reason == "stop" or not message.get("tool_calls"):
                    content = message.get("content", "")
                    if content:
                        logger.info(f"EditingAgent: Final response - {content[:100]}")
                    break

                # Process tool calls
                tool_calls = message.get("tool_calls", [])
                tool_results = []

                for tool_call in tool_calls:
                    tool_name = tool_call.get("function", {}).get("name")
                    tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                    tool_id = tool_call.get("id")

                    try:
                        tool_input = json.loads(tool_args_str)
                    except json.JSONDecodeError:
                        tool_input = {}

                    logger.info(f"EditingAgent: Using tool '{tool_name}'")

                    # Execute the tool
                    tool_result = await self._execute_tool(tool_name, tool_input)

                    # Check if finalize was called
                    if tool_name == "finalize_edit":
                        # Always use self.current_html - it has been modified by previous tools
                        edit_summary = tool_input.get("summary", "Edit completed")
                        final_html = self.current_html

                        logger.info(f"EditingAgent: finalize_edit called - summary: {edit_summary}")
                        logger.info(f"EditingAgent: Using self.current_html with length: {len(final_html)}")

                        return {
                            "success": True,
                            "html": final_html,
                            "summary": edit_summary,
                            "iterations": iteration,
                            "screenshots_captured": len(self.screenshots)
                        }

                    # Update current HTML if edit was successful
                    if tool_result.get("success") and tool_result.get("html"):
                        self.current_html = tool_result["html"]

                    # For fetch_reference_url, include screenshot description in result
                    tool_result_for_message = {k: v for k, v in tool_result.items() if k != "screenshot"}
                    if tool_name == "fetch_reference_url" and tool_result.get("has_screenshot"):
                        tool_result_for_message["visual_reference_available"] = True
                        tool_result_for_message["instruction"] = (
                            "Screenshot of reference URL captured. Use the design patterns, colors, "
                            "and layout you see to style the current page similarly."
                        )

                    tool_results.append({
                        "tool_call_id": tool_id,
                        "role": "tool",
                        "content": json.dumps(tool_result_for_message)
                    })

                # Add assistant response and tool results to messages (OpenRouter format)
                messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
                messages.extend(tool_results)

                # If we have a reference screenshot, add it as a user message with the image
                if self.reference_screenshot and len(self.screenshots) > 0:
                    try:
                        ref_screenshot_b64 = base64.b64encode(self.reference_screenshot).decode('utf-8')
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Here is the screenshot of the reference website. Use this as visual reference for your edits - match the colors, layout, and overall style."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{ref_screenshot_b64}"
                                    }
                                }
                            ]
                        })
                        # Only include once
                        self.reference_screenshot = None
                    except Exception as e:
                        logger.warning(f"Failed to include reference screenshot: {e}")

            # If we exhausted iterations, return current state
            return {
                "success": True,
                "html": self.current_html,
                "summary": edit_summary or "Edit completed",
                "iterations": iteration,
                "screenshots_captured": len(self.screenshots)
            }

        except Exception as e:
            logger.error(f"EditingAgent: Error - {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "html": html  # Return original on error
            }

    async def _execute_tool(self, tool_name: str, tool_input: Dict) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        try:
            # Helper to get selector with auto-injection from selected_element
            def get_selector():
                selector = tool_input.get("selector", "")
                if not selector and self.selected_element:
                    selector = self.selected_element.get("selector", "")
                    logger.info(f"EditingAgent: AUTO-INJECTING selector: '{selector}'")
                return selector

            if tool_name == "analyze_dom":
                return await self._analyze_dom(tool_input.get("html", self.current_html))

            elif tool_name == "edit_text":
                result = await self._edit_with_fallback(
                    html=self.current_html,  # Always use current state
                    selector=get_selector(),
                    edit_type="text",
                    edit_value=tool_input.get("new_text")
                )
                # Update current_html if successful
                if result.get("success") and result.get("html"):
                    self.current_html = result["html"]
                    logger.info(f"EditingAgent: edit_text SUCCESS - updated self.current_html")
                return result

            elif tool_name == "edit_style":
                result = await self._edit_with_fallback(
                    html=self.current_html,  # Always use current state
                    selector=get_selector(),
                    edit_type="style",
                    edit_value=tool_input.get("styles")
                )
                # Update current_html if successful
                if result.get("success") and result.get("html"):
                    self.current_html = result["html"]
                    logger.info(f"EditingAgent: edit_style SUCCESS - updated self.current_html")
                return result

            elif tool_name == "edit_attribute":
                result = await self._edit_with_fallback(
                    html=self.current_html,  # Always use current state
                    selector=get_selector(),
                    edit_type="attribute",
                    edit_value={
                        "name": tool_input.get("attribute"),
                        "value": tool_input.get("value")
                    }
                )
                # Update current_html if successful
                if result.get("success") and result.get("html"):
                    self.current_html = result["html"]
                    logger.info(f"EditingAgent: edit_attribute SUCCESS - updated self.current_html")
                return result

            elif tool_name == "replace_element":
                new_html = tool_input.get("new_html", "")

                # SAFEGUARD: Block if new_html is empty or too small (likely trying to remove)
                if not new_html or len(new_html.strip()) < 10:
                    logger.warning(f"EditingAgent: replace_element BLOCKED - new_html is empty or too small")
                    return {
                        "success": False,
                        "error": "BLOCKED: Cannot replace with empty content. Use modify_class to change appearance instead."
                    }

                result = await self._edit_with_fallback(
                    html=self.current_html,  # Always use current state
                    selector=get_selector(),
                    edit_type="replace",
                    edit_value=new_html
                )
                # Update current_html if successful
                if result.get("success") and result.get("html"):
                    self.current_html = result["html"]
                    logger.info(f"EditingAgent: replace_element SUCCESS - updated self.current_html")
                return result

            elif tool_name == "modify_class":
                # Targeted class replacement using BeautifulSoup
                from bs4 import BeautifulSoup

                selector = tool_input.get("selector", "")
                old_class = tool_input.get("old_class", "")
                new_class = tool_input.get("new_class", "")

                # SMART SELECTOR OVERRIDE: If user selected an element, prioritize it
                if self.selected_element:
                    selected_selector = self.selected_element.get("selector", "")
                    selected_classes = self.selected_element.get("classes", [])
                    color_classes = self.selected_element.get("color_classes", [])

                    # If AI is trying to edit body/html but user selected something specific, override
                    if selector in ["body", "html", "main", ""] or not selector:
                        selector = selected_selector
                        logger.info(f"EditingAgent: modify_class - OVERRIDING to selected element: '{selector}'")

                    # If old_class is in the selected element's classes, use selected element
                    elif old_class and selected_classes and old_class in " ".join(selected_classes):
                        selector = selected_selector
                        logger.info(f"EditingAgent: modify_class - old_class found in selected element, using: '{selector}'")

                    # SMART BACKGROUND COLOR DETECTION: If changing bg-* class but old_class not specified correctly
                    # Auto-detect the current bg-* class from color_classes
                    if new_class.startswith("bg-") and color_classes:
                        current_bg_class = None
                        for cc in color_classes:
                            if cc.startswith("bg-"):
                                current_bg_class = cc
                                break

                        # If old_class doesn't match any bg class but we found one, use it
                        if current_bg_class and old_class != current_bg_class:
                            if not old_class or old_class not in " ".join(selected_classes):
                                logger.info(f"EditingAgent: modify_class - AUTO-DETECTED bg class: '{current_bg_class}' -> '{new_class}'")
                                old_class = current_bg_class

                # Get outer_html for precise targeting (most reliable method)
                outer_html = self.selected_element.get("outer_html", "") if self.selected_element else ""

                logger.info(f"EditingAgent: modify_class - selector='{selector}', '{old_class}' -> '{new_class}'")
                logger.info(f"EditingAgent: modify_class - outer_html available: {bool(outer_html)}, length: {len(outer_html) if outer_html else 0}")

                if not old_class or not new_class:
                    return {"success": False, "error": "Missing old_class or new_class"}

                # STRATEGY: Try methods in order of precision
                # 1. outer_html replacement (MOST PRECISE - guaranteed to target exact element)
                # 2. BeautifulSoup selector (good but may match wrong element)
                # 3. Global replacement (LAST RESORT - affects all occurrences)

                # METHOD 1: outer_html replacement (MOST RELIABLE)
                if outer_html and old_class in outer_html:
                    logger.info(f"EditingAgent: modify_class - trying outer_html method (MOST PRECISE)")
                    new_outer_html = outer_html.replace(old_class, new_class)

                    # Check if outer_html exists in current HTML (exact match)
                    if outer_html in self.current_html:
                        modified_html = self.current_html.replace(outer_html, new_outer_html, 1)  # Replace only FIRST occurrence
                        if modified_html != self.current_html:
                            self.current_html = modified_html
                            logger.info(f"EditingAgent: modify_class SUCCESS (outer_html - PRECISE)")
                            return {
                                "success": True,
                                "html": modified_html,
                                "message": f"Changed class '{old_class}' to '{new_class}' on EXACT selected element"
                            }
                    else:
                        # Try with normalized whitespace
                        import re
                        normalized_outer = re.sub(r'\s+', ' ', outer_html.strip())
                        normalized_html = re.sub(r'\s+', ' ', self.current_html)

                        if normalized_outer in normalized_html:
                            # Find and replace in original HTML using fuzzy match
                            # Find a unique substring from outer_html that exists in current_html
                            class_pattern = re.escape(f'class="') + r'[^"]*' + re.escape(old_class) + r'[^"]*' + re.escape('"')
                            match = re.search(class_pattern, outer_html)
                            if match:
                                old_class_attr = match.group(0)
                                new_class_attr = old_class_attr.replace(old_class, new_class)
                                if old_class_attr in self.current_html:
                                    modified_html = self.current_html.replace(old_class_attr, new_class_attr, 1)
                                    if modified_html != self.current_html:
                                        self.current_html = modified_html
                                        logger.info(f"EditingAgent: modify_class SUCCESS (class attr replacement)")
                                        return {
                                            "success": True,
                                            "html": modified_html,
                                            "message": f"Changed class '{old_class}' to '{new_class}' via class attribute"
                                        }

                        logger.warning(f"EditingAgent: outer_html exact match not found, trying fingerprint method")

                # METHOD 1B: Text content fingerprint targeting
                # Use the element's text content to find the specific element
                if self.selected_element:
                    text_content = self.selected_element.get("text", "")
                    tag = self.selected_element.get("tag", "")

                    if text_content and len(text_content) > 5 and old_class in self.current_html:
                        import re
                        # Create a pattern to find the element containing this text with the old_class
                        # Escape special regex characters in text
                        escaped_text = re.escape(text_content[:50].strip())

                        # Pattern: find tag with old_class that contains our text
                        # This pattern finds: <tag ... class="...old_class..." ...>...text...</tag>
                        pattern = rf'(<{tag}[^>]*class="[^"]*){old_class}([^"]*"[^>]*>(?:[^<]*{escaped_text}|{escaped_text}[^<]*))'

                        match = re.search(pattern, self.current_html, re.IGNORECASE | re.DOTALL)
                        if match:
                            logger.info(f"EditingAgent: modify_class - found element via text fingerprint")
                            # Replace only in this specific match
                            start, end = match.span()
                            matched_text = match.group(0)
                            new_matched_text = matched_text.replace(old_class, new_class, 1)
                            modified_html = self.current_html[:start] + new_matched_text + self.current_html[end:]

                            if modified_html != self.current_html:
                                self.current_html = modified_html
                                logger.info(f"EditingAgent: modify_class SUCCESS (text fingerprint)")
                                return {
                                    "success": True,
                                    "html": modified_html,
                                    "message": f"Changed class '{old_class}' to '{new_class}' on element containing '{text_content[:30]}...'"
                                }

                        logger.warning(f"EditingAgent: fingerprint pattern didn't match, trying selector")

                # METHOD 2: BeautifulSoup selector
                if selector:
                    try:
                        soup = BeautifulSoup(self.current_html, 'html.parser')
                        element = soup.select_one(selector)

                        if element:
                            logger.info(f"EditingAgent: modify_class - found element with selector '{selector}'")
                            current_classes = element.get('class', [])
                            if isinstance(current_classes, str):
                                current_classes = current_classes.split()

                            if old_class in current_classes:
                                new_classes = [new_class if c == old_class else c for c in current_classes]
                                element['class'] = new_classes
                                modified_html = str(soup)
                                self.current_html = modified_html
                                logger.info(f"EditingAgent: modify_class SUCCESS (BeautifulSoup selector)")
                                return {
                                    "success": True,
                                    "html": modified_html,
                                    "message": f"Changed class '{old_class}' to '{new_class}' on element '{selector}'"
                                }
                            else:
                                # Class not on element, try adding new class
                                current_classes.append(new_class)
                                element['class'] = current_classes
                                modified_html = str(soup)
                                self.current_html = modified_html
                                logger.info(f"EditingAgent: modify_class - added {new_class} (old class not on element)")
                                return {
                                    "success": True,
                                    "html": modified_html,
                                    "message": f"Added class '{new_class}' to element '{selector}' ('{old_class}' was not on this element)"
                                }
                        else:
                            logger.warning(f"EditingAgent: selector '{selector}' not found in DOM")
                    except Exception as e:
                        logger.warning(f"EditingAgent: BeautifulSoup selector failed: {e}")

                # METHOD 3: Global replacement (LAST RESORT - WARN USER)
                if old_class in self.current_html:
                    logger.warning(f"EditingAgent: modify_class - using GLOBAL replacement (all methods failed)")
                    modified_html = self.current_html.replace(old_class, new_class)
                    self.current_html = modified_html
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": f"WARNING: Changed ALL '{old_class}' to '{new_class}' globally (targeted methods failed)"
                    }

                # FALLBACK: If we're trying to add a bg/text/border class but couldn't find old_class,
                # try to ADD the new class to the selected element instead
                if self.selected_element and new_class and (
                    new_class.startswith("bg-") or
                    new_class.startswith("text-") or
                    new_class.startswith("border-")
                ):
                    outer_html = self.selected_element.get("outer_html", "")
                    if outer_html and 'class="' in outer_html:
                        # Find the class attribute and add the new class to it
                        import re
                        class_match = re.search(r'class="([^"]*)"', outer_html)
                        if class_match:
                            current_classes = class_match.group(1)
                            new_classes = f"{current_classes} {new_class}"
                            new_outer_html = outer_html.replace(f'class="{current_classes}"', f'class="{new_classes}"')

                            if outer_html in self.current_html:
                                modified_html = self.current_html.replace(outer_html, new_outer_html, 1)
                                if modified_html != self.current_html:
                                    self.current_html = modified_html
                                    logger.info(f"EditingAgent: modify_class - ADDED '{new_class}' (element had no {old_class})")
                                    return {
                                        "success": True,
                                        "html": modified_html,
                                        "message": f"Added class '{new_class}' to element ('{old_class}' was not present)"
                                    }

                logger.info(f"EditingAgent: modify_class FAILED - class '{old_class}' not found anywhere")
                return {"success": False, "error": f"Class '{old_class}' not found in HTML"}

            elif tool_name == "find_and_replace":
                # Direct string replacement
                find_str = tool_input.get("find", "")
                replace_str = tool_input.get("replace", "")
                logger.info(f"EditingAgent: find_and_replace - finding: '{find_str[:100]}...'")
                if find_str:
                    if find_str in self.current_html:
                        modified_html = self.current_html.replace(find_str, replace_str)
                        self.current_html = modified_html
                        logger.info(f"EditingAgent: find_and_replace SUCCESS")
                        return {
                            "success": True,
                            "html": modified_html,
                            "message": f"Replaced '{find_str[:50]}...' successfully"
                        }
                    else:
                        logger.info(f"EditingAgent: find_and_replace FAILED - text not found")
                        return {"success": False, "error": f"Text '{find_str[:50]}...' not found in HTML"}
                return {"success": False, "error": "Missing find parameter"}

            elif tool_name == "finalize_edit":
                # This is handled in the main loop
                return {"success": True, "message": "Finalized"}

            elif tool_name == "add_element":
                # Add new HTML element to the page
                parent_selector = tool_input.get("parent_selector", "")
                new_html = tool_input.get("html", "")
                position = tool_input.get("position", "before_end")

                if not parent_selector or not new_html:
                    return {"success": False, "error": "parent_selector and html are required"}

                logger.info(f"EditingAgent: add_element - parent='{parent_selector}', position='{position}'")

                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(self.current_html, 'html.parser')
                    parent = soup.select_one(parent_selector)

                    if not parent:
                        return {"success": False, "error": f"Parent element not found: {parent_selector}"}

                    new_element = BeautifulSoup(new_html, 'html.parser')

                    if position == "before_begin":
                        parent.insert_before(new_element)
                    elif position == "after_begin":
                        parent.insert(0, new_element)
                    elif position == "before_end":
                        parent.append(new_element)
                    elif position == "after_end":
                        parent.insert_after(new_element)
                    else:
                        parent.append(new_element)  # Default to before_end

                    modified_html = str(soup)
                    self.current_html = modified_html
                    logger.info(f"EditingAgent: add_element SUCCESS - added to {parent_selector}")
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": f"Added element to {parent_selector} at position {position}"
                    }
                except Exception as e:
                    logger.error(f"EditingAgent: add_element error: {e}")
                    return {"success": False, "error": str(e)}

            elif tool_name == "remove_element":
                # Remove element from the page - BUT ONLY IF USER EXPLICITLY ASKED
                selector = tool_input.get("selector", "")

                # SAFEGUARD: Check if user actually asked for removal
                # This prevents AI from removing elements without explicit permission
                removal_keywords = ["remove", "delete", "hide", "get rid of", "take out", "eliminate"]
                instruction_lower = self.current_instruction.lower() if hasattr(self, 'current_instruction') else ""

                user_asked_for_removal = any(keyword in instruction_lower for keyword in removal_keywords)

                if not user_asked_for_removal:
                    logger.warning(f"EditingAgent: remove_element BLOCKED - user did not ask for removal")
                    return {
                        "success": False,
                        "error": "BLOCKED: Cannot remove elements unless user explicitly asks. Use modify_class or edit_style to change appearance instead."
                    }

                # Auto-inject selector from selected_element if not provided
                if not selector and self.selected_element:
                    selector = self.selected_element.get("selector", "")

                if not selector:
                    return {"success": False, "error": "selector is required"}

                logger.info(f"EditingAgent: remove_element - selector='{selector}'")

                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(self.current_html, 'html.parser')
                    elements = soup.select(selector)

                    if not elements:
                        return {"success": False, "error": f"Element not found: {selector}"}

                    removed_count = 0
                    for element in elements:
                        element.decompose()
                        removed_count += 1

                    modified_html = str(soup)
                    self.current_html = modified_html
                    logger.info(f"EditingAgent: remove_element SUCCESS - removed {removed_count} element(s)")
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": f"Removed {removed_count} element(s) matching {selector}"
                    }
                except Exception as e:
                    logger.error(f"EditingAgent: remove_element error: {e}")
                    return {"success": False, "error": str(e)}

            elif tool_name == "capture_screenshot":
                # Capture a screenshot for visual verification via local Playwright
                selector = tool_input.get("selector", "")
                reason = tool_input.get("reason", "visual check")

                # Auto-inject selector from selected_element if not provided
                if not selector and self.selected_element:
                    selector = self.selected_element.get("selector", "")

                try:
                    # Capture via local Playwright (fast, no cloud latency)
                    screenshot = await self._capture_local_screenshot(
                        self.current_html,
                        selector=selector if selector else None
                    )
                    if screenshot:
                        self.screenshots.append(screenshot)
                        logger.info(f"EditingAgent: capture_screenshot SUCCESS - reason: {reason}, selector: {selector or 'full page'}")
                        return {
                            "success": True,
                            "message": f"Screenshot captured for: {reason}",
                            "screenshot_index": len(self.screenshots) - 1,
                            "has_visual": True
                        }
                    else:
                        return {"success": False, "error": "Failed to capture screenshot"}
                except Exception as e:
                    logger.warning(f"EditingAgent: capture_screenshot failed: {e}")
                    return {"success": False, "error": str(e)}

            elif tool_name == "get_element_visual_info":
                # Get computed styles and visual info about an element via local Playwright
                selector = tool_input.get("selector", "")

                # Auto-inject selector from selected_element if not provided
                if not selector and self.selected_element:
                    selector = self.selected_element.get("selector", "")

                if not selector:
                    return {"success": False, "error": "No selector provided and no element selected"}

                try:
                    # Get visual info via local Playwright service
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(
                            f"{self.playwright_url}/get-element-visual-info",
                            json={
                                "html": self.current_html,
                                "selector": selector
                            }
                        )

                        if response.status_code == 200:
                            data = response.json()
                            if data.get("success"):
                                logger.info(f"EditingAgent: get_element_visual_info SUCCESS - {selector}")
                                return {
                                    "success": True,
                                    "element": data.get("element"),
                                    "message": f"Visual info for element: {selector}"
                                }

                    # Fallback to selected_element data
                    if self.selected_element:
                        return {
                            "success": True,
                            "element": {
                                "tag": self.selected_element.get("tag"),
                                "classes": self.selected_element.get("classes", []),
                                "color_classes": self.selected_element.get("color_classes", []),
                                "text": self.selected_element.get("text", "")[:100]
                            },
                            "message": "Visual info from selected element metadata"
                        }
                    return {"success": False, "error": f"Element not found: {selector}"}
                except Exception as e:
                    logger.warning(f"EditingAgent: get_element_visual_info failed: {e}")
                    # Fallback to selected_element data
                    if self.selected_element:
                        return {
                            "success": True,
                            "element": {
                                "tag": self.selected_element.get("tag"),
                                "classes": self.selected_element.get("classes", []),
                                "color_classes": self.selected_element.get("color_classes", []),
                                "text": self.selected_element.get("text", "")[:100]
                            },
                            "message": "Visual info from selected element (fallback)"
                        }
                    return {"success": False, "error": str(e)}

            elif tool_name == "fetch_reference_url":
                # Fetch external URL and extract design reference
                url = tool_input.get("url", "")
                focus_area = tool_input.get("focus_area", "")

                if not url:
                    return {"success": False, "error": "URL is required"}

                # Ensure URL has protocol
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url

                logger.info(f"EditingAgent: fetch_reference_url - fetching {url}, focus: {focus_area or 'full page'}")

                try:
                    result = await self._fetch_reference_url(url, focus_area)
                    if result.get("success"):
                        # Store the reference screenshot for the AI to see
                        if result.get("screenshot"):
                            self.reference_screenshot = result["screenshot"]
                            self.screenshots.append(result["screenshot"])
                        return result
                    else:
                        return {"success": False, "error": result.get("error", "Failed to fetch URL")}
                except Exception as e:
                    logger.error(f"EditingAgent: fetch_reference_url error: {e}")
                    return {"success": False, "error": str(e)}

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {str(e)}")
            return {"success": False, "error": str(e)}

    async def _analyze_dom(self, html: str) -> Dict[str, Any]:
        """Analyze DOM structure via Playwright service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.playwright_url}/get-dom-detailed",
                    json={"html": html, "include_bounds": False}
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "dom": data.get("dom"),
                        "message": "DOM analyzed successfully"
                    }
                else:
                    return {"success": False, "error": "Failed to analyze DOM"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _edit_via_playwright(
        self,
        html: str,
        selector: str,
        edit_type: str,
        edit_value: Any
    ) -> Dict[str, Any]:
        """Execute edit via Playwright service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.playwright_url}/edit-component",
                    json={
                        "html": html,
                        "selector": selector,
                        "edit_type": edit_type,
                        "edit_value": edit_value
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return {
                            "success": True,
                            "html": data.get("html"),
                            "message": f"Successfully edited {selector}"
                        }
                    else:
                        return {"success": False, "error": data.get("error")}
                else:
                    return {"success": False, "error": f"Playwright error: {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _edit_via_browserbase(
        self,
        selector: str,
        edit_type: str,
        edit_value: Any
    ) -> Dict[str, Any]:
        """
        Execute edit via Browserbase cloud browser.

        This is an alternative to local Playwright that provides:
        - Cloud-based execution (no local resources)
        - Session replay for debugging
        - Screenshot capture for verification

        Args:
            selector: CSS selector for target element
            edit_type: Type of edit (text, style, class, attribute, replace)
            edit_value: Value to apply

        Returns:
            Dict with success, html, and message
        """
        if not self.browserbase.is_available:
            return {"success": False, "error": "Browserbase not available"}

        try:
            # Map edit types to Browserbase execute_edit types
            type_mapping = {
                "text": "text",
                "style": "style",
                "class": "class",
                "attribute": "attribute",
                "replace": "outerHtml"
            }

            bb_edit_type = type_mapping.get(edit_type, edit_type)

            # Prepare value based on type
            if edit_type == "style" and isinstance(edit_value, dict):
                edit_value = json.dumps(edit_value)
            elif edit_type == "attribute" and isinstance(edit_value, dict):
                edit_value = f"{edit_value.get('name')}={edit_value.get('value', '')}"

            # Execute the edit
            result = await self.browserbase.execute_edit(
                selector=selector,
                edit_type=bb_edit_type,
                value=str(edit_value)
            )

            if result.get("success"):
                # Get the updated HTML from browser
                html = await self.browserbase.get_html()
                if html:
                    return {
                        "success": True,
                        "html": html,
                        "message": f"Successfully edited {selector} via Browserbase"
                    }
                return {"success": False, "error": "Failed to get updated HTML"}
            else:
                return {"success": False, "error": result.get("error", "Edit failed")}

        except Exception as e:
            logger.error(f"Browserbase edit error: {e}")
            return {"success": False, "error": str(e)}

    async def _edit_with_fallback(
        self,
        html: str,
        selector: str,
        edit_type: str,
        edit_value: Any
    ) -> Dict[str, Any]:
        """
        Execute edit with Playwright first, fallback to BeautifulSoup.

        Args:
            html: Current HTML
            selector: CSS selector
            edit_type: Type of edit
            edit_value: Value to apply

        Returns:
            Edit result dict
        """
        # Try Playwright first
        result = await self._edit_via_playwright(html, selector, edit_type, edit_value)

        # If Playwright failed, use BeautifulSoup fallback
        if not result.get("success"):
            logger.info(f"EditingAgent: Playwright failed, using BeautifulSoup fallback for {edit_type}")
            result = await self._edit_via_beautifulsoup(html, selector, edit_type, edit_value)

        return result

    def _simplify_selector(self, selector: str) -> str:
        """
        Simplify a CSS selector by removing Tailwind arbitrary value classes.
        e.g., 'h1.text-6xl.font-bold.leading-[0.9]' -> 'h1.text-6xl.font-bold'
        """
        import re
        # Remove classes with brackets (Tailwind arbitrary values)
        # Match .classname-[value] or .classname[value]
        simplified = re.sub(r'\.[a-zA-Z0-9_-]+\[[^\]]+\]', '', selector)
        # Also handle standalone [attr] selectors that might cause issues
        simplified = re.sub(r'\[[^\]]*\]', '', simplified)
        # Clean up any double dots or trailing dots
        simplified = re.sub(r'\.+', '.', simplified).rstrip('.')
        return simplified

    async def _edit_via_beautifulsoup(
        self,
        html: str,
        selector: str,
        edit_type: str,
        edit_value: Any
    ) -> Dict[str, Any]:
        """
        Execute edit via BeautifulSoup (fallback when Playwright is unavailable).

        Args:
            html: Current HTML
            selector: CSS selector
            edit_type: Type of edit (text, style, attribute, replace)
            edit_value: Value to apply

        Returns:
            Edit result dict
        """
        try:
            from bs4 import BeautifulSoup
            import re

            soup = BeautifulSoup(html, 'html.parser')
            element = None

            # Try original selector first
            try:
                element = soup.select_one(selector) if selector else None
            except Exception as selector_error:
                logger.warning(f"EditingAgent: Original selector failed: {selector_error}")
                # Try simplified selector (remove Tailwind arbitrary values)
                simplified = self._simplify_selector(selector)
                if simplified and simplified != selector:
                    logger.info(f"EditingAgent: Trying simplified selector: {simplified}")
                    try:
                        element = soup.select_one(simplified)
                    except Exception:
                        pass

                # If still no element, try just the tag name
                if not element and selector:
                    # Extract tag name from selector (e.g., "div.class > h1.class" -> "h1")
                    tag_match = re.search(r'([a-zA-Z0-9]+)(?:\.|#|$|\s|>|:)', selector.split('>')[-1].strip())
                    if tag_match:
                        tag_name = tag_match.group(1)
                        logger.info(f"EditingAgent: Trying tag-only selector: {tag_name}")
                        elements = soup.find_all(tag_name)
                        if elements:
                            # If we have selected element text, try to match by content
                            if self.selected_element and self.selected_element.get("text"):
                                target_text = self.selected_element["text"].strip()[:50]
                                for el in elements:
                                    if target_text in el.get_text():
                                        element = el
                                        logger.info(f"EditingAgent: Found element by text content match")
                                        break
                            if not element:
                                element = elements[0]  # Default to first match

            if not element:
                # Last resort: try string replacement for text edits
                if edit_type == "text" and self.selected_element:
                    old_text = self.selected_element.get("text", "").strip()
                    if old_text and old_text in html:
                        modified_html = html.replace(old_text, edit_value, 1)
                        if modified_html != html:
                            logger.info(f"EditingAgent: Used direct string replacement for text edit")
                            return {
                                "success": True,
                                "html": modified_html,
                                "message": f"Successfully edited text via string replacement"
                            }

                logger.warning(f"EditingAgent: BeautifulSoup - could not find element for selector '{selector}'")
                return {"success": False, "error": f"Element not found: {selector}"}

            if edit_type == "text":
                # Replace text content
                element.string = edit_value
                logger.info(f"EditingAgent: BeautifulSoup - changed text to '{edit_value[:50]}...'")

            elif edit_type == "style":
                # Add/update inline styles
                existing_style = element.get("style", "")
                if isinstance(edit_value, dict):
                    style_str = "; ".join(f"{k}: {v}" for k, v in edit_value.items())
                else:
                    style_str = str(edit_value)
                element["style"] = f"{existing_style}; {style_str}".strip("; ")
                logger.info(f"EditingAgent: BeautifulSoup - updated styles")

            elif edit_type == "attribute":
                # Set attribute
                if isinstance(edit_value, dict):
                    attr_name = edit_value.get("name")
                    attr_val = edit_value.get("value", "")
                    if attr_name:
                        element[attr_name] = attr_val
                        logger.info(f"EditingAgent: BeautifulSoup - set {attr_name}='{attr_val}'")

            elif edit_type == "replace":
                # Replace entire element HTML
                new_element = BeautifulSoup(edit_value, 'html.parser')
                element.replace_with(new_element)
                logger.info(f"EditingAgent: BeautifulSoup - replaced element")

            else:
                return {"success": False, "error": f"Unknown edit type: {edit_type}"}

            modified_html = str(soup)
            return {
                "success": True,
                "html": modified_html,
                "message": f"Successfully edited {selector} via BeautifulSoup"
            }

        except Exception as e:
            logger.error(f"EditingAgent: BeautifulSoup edit error: {e}")
            return {"success": False, "error": str(e)}

    async def _capture_local_screenshot(
        self,
        html: str,
        selector: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Capture screenshot via local Playwright service.

        This provides visual context without Browserbase cloud latency.
        Typical latency: ~300-500ms (vs ~2-3s with Browserbase)

        Args:
            html: HTML content to render
            selector: Optional CSS selector for element screenshot

        Returns:
            Screenshot as bytes, or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.playwright_url}/screenshot",
                    json={
                        "html": html,
                        "selector": selector,
                        "full_page": False  # Viewport only for speed
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("screenshot"):
                        # Decode base64 to bytes
                        screenshot_bytes = base64.b64decode(data["screenshot"])
                        logger.debug(f"Local screenshot captured: {len(screenshot_bytes)} bytes")
                        return screenshot_bytes

                logger.warning(f"Local screenshot failed: {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"Local screenshot error: {e}")
            return None

    async def _fetch_reference_url(
        self,
        url: str,
        focus_area: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch an external URL and extract design reference information.

        Uses the Playwright service to:
        1. Navigate to the URL
        2. Capture a screenshot
        3. Extract design elements (colors, fonts, layout)

        Args:
            url: The URL to fetch
            focus_area: Optional area to focus on (e.g., 'hero', 'navigation')

        Returns:
            Dict with screenshot, design info, and extracted patterns
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Call the Playwright service to fetch the external URL
                response = await client.post(
                    f"{self.playwright_url}/fetch-url",
                    json={
                        "url": url,
                        "capture_screenshot": True,
                        "extract_design": True,
                        "focus_area": focus_area
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        result = {
                            "success": True,
                            "url": url,
                            "message": f"Successfully fetched {url}",
                            "design_info": data.get("design_info", {}),
                            "has_screenshot": bool(data.get("screenshot"))
                        }

                        # Decode screenshot if present
                        if data.get("screenshot"):
                            result["screenshot"] = base64.b64decode(data["screenshot"])
                            result["screenshot_description"] = (
                                f"Screenshot captured of {url}. "
                                f"Focus area: {focus_area or 'full page'}. "
                                "Use this visual reference to understand the design patterns."
                            )

                        # Include extracted design elements
                        design_info = data.get("design_info", {})
                        if design_info:
                            result["extracted_patterns"] = {
                                "colors": design_info.get("colors", []),
                                "fonts": design_info.get("fonts", []),
                                "layout": design_info.get("layout", ""),
                                "style_notes": design_info.get("style_notes", "")
                            }

                        logger.info(f"EditingAgent: fetch_reference_url SUCCESS - {url}")
                        return result
                    else:
                        return {"success": False, "error": data.get("error", "Failed to fetch URL")}
                else:
                    # Try fallback: fetch HTML directly without screenshot
                    return await self._fetch_reference_url_fallback(url)

        except Exception as e:
            logger.warning(f"EditingAgent: fetch_reference_url error: {e}, trying fallback")
            return await self._fetch_reference_url_fallback(url)

    async def _fetch_reference_url_fallback(self, url: str) -> Dict[str, Any]:
        """
        Fallback method to fetch URL design info without Playwright.
        Uses direct HTTP fetch and extracts design patterns from HTML/CSS.
        """
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                )

                if response.status_code == 200:
                    html = response.text

                    # Extract basic design info from HTML
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')

                    # Extract colors from inline styles and classes
                    colors = set()
                    fonts = set()

                    # Find color patterns in style tags
                    for style in soup.find_all('style'):
                        style_text = style.string or ""
                        # Extract hex colors
                        import re
                        hex_colors = re.findall(r'#[0-9a-fA-F]{3,6}', style_text)
                        colors.update(hex_colors[:10])  # Limit to 10
                        # Extract font families
                        font_matches = re.findall(r'font-family:\s*([^;]+)', style_text)
                        for fm in font_matches[:5]:
                            fonts.add(fm.strip().strip('"\''))

                    # Extract from inline styles
                    for elem in soup.find_all(style=True)[:50]:
                        style_attr = elem.get('style', '')
                        hex_colors = re.findall(r'#[0-9a-fA-F]{3,6}', style_attr)
                        colors.update(hex_colors)

                    # Extract Tailwind color classes
                    tailwind_colors = set()
                    for elem in soup.find_all(class_=True)[:100]:
                        classes = elem.get('class', [])
                        if isinstance(classes, str):
                            classes = classes.split()
                        for cls in classes:
                            if any(c in cls for c in ['bg-', 'text-', 'border-']) and any(c in cls for c in ['blue', 'red', 'green', 'purple', 'pink', 'yellow', 'gray', 'slate', 'zinc']):
                                tailwind_colors.add(cls)

                    return {
                        "success": True,
                        "url": url,
                        "message": f"Fetched {url} (text only, no screenshot available)",
                        "design_info": {
                            "colors": list(colors)[:10],
                            "tailwind_colors": list(tailwind_colors)[:20],
                            "fonts": list(fonts)[:5],
                            "note": "Screenshot not available. Design info extracted from HTML/CSS."
                        },
                        "has_screenshot": False
                    }
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"EditingAgent: fetch_reference_url_fallback error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
editing_agent = EditingAgent()


async def edit_with_agent(
    html: str,
    instruction: str,
    design_context: Optional[Dict[str, Any]] = None,
    selected_element: Optional[Dict[str, Any]] = None,
    max_iterations: int = 15
) -> Dict[str, Any]:
    """
    Convenience function to edit HTML using the editing agent.

    Args:
        html: Current HTML
        instruction: Edit instruction
        design_context: Extracted design metadata (fonts, colors, sections)
        selected_element: Currently selected element info
        max_iterations: Maximum number of tool use iterations

    Returns:
        Edited HTML and metadata
    """
    return await editing_agent.edit(
        html=html,
        instruction=instruction,
        max_iterations=max_iterations,
        design_context=design_context,
        selected_element=selected_element
    )
