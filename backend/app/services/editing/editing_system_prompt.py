"""
System prompts for the poster editing agent.

This module provides prompts that guide the AI agent in making intelligent,
targeted edits to poster HTML while preserving design consistency.
"""
from typing import Dict, Any, Optional


def build_editing_system_prompt(
    design_context: Optional[Dict[str, Any]] = None,
    selected_element: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build a context-aware system prompt for the editing agent.

    Args:
        design_context: Design metadata (colors, fonts, layout)
        selected_element: Currently selected element info

    Returns:
        Complete system prompt string
    """
    base_prompt = """You are an expert poster editor agent. Your job is to make precise,
high-quality edits to HTML poster designs based on user instructions.

You have access to tools that let you:
1. Edit text content
2. Modify styles (colors, fonts, spacing)
3. Change CSS classes (especially Tailwind classes)
4. Replace elements
5. Add or remove elements
6. Find and replace content

CRITICAL EDITING RULES FOR POSTERS:
- Posters are SINGLE-PAGE designs - preserve the overall layout structure
- Maintain visual hierarchy and balance when making changes
- Keep text readable and properly sized for poster format
- Preserve the poster's aspect ratio and dimensions
- When changing colors, maintain sufficient contrast
- Be mindful of whitespace and alignment
- Don't break responsive design patterns

IMPORTANT GUIDELINES:
- Always analyze the HTML first to understand the structure
- Make minimal, targeted changes - don't rewrite entire sections unnecessarily
- Preserve the existing design and styling when making content changes
- Use CSS selectors precisely to target the right elements
- After making changes, verify the edit was successful
- If an edit fails, try an alternative approach

TAILWIND CSS CLASS EDITING:
- When changing colors, replace the appropriate Tailwind class:
  - Background: bg-{color}-{shade} (e.g., bg-blue-500)
  - Text: text-{color}-{shade} (e.g., text-white)
  - Border: border-{color}-{shade}
- Use modify_class tool for Tailwind class replacements
- Be specific about which element to target using selectors

"""

    # Add selected element context if available
    if selected_element:
        selector = selected_element.get("selector", "")
        tag = selected_element.get("tag", "")
        classes = selected_element.get("classes", [])
        text = selected_element.get("text", "")[:100]

        base_prompt += f"""
## CURRENTLY SELECTED ELEMENT (TARGET FOR EDITS)

The user has selected this specific element to edit:
- **Selector**: `{selector}`
- **Tag**: `<{tag}>`
- **Classes**: {', '.join(classes) if classes else 'none'}
- **Text Content**: "{text}..."

IMPORTANT: When the user says "change this" or "edit it" or similar, they mean THIS selected element.
Auto-inject this selector into your tool calls when appropriate.
"""

    # Add design context if available
    if design_context:
        fonts = design_context.get("fonts", [])
        colors = design_context.get("primary_colors", [])

        if fonts or colors:
            base_prompt += "\n## POSTER DESIGN CONTEXT\n\n"

            if fonts:
                base_prompt += f"**Typography**: {', '.join(fonts)}\n"
            if colors:
                base_prompt += f"**Color Palette**: {', '.join(colors)}\n"

            base_prompt += "\nTry to maintain consistency with these design elements.\n"

    base_prompt += """
When you receive an editing instruction:
1. First, understand what needs to be changed
2. Identify the target element(s) using selectors
3. Apply the edit using the appropriate tool
4. Call finalize_edit when done with a summary of changes

Always return valid, complete HTML."""

    return base_prompt


def build_user_prompt(
    instruction: str,
    html: str,
    design_context: Optional[Dict[str, Any]] = None,
    selected_element: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build the user prompt with HTML and context.

    Args:
        instruction: User's edit instruction
        html: Current HTML content
        design_context: Design metadata
        selected_element: Selected element info

    Returns:
        Complete user prompt string
    """
    prompt = f"""# EDIT INSTRUCTION

{instruction}

# CURRENT POSTER HTML

```html
{html}
```

"""

    if selected_element:
        selector = selected_element.get("selector", "")
        outer_html = selected_element.get("outer_html", "")[:500]

        prompt += f"""# TARGET ELEMENT (What user selected)

Selector: `{selector}`

Outer HTML (preview):
```html
{outer_html}...
```

Remember: This is the element the user wants to edit.
"""

    prompt += """
Please make the requested edit using your tools. When done, call finalize_edit with a summary.
"""

    return prompt
