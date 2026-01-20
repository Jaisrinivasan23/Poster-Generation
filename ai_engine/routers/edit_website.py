"""
Website editing API router with Agent-based intelligent editing.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import httpx
import json
import re

from logging_config import logger
from config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address
from agents.editing_agent import editing_agent, edit_with_agent

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# SMART INSTRUCTION PREPROCESSING
# ============================================================================

def preprocess_edit_instruction(
    instruction: str,
    selected_element: Optional[Dict[str, Any]] = None
) -> tuple[str, Optional[str]]:
    """
    Preprocess edit instruction for smarter handling.

    CONSERVATIVE APPROACH: Only use fast path when intent is UNAMBIGUOUS.

    Fast path triggers:
    1. Image selected + instruction is ONLY a URL (nothing else)
    2. Explicit patterns like "replace with [url]" for images

    Args:
        instruction: The user's edit instruction
        selected_element: Currently selected element info

    Returns:
        Tuple of (processed_instruction, fast_path_type)
        fast_path_type can be: "image_replace" or None
    """
    if not instruction:
        return instruction, None

    instruction_stripped = instruction.strip()
    tag = selected_element.get("tag", "").lower() if selected_element else ""

    # -------------------------------------------------------------------------
    # SMART IMAGE URL DETECTION (CONSERVATIVE)
    # -------------------------------------------------------------------------
    # Only trigger fast path when:
    # 1. Image is selected AND
    # 2. Instruction is JUST a URL (no other text) OR
    # 3. Instruction explicitly says "replace" with a URL

    if tag == "img":
        # Pattern 1: Instruction is ONLY a URL
        url_only_pattern = r'^(https?://[^\s]+)$'
        match = re.match(url_only_pattern, instruction_stripped)
        if match:
            new_url = match.group(1)
            processed = f"Replace the image src attribute with: {new_url}"
            logger.info(f"Smart preprocessing: Image selected + URL only -> fast path")
            return processed, "image_replace"

        # Pattern 2: Explicit replacement intent with URL
        explicit_patterns = [
            r'^(?:replace|change|update|set)(?:\s+(?:it|this|image|src))?\s*(?:to|with|:)\s*(https?://[^\s]+)$',
            r'^(?:use|new\s+(?:url|image)|url|src)\s*[:=]?\s*(https?://[^\s]+)$',
        ]

        for pattern in explicit_patterns:
            match = re.match(pattern, instruction_stripped, re.IGNORECASE)
            if match:
                new_url = match.group(1)
                processed = f"Replace the image src attribute with: {new_url}"
                logger.info(f"Smart preprocessing: Explicit image replacement detected")
                return processed, "image_replace"

    # -------------------------------------------------------------------------
    # NO TEXT FAST PATH - Let AI handle text to avoid misinterpretation
    # -------------------------------------------------------------------------
    # Text edits are ambiguous - "Hello World" could mean:
    # - Replace text with "Hello World"
    # - Search for "Hello World"
    # - Add "Hello World" somewhere
    # Let the AI agent interpret based on full context

    return instruction, None


# ============================================================================
# FAST PATH EDITING (bypasses full agent loop for simple edits)
# ============================================================================

async def fast_path_image_replace(
    html: str,
    new_url: str,
    selected_element: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fast path for image replacement - directly replaces src attribute.

    This bypasses the full AI agent loop for simple image URL changes.
    ~10x faster than agent-based editing.
    """
    try:
        selector = selected_element.get("selector", "")
        outer_html = selected_element.get("outer_html", "")

        if not selector:
            return {"success": False, "error": "No selector provided"}

        # Method 1: Use outer_html for precise replacement
        if outer_html and 'src="' in outer_html:
            # Extract current src
            src_match = re.search(r'src="([^"]*)"', outer_html)
            if src_match:
                old_src = src_match.group(1)
                new_outer_html = outer_html.replace(f'src="{old_src}"', f'src="{new_url}"')

                if outer_html in html:
                    modified_html = html.replace(outer_html, new_outer_html, 1)
                    logger.info(f"Fast path image replace: SUCCESS via outer_html")
                    return {
                        "success": True,
                        "html": modified_html,
                        "summary": f"Replaced image URL"
                    }

        # Method 2: Use Playwright service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.PLAYWRIGHT_SERVICE_URL}/edit-component",
                json={
                    "html": html,
                    "selector": selector,
                    "edit_type": "attribute",
                    "edit_value": {"name": "src", "value": new_url}
                }
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"Fast path image replace: SUCCESS via Playwright")
                    return {
                        "success": True,
                        "html": result.get("html"),
                        "summary": f"Replaced image URL"
                    }

        return {"success": False, "error": "Fast path failed"}

    except Exception as e:
        logger.error(f"Fast path image replace error: {e}")
        return {"success": False, "error": str(e)}


class SelectedElement(BaseModel):
    """Model for selected element context"""
    selector: str
    tag: Optional[str] = None
    classes: Optional[List[str]] = []
    text: Optional[str] = None
    parent_selector: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = {}
    outer_html: Optional[str] = None  # For precise element targeting
    color_classes: Optional[List[str]] = []  # Tailwind color classes


class EditWebsiteRequest(BaseModel):
    """Request model for editing a website"""
    html: str
    edit_instruction: str
    project_id: Optional[int] = None
    design_context: Optional[Dict[str, Any]] = None
    selected_element: Optional[SelectedElement] = None


class EditWebsiteResponse(BaseModel):
    """Response model for editing a website"""
    success: bool
    html: Optional[str] = None
    error: Optional[str] = None
    edit_type: Optional[str] = None  # 'simple' or 'complex'
    model: Optional[str] = None
    execution_time: Optional[float] = None
    replay_url: Optional[str] = None  # Browserbase session replay URL for debugging


@router.post("/edit/optimized", response_model=EditWebsiteResponse)
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
async def edit_website_optimized(request: Request, data: EditWebsiteRequest):
    """
    Edit website using optimized routing with smart instruction preprocessing.

    This endpoint intelligently routes edits:
    1. Smart preprocessing detects intent (image URL, text replacement, etc.)
    2. Fast path for simple image/text replacements (instant, <500ms)
    3. AI agent for complex edits (5-10s)

    Rate limit: 10 requests per minute
    """
    try:
        start_time = time.time()

        # Convert selected_element to dict if present
        selected_element_dict = None
        if data.selected_element:
            selected_element_dict = data.selected_element.model_dump()

        logger.info(
            "Edit request received",
            instruction=data.edit_instruction[:100],
            html_size=len(data.html),
            has_selected_element=selected_element_dict is not None,
            selected_tag=selected_element_dict.get("tag") if selected_element_dict else None
        )

        # =====================================================================
        # STEP 1: SMART PREPROCESSING
        # =====================================================================
        processed_instruction, fast_path_type = preprocess_edit_instruction(
            data.edit_instruction,
            selected_element_dict
        )

        if processed_instruction != data.edit_instruction:
            logger.info(f"Instruction preprocessed: '{data.edit_instruction[:50]}...' -> '{processed_instruction[:50]}...'")

        # =====================================================================
        # STEP 2: FAST PATH FOR IMAGE URL REPLACEMENT
        # =====================================================================
        # Only for unambiguous cases: image selected + URL provided
        if fast_path_type == "image_replace" and selected_element_dict:
            url_match = re.search(r'(https?://[^\s<>"\']+)', processed_instruction)
            if url_match:
                new_url = url_match.group(1)
                result = await fast_path_image_replace(
                    html=data.html,
                    new_url=new_url,
                    selected_element=selected_element_dict
                )

                if result.get("success"):
                    execution_time = time.time() - start_time
                    logger.info(f"Fast path image replace completed in {execution_time:.2f}s")
                    return EditWebsiteResponse(
                        success=True,
                        html=result.get("html"),
                        edit_type="fast_path_image",
                        model="direct",
                        execution_time=execution_time
                    )
                else:
                    logger.warning(f"Fast path failed, falling back to AI: {result.get('error')}")

        # =====================================================================
        # STEP 3: CLASSIFY AND ROUTE
        # =====================================================================
        edit_type = _classify_edit(processed_instruction)

        if edit_type == "simple":
            # Try Playwright first for simple edits
            try:
                result = await _edit_with_playwright(data.html, processed_instruction)

                if result.get("success"):
                    execution_time = time.time() - start_time

                    logger.info(
                        "Edit completed with Playwright",
                        edit_type="simple",
                        execution_time=execution_time
                    )

                    return EditWebsiteResponse(
                        success=True,
                        html=result.get("html"),
                        edit_type="simple",
                        model="playwright",
                        execution_time=execution_time
                    )
            except Exception as e:
                logger.warning(f"Playwright edit failed, falling back to AI: {str(e)}")
                edit_type = "complex"  # Fallback to AI

        # =====================================================================
        # STEP 4: AI AGENT FOR COMPLEX EDITS
        # =====================================================================
        if edit_type == "complex":
            result = await _edit_with_ai(
                html=data.html,
                instruction=processed_instruction,  # Use preprocessed instruction
                design_context=data.design_context,
                selected_element=selected_element_dict
            )

            if not result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Edit failed")
                )

            execution_time = time.time() - start_time

            logger.info(
                "Edit completed with AI",
                edit_type="complex",
                execution_time=execution_time,
                replay_url=result.get("replay_url")
            )

            return EditWebsiteResponse(
                success=True,
                html=result.get("html"),
                edit_type="complex",
                model=result.get("model"),
                execution_time=execution_time,
                replay_url=result.get("replay_url")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing website: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _classify_edit(instruction: str) -> str:
    """
    Classify edit as 'simple' or 'complex'.

    Simple: Only very basic text changes
    Complex: Everything else (colors, styles, layout, etc.) - handled by AI agent

    Note: We now route most edits to the AI agent because it handles
    Tailwind CSS classes better than the simple Playwright editor.
    """
    instruction_lower = instruction.lower()

    # Only very basic edits go to Playwright
    simple_keywords = [
        "fix typo", "fix spelling", "correct spelling"
    ]

    # Everything else goes to AI agent
    if any(keyword in instruction_lower for keyword in simple_keywords):
        return "simple"

    # Default to complex - AI agent handles Tailwind better
    return "complex"


async def _edit_with_playwright(html: str, instruction: str) -> dict:
    """Edit HTML using Playwright service (fast for simple edits)"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.PLAYWRIGHT_SERVICE_URL}/edit-simple",
                json={
                    "html": html,
                    "instruction": instruction
                }
            )
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "html": data.get("html", html)
            }

    except Exception as e:
        logger.error(f"Playwright edit error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def _edit_with_ai(
    html: str,
    instruction: str,
    design_context: Optional[Dict[str, Any]] = None,
    selected_element: Optional[Dict[str, Any]] = None,
    max_iterations: int = 15
) -> dict:
    """Edit HTML using Claude AI Agent (for complex edits with tool use)"""
    try:
        # Use the editing agent with tools for intelligent editing
        result = await edit_with_agent(
            html=html,
            instruction=instruction,
            design_context=design_context,
            selected_element=selected_element,
            max_iterations=max_iterations
        )

        if result.get("success"):
            return {
                "success": True,
                "html": result.get("html"),
                "model": f"agent-{settings.CLAUDE_MODEL_SONNET}",
                "summary": result.get("summary"),
                "iterations": result.get("iterations")
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Agent edit failed")
            }

    except Exception as e:
        logger.error(f"AI Agent edit error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


class AgentEditRequest(BaseModel):
    """Request model for agent-based editing"""
    html: str
    instruction: str
    max_iterations: Optional[int] = 15  # Increased for complex edits
    design_context: Optional[Dict[str, Any]] = None
    selected_element: Optional[SelectedElement] = None


class AgentEditResponse(BaseModel):
    """Response model for agent-based editing"""
    success: bool
    html: Optional[str] = None
    summary: Optional[str] = None
    iterations: Optional[int] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


@router.post("/edit/agent", response_model=AgentEditResponse)
@limiter.limit("5/minute")
async def edit_with_agent_endpoint(request: Request, data: AgentEditRequest):
    """
    Edit website using intelligent Claude Agent with tools.

    The agent can:
    - Analyze DOM structure
    - Make targeted text/style/attribute changes
    - Add/remove elements
    - Iterate and refine edits autonomously

    Rate limit: 5 requests per minute (more intensive than simple edits)
    """
    try:
        start_time = time.time()

        logger.info(
            "Agent edit request received",
            instruction=data.instruction[:100],
            html_size=len(data.html),
            max_iterations=data.max_iterations
        )

        # Convert selected_element to dict if present
        selected_element_dict = None
        if data.selected_element:
            selected_element_dict = data.selected_element.model_dump()

        # Run the editing agent with design context
        result = await editing_agent.edit(
            html=data.html,
            instruction=data.instruction,
            max_iterations=data.max_iterations,
            design_context=data.design_context,
            selected_element=selected_element_dict
        )

        execution_time = time.time() - start_time

        if result.get("success"):
            logger.info(
                "Agent edit completed successfully",
                iterations=result.get("iterations"),
                summary=result.get("summary"),
                execution_time=execution_time
            )

            return AgentEditResponse(
                success=True,
                html=result.get("html"),
                summary=result.get("summary"),
                iterations=result.get("iterations"),
                execution_time=execution_time
            )
        else:
            logger.error(f"Agent edit failed: {result.get('error')}")
            return AgentEditResponse(
                success=False,
                error=result.get("error"),
                html=result.get("html"),  # Return original on error
                execution_time=execution_time
            )

    except Exception as e:
        logger.error(f"Agent edit endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edit/component")
@limiter.limit("20/minute")
async def edit_component(request: Request, data: dict):
    """
    Edit a specific component using Playwright (fast, targeted edits).

    This endpoint is for direct component manipulation:
    - Text replacement
    - Style changes
    - Attribute updates
    - Element replacement

    Rate limit: 20 requests per minute
    """
    try:
        html = data.get("html")
        selector = data.get("selector")
        edit_type = data.get("edit_type")  # text, style, attribute, replace, hide
        edit_value = data.get("edit_value")

        if not all([html, selector, edit_type]):
            raise HTTPException(
                status_code=400,
                detail="html, selector, and edit_type are required"
            )

        logger.info(f"Component edit: {edit_type} on {selector}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.PLAYWRIGHT_SERVICE_URL}/edit-component",
                json={
                    "html": html,
                    "selector": selector,
                    "edit_type": edit_type,
                    "edit_value": edit_value
                }
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": result.get("success", False),
                    "html": result.get("html"),
                    "error": result.get("error")
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Playwright service error: {response.text}"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component edit error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
