"""
Editing Agent for intelligent poster editing using Claude AI.

This agent can:
- Understand the current HTML structure
- Make targeted edits using tools
- Iterate and refine edits autonomously
- Handle complex multi-step editing tasks
- Maintain design consistency
"""
from typing import List, Dict, Any, Optional
import json
import httpx
from app.config import settings
from app.services.editing.editing_system_prompt import (
    build_editing_system_prompt,
    build_user_prompt
)


class PosterEditingAgent:
    """
    Intelligent editing agent with tool use for poster modifications.
    Uses OpenRouter API for AI capabilities.
    """

    # Tool definitions for the agent
    EDITING_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "edit_text",
                "description": "Change the text content of an element. Use a CSS selector to target the element.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the element (e.g., 'h1', '.hero-title', '#main-heading')"
                        },
                        "new_text": {
                            "type": "string",
                            "description": "The new text content"
                        }
                    },
                    "required": ["selector", "new_text"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "modify_class",
                "description": "Replace a CSS class on a specific element. Use this for Tailwind class changes (colors, spacing, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for the specific element. If empty, uses the currently selected element."
                        },
                        "old_class": {
                            "type": "string",
                            "description": "The class to replace (e.g., 'bg-blue-500', 'text-white')"
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
                "name": "edit_style",
                "description": "Change CSS styles of an element. Use a CSS selector to target the element.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the element"
                        },
                        "styles": {
                            "type": "object",
                            "description": "Object of CSS properties to change (e.g., {\"backgroundColor\": \"blue\", \"color\": \"white\"})"
                        }
                    },
                    "required": ["selector", "styles"]
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
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target the element"
                        },
                        "new_html": {
                            "type": "string",
                            "description": "The new HTML to replace with"
                        }
                    },
                    "required": ["selector", "new_html"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "finalize_edit",
                "description": "Call this when you're done editing. Provide a summary of what you changed.",
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
        }
    ]

    def __init__(self, model: str = None):
        """Initialize the editing agent."""
        self.api_key = settings.openrouter_api_key
        self.model = model or "anthropic/claude-sonnet-4"
        self.current_html = ""
        self.selected_element = None
        self.max_iterations = 10
        self.temperature = 0.3

        print(f"Initialized PosterEditingAgent with model: {self.model}")

    async def edit(
        self,
        html: str,
        instruction: str,
        max_iterations: int = 10,
        design_context: Optional[Dict[str, Any]] = None,
        selected_element: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Edit HTML based on user instruction using tool-based agent.

        Args:
            html: Current HTML content
            instruction: User's edit instruction
            max_iterations: Max tool use iterations
            design_context: Extracted design metadata
            selected_element: Currently selected element info

        Returns:
            Edited HTML and metadata
        """
        try:
            print(f"PosterEditingAgent: Starting edit - {instruction[:50]}...")
            if selected_element:
                print(f"PosterEditingAgent: Target element: {selected_element.get('selector', 'none')}")

            self.current_html = html
            self.selected_element = selected_element

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

            # Run agent with tools
            messages = [{"role": "user", "content": user_prompt}]
            iteration = 0
            final_html = html
            edit_summary = ""

            while iteration < max_iterations:
                iteration += 1
                print(f"PosterEditingAgent: Iteration {iteration}")

                # Call OpenRouter API with tools
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": "https://topmate.io",
                                "X-Title": "Poster Editor"
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
                            print(f"OpenRouter API error: {response.status_code} - {error_text}")
                            return {
                                "success": False,
                                "error": f"API error: {response.status_code}",
                                "html": html
                            }

                        result = response.json()
                except Exception as e:
                    print(f"OpenRouter API error: {e}")
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
                        print(f"PosterEditingAgent: Final response - {content[:100]}")
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

                    print(f"PosterEditingAgent: Using tool '{tool_name}'")

                    # Execute the tool
                    tool_result = await self._execute_tool(tool_name, tool_input)

                    # Check if finalize was called
                    if tool_name == "finalize_edit":
                        edit_summary = tool_input.get("summary", "Edit completed")
                        final_html = self.current_html

                        print(f"PosterEditingAgent: finalize_edit called - summary: {edit_summary}")

                        return {
                            "success": True,
                            "html": final_html,
                            "summary": edit_summary,
                            "iterations": iteration
                        }

                    # Update current HTML if edit was successful
                    if tool_result.get("success") and tool_result.get("html"):
                        self.current_html = tool_result["html"]

                    tool_results.append({
                        "tool_call_id": tool_id,
                        "role": "tool",
                        "content": json.dumps({k: v for k, v in tool_result.items() if k != "html"})
                    })

                # Add assistant response and tool results to messages
                messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
                messages.extend(tool_results)

            # If we exhausted iterations, return current state
            return {
                "success": True,
                "html": self.current_html,
                "summary": edit_summary or "Edit completed",
                "iterations": iteration
            }

        except Exception as e:
            print(f"PosterEditingAgent: Error - {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "html": html
            }

    async def _execute_tool(self, tool_name: str, tool_input: Dict) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        try:
            from bs4 import BeautifulSoup

            # Helper to get selector with auto-injection
            def get_selector():
                selector = tool_input.get("selector", "")
                if not selector and self.selected_element:
                    selector = self.selected_element.get("selector", "")
                    print(f"PosterEditingAgent: AUTO-INJECTING selector: '{selector}'")
                return selector

            if tool_name == "edit_text":
                selector = get_selector()
                new_text = tool_input.get("new_text")

                soup = BeautifulSoup(self.current_html, 'html.parser')
                element = soup.select_one(selector) if selector else None

                if element:
                    element.string = new_text
                    modified_html = str(soup)
                    self.current_html = modified_html
                    print(f"PosterEditingAgent: edit_text SUCCESS")
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": f"Changed text to '{new_text[:50]}...'"
                    }
                else:
                    return {"success": False, "error": f"Element not found: {selector}"}

            elif tool_name == "modify_class":
                selector = tool_input.get("selector", "")
                old_class = tool_input.get("old_class", "")
                new_class = tool_input.get("new_class", "")

                # Auto-inject selector if not provided
                if not selector and self.selected_element:
                    selector = self.selected_element.get("selector", "")

                # Try outer_html replacement first (most precise)
                if self.selected_element:
                    outer_html = self.selected_element.get("outer_html", "")
                    if outer_html and old_class in outer_html:
                        new_outer_html = outer_html.replace(old_class, new_class)
                        if outer_html in self.current_html:
                            modified_html = self.current_html.replace(outer_html, new_outer_html, 1)
                            self.current_html = modified_html
                            print(f"PosterEditingAgent: modify_class SUCCESS (outer_html)")
                            return {
                                "success": True,
                                "html": modified_html,
                                "message": f"Changed class '{old_class}' to '{new_class}'"
                            }

                # Fallback to BeautifulSoup
                if selector:
                    soup = BeautifulSoup(self.current_html, 'html.parser')
                    element = soup.select_one(selector)

                    if element:
                        current_classes = element.get('class', [])
                        if isinstance(current_classes, str):
                            current_classes = current_classes.split()

                        if old_class in current_classes:
                            new_classes = [new_class if c == old_class else c for c in current_classes]
                            element['class'] = new_classes
                            modified_html = str(soup)
                            self.current_html = modified_html
                            print(f"PosterEditingAgent: modify_class SUCCESS (BeautifulSoup)")
                            return {
                                "success": True,
                                "html": modified_html,
                                "message": f"Changed class '{old_class}' to '{new_class}'"
                            }

                # Global replacement as last resort
                if old_class in self.current_html:
                    modified_html = self.current_html.replace(old_class, new_class)
                    self.current_html = modified_html
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": f"Changed ALL '{old_class}' to '{new_class}' globally"
                    }

                return {"success": False, "error": f"Class '{old_class}' not found"}

            elif tool_name == "find_and_replace":
                find_str = tool_input.get("find", "")
                replace_str = tool_input.get("replace", "")

                if find_str and find_str in self.current_html:
                    modified_html = self.current_html.replace(find_str, replace_str)
                    self.current_html = modified_html
                    print(f"PosterEditingAgent: find_and_replace SUCCESS")
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": f"Replaced '{find_str[:50]}...'"
                    }
                else:
                    return {"success": False, "error": f"Text '{find_str[:50]}...' not found"}

            elif tool_name == "edit_style":
                selector = get_selector()
                styles = tool_input.get("styles", {})

                soup = BeautifulSoup(self.current_html, 'html.parser')
                element = soup.select_one(selector) if selector else None

                if element:
                    existing_style = element.get("style", "")
                    style_str = "; ".join(f"{k}: {v}" for k, v in styles.items())
                    element["style"] = f"{existing_style}; {style_str}".strip("; ")
                    modified_html = str(soup)
                    self.current_html = modified_html
                    print(f"PosterEditingAgent: edit_style SUCCESS")
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": "Updated styles"
                    }
                else:
                    return {"success": False, "error": f"Element not found: {selector}"}

            elif tool_name == "replace_element":
                selector = get_selector()
                new_html = tool_input.get("new_html", "")

                soup = BeautifulSoup(self.current_html, 'html.parser')
                element = soup.select_one(selector) if selector else None

                if element:
                    new_element = BeautifulSoup(new_html, 'html.parser')
                    element.replace_with(new_element)
                    modified_html = str(soup)
                    self.current_html = modified_html
                    print(f"PosterEditingAgent: replace_element SUCCESS")
                    return {
                        "success": True,
                        "html": modified_html,
                        "message": "Replaced element"
                    }
                else:
                    return {"success": False, "error": f"Element not found: {selector}"}

            elif tool_name == "finalize_edit":
                return {"success": True, "message": "Finalized"}

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            print(f"Tool execution error ({tool_name}): {str(e)}")
            return {"success": False, "error": str(e)}


# Singleton instance
poster_editing_agent = PosterEditingAgent()


async def edit_poster_with_agent(
    html: str,
    instruction: str,
    design_context: Optional[Dict[str, Any]] = None,
    selected_element: Optional[Dict[str, Any]] = None,
    max_iterations: int = 10
) -> Dict[str, Any]:
    """
    Convenience function to edit poster HTML using the editing agent.

    Args:
        html: Current HTML
        instruction: Edit instruction
        design_context: Extracted design metadata
        selected_element: Currently selected element info
        max_iterations: Maximum iterations

    Returns:
        Edited HTML and metadata
    """
    return await poster_editing_agent.edit(
        html=html,
        instruction=instruction,
        max_iterations=max_iterations,
        design_context=design_context,
        selected_element=selected_element
    )
