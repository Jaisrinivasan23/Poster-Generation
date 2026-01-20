"""
Chat API router for chatbot interactions.

This module provides API endpoints for the AI chatbot that guides users
through website building with streaming responses via Server-Sent Events (SSE).
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json

from agents.chatbot_orchestrator import orchestrator, ChatMode
from mcp_tools.galactus_tools import fetch_galactus_profile, get_chatbot_suggestions, prepare_website_generation_data
from logging_config import logger

router = APIRouter()


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message"""
    session_id: str
    message: str
    mode: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class InitSessionRequest(BaseModel):
    """Request model for initializing a chat session"""
    session_id: str
    username: str


class SetModeRequest(BaseModel):
    """Request model for changing chat mode"""
    session_id: str
    mode: str  # template_selection, section_builder, freeform_chat


class UpdateHtmlRequest(BaseModel):
    """Request model for updating session HTML"""
    session_id: str
    html: str


class InitSessionResponse(BaseModel):
    """Response model for session initialization"""
    success: bool
    session_id: str
    mode: str
    profile_loaded: bool
    profile_summary: Optional[Dict[str, Any]] = None
    initial_suggestions: List[Dict[str, Any]] = []  # Allow any value types
    welcome_message: str = ""


class SessionStateResponse(BaseModel):
    """Response model for session state"""
    session_id: str
    mode: str
    username: Optional[str] = None
    has_html: bool
    html_size: int = 0
    completed_sections: List[str] = []
    selected_template: Optional[str] = None
    history_length: int = 0


@router.post("/chat/init", response_model=InitSessionResponse)
async def init_chat_session(data: InitSessionRequest):
    """
    Initialize a chat session with user profile.

    Fetches user profile from Galactus API and sets up conversation context.

    Args:
        data: Session ID and username

    Returns:
        Session initialization status with profile summary
    """
    try:
        logger.info(f"Initializing chat session: {data.session_id} for user: {data.username}")

        # Get or create session
        state = orchestrator.get_or_create_session(data.session_id)
        state.username = data.username

        # Fetch user profile from Galactus
        profile_result = await fetch_galactus_profile(data.username)

        profile_loaded = False
        profile_summary = None

        if profile_result.get("success"):
            profile_data = profile_result.get("data", {})

            # Use set_user_profile to also generate intelligent suggestions
            orchestrator.set_user_profile(data.session_id, data.username, profile_result)
            profile_loaded = True

            # Create profile summary with rich data
            services = profile_data.get("services", [])
            testimonials = profile_data.get("testimonials", [])
            stats = profile_data.get("stats", {})

            profile_summary = {
                "name": profile_data.get("name"),
                "tagline": profile_data.get("tagline"),
                "bio": profile_data.get("bio", "")[:200],
                "profile_pic": profile_data.get("profile_pic"),
                "services_count": len(services),
                "services": [
                    {
                        "id": s.get("id"),
                        "title": s.get("title"),
                        "price": s.get("price"),
                        "type": s.get("type")
                    }
                    for s in services[:5]
                ],
                "testimonials_count": len(testimonials),
                "rating": stats.get("rating", 0),
                "bookings": stats.get("bookings", 0),
                "reviews": stats.get("reviews", 0),
                "social_links": profile_data.get("social_links", {}),
                "is_mock": profile_result.get("is_mock", False)
            }

            logger.info(f"Profile loaded for {data.username}: {len(services)} services, {len(testimonials)} testimonials")

        # Get initial suggestions for the mode (now uses profile-based suggestions)
        initial_suggestions = orchestrator.get_initial_suggestions(data.session_id, state.mode)

        # Generate welcome message
        name = profile_summary.get("name", data.username) if profile_summary else data.username
        services_count = profile_summary.get("services_count", 0) if profile_summary else 0

        welcome_message = (
            f"Hello! I'm your AI website assistant. "
            f"I've loaded {name}'s profile with {services_count} services. "
            f"How would you like to build your website? "
            f"You can choose a template, build section by section, or just tell me what you want!"
        )

        return InitSessionResponse(
            success=True,
            session_id=data.session_id,
            mode=state.mode.value,
            profile_loaded=profile_loaded,
            profile_summary=profile_summary,
            initial_suggestions=initial_suggestions,
            welcome_message=welcome_message
        )

    except Exception as e:
        logger.error(f"Error initializing chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/send")
async def send_chat_message(request: Request, data: ChatMessageRequest):
    """
    Send a message to the chatbot and stream response.

    Uses Server-Sent Events (SSE) for streaming responses.
    Response chunks include text, suggestions, and actions.

    Args:
        data: Session ID, message, optional mode and context

    Returns:
        StreamingResponse with SSE events
    """
    async def event_stream():
        try:
            logger.info(f"Processing chat message for session: {data.session_id}")

            # Set mode if provided
            if data.mode:
                mode_map = {
                    "template_selection": ChatMode.TEMPLATE_SELECTION,
                    "section_builder": ChatMode.SECTION_BUILDER,
                    "freeform_chat": ChatMode.FREEFORM_CHAT
                }
                if data.mode in mode_map:
                    orchestrator.set_mode(data.session_id, mode_map[data.mode])

            # Process message and stream response
            async for chunk in orchestrator.process_message(
                session_id=data.session_id,
                message=data.message,
                context=data.context
            ):
                # Format as SSE
                yield f"data: {json.dumps(chunk)}\n\n"

        except Exception as e:
            logger.error(f"Chat stream error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/chat/mode")
async def set_chat_mode(data: SetModeRequest):
    """
    Change the chat mode for a session.

    Args:
        data: Session ID and new mode

    Returns:
        Success status and updated mode
    """
    try:
        mode_map = {
            "template_selection": ChatMode.TEMPLATE_SELECTION,
            "section_builder": ChatMode.SECTION_BUILDER,
            "freeform_chat": ChatMode.FREEFORM_CHAT
        }

        if data.mode not in mode_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {data.mode}. Valid modes: {list(mode_map.keys())}"
            )

        success = orchestrator.set_mode(data.session_id, mode_map[data.mode])

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get suggestions for new mode (uses profile-based suggestions)
        suggestions = orchestrator.get_initial_suggestions(data.session_id, mode_map[data.mode])

        return {
            "success": True,
            "mode": data.mode,
            "suggestions": suggestions
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting chat mode: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/session/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str):
    """
    Get current session state.

    Args:
        session_id: Session identifier

    Returns:
        Current session state including mode, progress, and history
    """
    state = orchestrator.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStateResponse(
        session_id=session_id,
        mode=state.mode.value,
        username=state.username,
        has_html=bool(state.current_html),
        html_size=len(state.current_html) if state.current_html else 0,
        completed_sections=state.completed_sections,
        selected_template=state.selected_template,
        history_length=len(state.conversation_history)
    )


@router.post("/chat/apply-html")
async def apply_html_to_session(data: UpdateHtmlRequest):
    """
    Update session with generated/edited HTML.

    This keeps the chatbot in sync with the current website state.

    Args:
        data: Session ID and HTML content

    Returns:
        Success status
    """
    if not data.session_id or not data.html:
        raise HTTPException(status_code=400, detail="session_id and html required")

    success = orchestrator.update_session_html(data.session_id, data.html)

    if not success:
        # Create session if doesn't exist
        state = orchestrator.get_or_create_session(data.session_id)
        state.current_html = data.html
        success = True

    return {
        "success": success,
        "html_size": len(data.html)
    }


@router.post("/chat/action")
async def handle_chat_action(data: dict):
    """
    Handle an action extracted from chat response.

    Actions include:
    - SELECT_TEMPLATE: Set the selected template
    - SECTION_COMPLETE: Mark a section as complete
    - EDIT_WEBSITE: Apply an edit instruction

    Args:
        data: Action type and parameters

    Returns:
        Action result
    """
    try:
        session_id = data.get("session_id")
        action_type = data.get("action_type")
        action_data = data.get("action_data")

        if not session_id or not action_type:
            raise HTTPException(status_code=400, detail="session_id and action_type required")

        result = {"success": True, "action": action_type}

        if action_type == "SELECT_TEMPLATE":
            orchestrator.set_selected_template(session_id, action_data)
            result["template"] = action_data

        elif action_type == "SECTION_COMPLETE":
            orchestrator.mark_section_complete(session_id, action_data)
            result["section"] = action_data

        elif action_type == "GENERATE_SECTION":
            # This would trigger section generation
            result["section"] = action_data
            result["requires_generation"] = True

        elif action_type == "EDIT_WEBSITE":
            # This would trigger website editing
            result["edit_instruction"] = action_data
            result["requires_edit"] = True

        elif action_type == "ADD_SECTION":
            result["section_type"] = action_data
            result["requires_generation"] = True

        elif action_type == "REMOVE_ELEMENT":
            result["element"] = action_data
            result["requires_edit"] = True

        else:
            result["warning"] = f"Unknown action type: {action_type}"

        logger.info(f"Handled action {action_type} for session {session_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling chat action: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a chat session.

    Args:
        session_id: Session identifier

    Returns:
        Success status
    """
    if session_id in orchestrator.sessions:
        del orchestrator.sessions[session_id]
        logger.info(f"Deleted session: {session_id}")
        return {"success": True, "session_id": session_id}

    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/chat/suggestions/{session_id}")
async def get_profile_suggestions(session_id: str):
    """
    Get intelligent suggestions based on user profile.

    Returns template recommendations, section suggestions, content improvements,
    and quick actions tailored to the user's profile data.

    Args:
        session_id: Session identifier

    Returns:
        Profile-based suggestions for all modes
    """
    state = orchestrator.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    suggestions = orchestrator.get_profile_suggestions(session_id)

    return {
        "success": True,
        "session_id": session_id,
        "username": state.username,
        "suggestions": suggestions
    }


@router.get("/chat/generation-data/{session_id}")
async def get_generation_data(session_id: str):
    """
    Get prepared data for website generation.

    Returns the complete profile data formatted for LLM consumption,
    including all instructions for using images, CTAs, testimonials, etc.

    Args:
        session_id: Session identifier

    Returns:
        Formatted generation data string
    """
    state = orchestrator.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    if not state.user_profile:
        raise HTTPException(status_code=400, detail="No profile loaded for session")

    # Prepare the generation data
    generation_data = prepare_website_generation_data(
        state.username,
        state.user_profile
    )

    return {
        "success": True,
        "session_id": session_id,
        "username": state.username,
        "generation_data": generation_data,
        "data_length": len(generation_data)
    }


@router.post("/chat/generate-website")
async def trigger_website_generation(data: dict):
    """
    Trigger website generation with profile data.

    Uses the prepared generation data to create a complete website
    through the AI engine.

    Args:
        data: session_id, optional template preference, and custom instructions

    Returns:
        Generation request result (actual generation is handled by build_website router)
    """
    try:
        session_id = data.get("session_id")
        template = data.get("template")
        custom_instructions = data.get("instructions", "")

        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required")

        state = orchestrator.get_session(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        if not state.user_profile:
            raise HTTPException(status_code=400, detail="No profile loaded for session")

        # Prepare the generation prompt
        generation_data = prepare_website_generation_data(
            state.username,
            state.user_profile
        )

        # Build the full prompt
        prompt_parts = [generation_data]

        if template:
            prompt_parts.append(f"\nSELECTED TEMPLATE STYLE: {template}")
            orchestrator.set_selected_template(session_id, template)

        if custom_instructions:
            prompt_parts.append(f"\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}")

        full_prompt = "\n".join(prompt_parts)

        logger.info(f"Website generation triggered for session {session_id}, prompt length: {len(full_prompt)}")

        return {
            "success": True,
            "session_id": session_id,
            "username": state.username,
            "template": template,
            "prompt": full_prompt,
            "prompt_length": len(full_prompt),
            "ready_for_generation": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering website generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
