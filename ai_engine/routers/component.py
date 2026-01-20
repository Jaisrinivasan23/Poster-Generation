"""
Component identification and editing API router.

This module provides API endpoints for identifying editable components
in generated HTML and applying targeted edits via the visual overlay system.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import hashlib

from config import settings
from logging_config import logger

router = APIRouter()


class IdentifyComponentsRequest(BaseModel):
    """Request model for component identification"""
    html: str
    include_text: bool = True
    include_bounds: bool = True


class ComponentInfo(BaseModel):
    """Information about an identified component"""
    id: str
    type: str  # section, editable, element
    name: str  # Human-readable name
    selector: str  # CSS selector
    tag: str
    classes: List[str] = []
    text: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None
    editable: bool = True
    children: List[str] = []


class IdentifyComponentsResponse(BaseModel):
    """Response model for component identification"""
    success: bool
    components: List[ComponentInfo] = []
    total_count: int = 0
    error: Optional[str] = None


class EditComponentRequest(BaseModel):
    """Request model for component editing"""
    html: str
    component_id: str
    selector: str
    edit_type: str  # text, style, attribute, class, replace
    edit_value: Any


class EditComponentResponse(BaseModel):
    """Response model for component editing"""
    success: bool
    html: Optional[str] = None
    component_id: Optional[str] = None
    error: Optional[str] = None


# Semantic section mapping for component identification
SECTION_TAGS = {"header", "nav", "main", "section", "article", "aside", "footer"}
SECTION_CLASSES = {"hero", "about", "services", "testimonials", "contact", "pricing", "cta", "features"}
EDITABLE_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "a", "button", "img", "li"}

# Section name hints
SECTION_NAME_HINTS = {
    "hero": "Hero Section",
    "about": "About Section",
    "services": "Services Section",
    "testimonials": "Testimonials",
    "contact": "Contact Section",
    "footer": "Footer",
    "header": "Header",
    "nav": "Navigation",
    "pricing": "Pricing Section",
    "cta": "Call to Action",
    "features": "Features Section"
}


@router.post("/component/identify", response_model=IdentifyComponentsResponse)
async def identify_components(data: IdentifyComponentsRequest):
    """
    Identify all editable components in HTML.

    Returns a component tree with selectors and metadata for the visual overlay system.

    Args:
        data: HTML content and options

    Returns:
        List of identified components with selectors and bounds
    """
    try:
        logger.info("Identifying components in HTML")

        # Get DOM structure from Playwright service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.PLAYWRIGHT_SERVICE_URL}/get-dom-detailed",
                json={
                    "html": data.html,
                    "include_bounds": data.include_bounds
                }
            )

            if response.status_code != 200:
                # Fallback to basic DOM parsing
                logger.warning("Playwright service unavailable, using basic parsing")
                return IdentifyComponentsResponse(
                    success=False,
                    error="Playwright service unavailable",
                    components=[],
                    total_count=0
                )

            dom_data = response.json()

        # Process DOM into component tree
        components = _process_dom_to_components(dom_data.get("dom", {}))

        logger.info(f"Identified {len(components)} components")

        return IdentifyComponentsResponse(
            success=True,
            components=components,
            total_count=len(components)
        )

    except Exception as e:
        logger.error(f"Component identification error: {str(e)}")
        return IdentifyComponentsResponse(
            success=False,
            error=str(e),
            components=[],
            total_count=0
        )


def _process_dom_to_components(dom: Dict, parent_id: str = "", depth: int = 0) -> List[ComponentInfo]:
    """
    Process DOM structure into component list.

    Identifies semantic sections and editable elements.

    Args:
        dom: DOM node from Playwright
        parent_id: Parent component ID for building hierarchy
        depth: Current depth in tree

    Returns:
        List of ComponentInfo objects
    """
    components = []

    if not dom or depth > 10:  # Limit recursion depth
        return components

    tag = dom.get("tag", "").lower()
    classes = dom.get("classes", [])
    element_id = dom.get("id", "")
    text = dom.get("text", "")
    bounds = dom.get("bounds")

    # Skip non-visual elements
    if tag in ("script", "style", "noscript", "meta", "link"):
        return components

    # Generate unique component ID
    comp_id = _generate_component_id(tag, element_id, classes, parent_id)

    # Determine component type and name
    comp_type, comp_name = _classify_component(tag, classes, element_id, text)

    # Only include significant components
    is_significant = (
        comp_type == "section" or
        (comp_type == "editable" and bounds and bounds.get("height", 0) > 15) or
        tag in SECTION_TAGS
    )

    if is_significant:
        # Build CSS selector
        selector = _build_css_selector(tag, element_id, classes)

        component = ComponentInfo(
            id=comp_id,
            type=comp_type,
            name=comp_name,
            selector=selector,
            tag=tag,
            classes=classes,
            text=text[:100] if text else None,
            bounds=bounds,
            editable=comp_type in ("section", "editable"),
            children=[]
        )

        components.append(component)

    # Process children recursively
    for child in dom.get("children", []):
        child_components = _process_dom_to_components(
            child,
            comp_id if is_significant else parent_id,
            depth + 1
        )

        # Link children to parent
        if is_significant and components:
            components[-1].children.extend([c.id for c in child_components if c.type in ("section", "editable")])

        components.extend(child_components)

    return components


def _generate_component_id(tag: str, el_id: str, classes: List, parent_id: str) -> str:
    """Generate unique component identifier"""
    parts = [parent_id, tag, el_id, "-".join(classes[:3])]
    hash_input = "|".join(str(p) for p in parts)
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]


def _classify_component(tag: str, classes: List, el_id: str, text: str) -> tuple:
    """
    Classify component type and determine human-readable name.

    Returns:
        Tuple of (type, name)
    """
    classes_lower = [c.lower() for c in classes]
    el_id_lower = el_id.lower() if el_id else ""

    # Check for semantic sections
    if tag in SECTION_TAGS:
        name = _determine_section_name(tag, classes, el_id)
        return ("section", name)

    # Check for section classes
    for cls in classes_lower:
        if cls in SECTION_CLASSES:
            name = SECTION_NAME_HINTS.get(cls, f"{cls.title()} Section")
            return ("section", name)

    # Check section indicators in ID
    for hint, name in SECTION_NAME_HINTS.items():
        if hint in el_id_lower:
            return ("section", name)

    # Editable text elements
    if tag in EDITABLE_TAGS:
        if tag.startswith("h"):
            name = f"Heading - {text[:30]}..." if text else f"Heading ({tag})"
        elif tag == "p":
            name = f"Text - {text[:30]}..." if text else "Paragraph"
        elif tag == "a":
            name = f"Link - {text[:20]}..." if text else "Link"
        elif tag == "button":
            name = f"Button - {text[:20]}..." if text else "Button"
        elif tag == "img":
            name = "Image"
        else:
            name = f"{tag.title()} - {text[:20]}..." if text else tag.title()

        return ("editable", name)

    # Default
    return ("element", tag)


def _determine_section_name(tag: str, classes: List, el_id: str) -> str:
    """Determine human-readable section name"""
    classes_lower = [c.lower() for c in classes]
    el_id_lower = el_id.lower() if el_id else ""

    # Check hints in classes and ID
    for hint, name in SECTION_NAME_HINTS.items():
        if hint in el_id_lower or any(hint in c for c in classes_lower):
            return name

    # Fallback to tag-based name
    return f"{tag.title()} Section"


def _build_css_selector(tag: str, el_id: str, classes: List) -> str:
    """Build precise CSS selector for element"""
    if el_id:
        return f"#{el_id}"
    elif classes:
        # Use first 2 classes for specificity
        class_selector = '.'.join(classes[:2])
        return f"{tag}.{class_selector}"
    else:
        return tag


@router.post("/component/edit", response_model=EditComponentResponse)
async def edit_component(data: EditComponentRequest):
    """
    Edit a specific component by selector.

    Supports text, style, attribute, and class edits.

    Args:
        data: HTML, component info, edit type and value

    Returns:
        Modified HTML
    """
    try:
        logger.info(f"Editing component {data.component_id} with {data.edit_type}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.PLAYWRIGHT_SERVICE_URL}/edit-component",
                json={
                    "html": data.html,
                    "selector": data.selector,
                    "edit_type": data.edit_type,
                    "edit_value": data.edit_value
                }
            )

            if response.status_code != 200:
                error_detail = response.json().get("error", "Unknown error")
                logger.error(f"Playwright edit failed: {error_detail}")
                return EditComponentResponse(
                    success=False,
                    error=f"Edit failed: {error_detail}"
                )

            result = response.json()

        logger.info(f"Component {data.component_id} edited successfully")

        return EditComponentResponse(
            success=True,
            html=result.get("html"),
            component_id=data.component_id
        )

    except httpx.TimeoutException:
        logger.error("Playwright service timeout")
        return EditComponentResponse(
            success=False,
            error="Edit service timeout"
        )
    except Exception as e:
        logger.error(f"Component edit error: {str(e)}")
        return EditComponentResponse(
            success=False,
            error=str(e)
        )


@router.post("/component/get-element-html")
async def get_element_html(data: dict):
    """
    Get the HTML of a specific element by selector.

    Args:
        data: HTML content and selector

    Returns:
        Element's outer HTML
    """
    try:
        html = data.get("html")
        selector = data.get("selector")

        if not html or not selector:
            raise HTTPException(status_code=400, detail="html and selector required")

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.PLAYWRIGHT_SERVICE_URL}/get-element",
                json={"html": html, "selector": selector}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Element not found")

            result = response.json()

        return {
            "success": True,
            "element_html": result.get("element_html"),
            "text_content": result.get("text_content")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get element error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/component/batch-edit")
async def batch_edit_components(data: dict):
    """
    Apply multiple edits to components in a single request.

    Args:
        data: HTML and list of edits

    Returns:
        Modified HTML after all edits
    """
    try:
        html = data.get("html")
        edits = data.get("edits", [])

        if not html or not edits:
            raise HTTPException(status_code=400, detail="html and edits required")

        current_html = html

        for edit in edits:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{settings.PLAYWRIGHT_SERVICE_URL}/edit-component",
                    json={
                        "html": current_html,
                        "selector": edit.get("selector"),
                        "edit_type": edit.get("edit_type"),
                        "edit_value": edit.get("edit_value")
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    current_html = result.get("html", current_html)
                else:
                    logger.warning(f"Batch edit failed for selector: {edit.get('selector')}")

        return {
            "success": True,
            "html": current_html,
            "edits_applied": len(edits)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch edit error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
