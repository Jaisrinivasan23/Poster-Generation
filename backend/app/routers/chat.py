"""
Chat-based email template editing router - FastAPI version with streaming
Migrated from: frontend/app/api/chat/route.ts
"""
import json
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from anthropic import Anthropic

router = APIRouter()

# ============================================================================
# CHAT SYSTEM PROMPT - EXACT COPY FROM TYPESCRIPT
# ============================================================================

CHAT_SYSTEM_PROMPT = """You are an expert email template editor helping to iterate on an existing HTML email template.

## Your Role
You help users modify their email templates based on their instructions. You understand HTML email constraints and SuprSend requirements.

## Rules
1. When asked to make changes, output the COMPLETE updated HTML (not just the changed parts)
2. Preserve all existing SuprSend variables: {{variable}} for text, {{{url}}} for URLs, {{$hosted_preference_url}} for unsubscribe
3. Preserve ALL block markers: <!-- BLOCK:type -->...<!-- /BLOCK:type -->
4. Maintain email client compatibility (tables for layout, inline styles, no flexbox/grid)
5. Keep the same overall structure unless specifically asked to change it
6. Use table-based layouts, max 600px width
7. Maintain MSO conditionals for Outlook

## Response Format
ALWAYS respond in this exact format:

<html>
[COMPLETE HTML EMAIL HERE - from <!DOCTYPE html> to </html>]
</html>

<explanation>
[Brief description of what you changed - 1-3 sentences max]
</explanation>

## Important
- Output the FULL HTML every time, not just snippets
- Do NOT use markdown code fences inside the <html> tags
- Keep all block comment markers intact
- If you can't make a change, explain why in the explanation section"""


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatContext(BaseModel):
    brandName: str
    emailType: str
    tone: str
    primaryColor: str
    secondaryColor: str
    accentColor: Optional[str] = None
    industry: Optional[str] = None


class ChatRequest(BaseModel):
    apiKey: str
    currentHtml: str
    messages: List[ChatMessage]
    newMessage: str
    context: ChatContext


# ============================================================================
# API ENDPOINT
# ============================================================================

@router.post("/chat")
async def chat_with_template(request: ChatRequest):
    """
    Chat endpoint for iterating on email templates with streaming response.
    Migrated from: frontend/app/api/chat/route.ts
    """
    try:
        if not request.apiKey:
            raise HTTPException(status_code=400, detail="API key is required")
        
        if not request.currentHtml or not request.newMessage:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        client = Anthropic(api_key=request.apiKey)
        
        # Build system prompt with context
        system_prompt = f"""{CHAT_SYSTEM_PROMPT}

## Current Template Context
- Brand: {request.context.brandName}
- Email Type: {request.context.emailType}
- Tone: {request.context.tone}
- Primary Color: {request.context.primaryColor}
- Secondary Color: {request.context.secondaryColor}
{f'- Accent Color: {request.context.accentColor}' if request.context.accentColor else ''}
{f'- Industry: {request.context.industry}' if request.context.industry else ''}"""

        # Build message history
        conversation_messages = []
        
        # Add the current HTML as context in the first user message
        conversation_messages.append({
            "role": "user",
            "content": f"Here is the current email template:\n\n{request.currentHtml}\n\nPlease help me make changes to this template.",
        })
        
        # Add a placeholder assistant acknowledgment
        conversation_messages.append({
            "role": "assistant",
            "content": "I can see your email template. What changes would you like me to make?",
        })
        
        # Add previous conversation messages
        for msg in request.messages:
            conversation_messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        # Add the new user message
        conversation_messages.append({
            "role": "user",
            "content": request.newMessage,
        })
        
        # Create streaming response
        async def generate():
            try:
                full_response = ""
                
                with client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=16384,
                    system=system_prompt,
                    messages=conversation_messages,
                ) as stream:
                    for text in stream.text_stream:
                        full_response += text
                        # Send chunk to client
                        chunk_data = {"type": "chunk", "content": text}
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                
                # Parse the final response
                import re
                html_match = re.search(r'<html>([\s\S]*?)</html>', full_response)
                explanation_match = re.search(r'<explanation>([\s\S]*?)</explanation>', full_response)
                
                result = {
                    "type": "complete",
                    "html": html_match.group(1).strip() if html_match else None,
                    "explanation": explanation_match.group(1).strip() if explanation_match else "Changes applied.",
                    "fullResponse": full_response,
                }
                
                yield f"data: {json.dumps(result)}\n\n"
                
            except Exception as e:
                error_data = {"type": "error", "error": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid API key")
        raise HTTPException(status_code=500, detail=f"Chat failed: {error_msg}")


@router.post("/chat-sync")
async def chat_with_template_sync(request: ChatRequest):
    """
    Non-streaming version of chat endpoint for simpler integration.
    Returns the complete response in one JSON object.
    """
    try:
        if not request.apiKey:
            raise HTTPException(status_code=400, detail="API key is required")
        
        if not request.currentHtml or not request.newMessage:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        client = Anthropic(api_key=request.apiKey)
        
        # Build system prompt with context
        system_prompt = f"""{CHAT_SYSTEM_PROMPT}

## Current Template Context
- Brand: {request.context.brandName}
- Email Type: {request.context.emailType}
- Tone: {request.context.tone}
- Primary Color: {request.context.primaryColor}
- Secondary Color: {request.context.secondaryColor}
{f'- Accent Color: {request.context.accentColor}' if request.context.accentColor else ''}
{f'- Industry: {request.context.industry}' if request.context.industry else ''}"""

        # Build message history
        conversation_messages = []
        
        # Add the current HTML as context in the first user message
        conversation_messages.append({
            "role": "user",
            "content": f"Here is the current email template:\n\n{request.currentHtml}\n\nPlease help me make changes to this template.",
        })
        
        # Add a placeholder assistant acknowledgment
        conversation_messages.append({
            "role": "assistant",
            "content": "I can see your email template. What changes would you like me to make?",
        })
        
        # Add previous conversation messages
        for msg in request.messages:
            conversation_messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        # Add the new user message
        conversation_messages.append({
            "role": "user",
            "content": request.newMessage,
        })
        
        # Create non-streaming response
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16384,
            system=system_prompt,
            messages=conversation_messages,
        )
        
        full_response = ""
        if response.content and response.content[0].type == "text":
            full_response = response.content[0].text
        
        # Parse the response
        import re
        html_match = re.search(r'<html>([\s\S]*?)</html>', full_response)
        explanation_match = re.search(r'<explanation>([\s\S]*?)</explanation>', full_response)
        
        return {
            "html": html_match.group(1).strip() if html_match else None,
            "explanation": explanation_match.group(1).strip() if explanation_match else "Changes applied.",
            "fullResponse": full_response,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid API key")
        raise HTTPException(status_code=500, detail=f"Chat failed: {error_msg}")
