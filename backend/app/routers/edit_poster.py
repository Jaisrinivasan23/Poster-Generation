"""
Poster editing API router with AI-based intelligent editing.

This module provides endpoints for editing poster HTML using an AI agent
that understands design context and makes targeted, precise changes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time

from app.agents.editing_agent import edit_poster_with_agent

router = APIRouter()


class SelectedElement(BaseModel):
    """Model for selected element context"""
    selector: str
    tag: Optional[str] = None
    classes: Optional[List[str]] = []
    text: Optional[str] = None
    outer_html: Optional[str] = None
    color_classes: Optional[List[str]] = []


class EditPosterRequest(BaseModel):
    """Request model for editing a poster"""
    html: str
    edit_instruction: str
    design_context: Optional[Dict[str, Any]] = None
    selected_element: Optional[SelectedElement] = None
    max_iterations: Optional[int] = 10


class EditPosterResponse(BaseModel):
    """Response model for editing a poster"""
    success: bool
    html: Optional[str] = None
    summary: Optional[str] = None
    iterations: Optional[int] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


@router.post("/api/edit-poster", response_model=EditPosterResponse)
async def edit_poster(data: EditPosterRequest):
    """
    Edit poster using intelligent Claude Agent with tools.

    The agent can:
    - Edit text content
    - Modify styles and colors
    - Change CSS classes (Tailwind)
    - Replace elements
    - Make targeted, precise changes while preserving design

    Args:
        data: EditPosterRequest with HTML, instruction, and optional context

    Returns:
        EditPosterResponse with edited HTML and summary
    """
    try:
        start_time = time.time()

        print(f"Edit poster request: {data.edit_instruction[:100]}")
        if data.selected_element:
            print(f"Selected element: {data.selected_element.selector}")

        # Convert selected_element to dict if present
        selected_element_dict = None
        if data.selected_element:
            selected_element_dict = data.selected_element.model_dump()

        # Run the editing agent
        result = await edit_poster_with_agent(
            html=data.html,
            instruction=data.edit_instruction,
            design_context=data.design_context,
            selected_element=selected_element_dict,
            max_iterations=data.max_iterations
        )

        execution_time = time.time() - start_time

        if result.get("success"):
            print(f"Edit completed successfully in {execution_time:.2f}s - {result.get('summary')}")

            return EditPosterResponse(
                success=True,
                html=result.get("html"),
                summary=result.get("summary"),
                iterations=result.get("iterations"),
                execution_time=execution_time
            )
        else:
            print(f"Edit failed: {result.get('error')}")
            return EditPosterResponse(
                success=False,
                error=result.get("error"),
                html=result.get("html"),
                execution_time=execution_time
            )

    except Exception as e:
        print(f"Edit poster endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class ChatMessageRequest(BaseModel):
    """Request for chat-based editing"""
    session_id: str
    message: str
    html: str
    selected_element: Optional[SelectedElement] = None
    design_context: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    """Response for chat-based editing"""
    success: bool
    html: Optional[str] = None
    summary: Optional[str] = None
    reply: str = ""
    error: Optional[str] = None


@router.post("/api/poster-chat", response_model=ChatMessageResponse)
async def poster_chat(data: ChatMessageRequest):
    """
    Chat-based poster editing endpoint.

    Allows conversational editing with context tracking.

    Args:
        data: ChatMessageRequest with session, message, and HTML

    Returns:
        ChatMessageResponse with edited HTML and AI reply
    """
    try:
        # Convert selected_element to dict if present
        selected_element_dict = None
        if data.selected_element:
            selected_element_dict = data.selected_element.model_dump()

        # Process the edit
        result = await edit_poster_with_agent(
            html=data.html,
            instruction=data.message,
            design_context=data.design_context,
            selected_element=selected_element_dict,
            max_iterations=10
        )

        if result.get("success"):
            summary = result.get("summary", "Made the requested changes")
            return ChatMessageResponse(
                success=True,
                html=result.get("html"),
                summary=summary,
                reply=f"✓ {summary}"
            )
        else:
            return ChatMessageResponse(
                success=False,
                error=result.get("error"),
                reply=f"Sorry, I couldn't make that change: {result.get('error')}"
            )

    except Exception as e:
        print(f"Poster chat error: {str(e)}")
        return ChatMessageResponse(
            success=False,
            error=str(e),
            reply=f"Error: {str(e)}"
        )
