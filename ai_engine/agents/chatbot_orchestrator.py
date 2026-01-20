"""
Chatbot Orchestrator - Manages conversation modes and agent routing for AI website building.
Uses OpenRouter API for AI capabilities.
"""
from typing import Dict, Any, List, Optional, AsyncIterator
from enum import Enum
from dataclasses import dataclass, field
import json
import re
import httpx
from logging_config import logger
from config import settings


class ChatMode(Enum):
    """Chat interaction modes"""
    TEMPLATE_SELECTION = "template_selection"
    SECTION_BUILDER = "section_builder"
    FREEFORM_CHAT = "freeform_chat"


@dataclass
class ConversationState:
    """Tracks conversation context across turns"""
    session_id: str
    mode: ChatMode = ChatMode.TEMPLATE_SELECTION
    username: Optional[str] = None
    user_profile: Optional[Dict] = None
    current_html: str = ""
    selected_template: Optional[str] = None
    completed_sections: List[str] = field(default_factory=list)
    conversation_history: List[Dict] = field(default_factory=list)
    pending_suggestions: List[Dict] = field(default_factory=list)


# System prompts for each mode
TEMPLATE_AGENT_PROMPT = """You are a website design assistant helping users choose a template style for their portfolio website.

Your job is to:
1. Understand the user's brand/style preferences
2. Suggest appropriate templates based on their needs
3. Help them make a decision

Available templates:
- **modern-gradient**: Gradient backgrounds, bold typography, animated sections
- **minimal-clean**: Clean white space, subtle colors, elegant typography
- **bold-creative**: Vibrant colors, unique layouts, attention-grabbing
- **professional-corporate**: Traditional layout, trustworthy feel, business-focused
- **dark-mode**: Dark backgrounds, neon accents, modern tech aesthetic

When the user selects a template, respond with:
[ACTION: SELECT_TEMPLATE - template_name]"""


SECTION_BUILDER_PROMPT = """You are a website section builder assistant guiding users through creating their website section by section.

Guide the user through these sections:
1. Hero Section - Name, tagline, profile image, primary CTA
2. About Section - Bio, expertise, professional highlights
3. Services Section - Services with pricing and descriptions
4. Testimonials Section - Reviews and ratings from clients
5. Contact Section - Social links, booking CTA

When generating a section: [ACTION: GENERATE_SECTION - section_name]
When complete: [ACTION: SECTION_COMPLETE - section_name]"""


FREEFORM_AGENT_PROMPT = """You are an AI website editing assistant. Your job is to EXECUTE edits immediately, not ask questions.

## CRITICAL RULES:
1. **NEVER ASK QUESTIONS** - You have all the context you need. Just do it.
2. **ALWAYS USE ACTIONS** - Every response must include an [ACTION:] command
3. **BE CONCISE** - Short responses, no long explanations
4. **MAKE DECISIONS** - If something is ambiguous, make your best judgment

## AVAILABLE ACTIONS:
- [ACTION: EDIT_WEBSITE - description] - For any visual/content changes
- [ACTION: ADD_SECTION - section_type] - Add new sections
- [ACTION: REMOVE_ELEMENT - element_description] - Remove elements

## EXAMPLES:
User: "make it darker"
Response: Making the background darker. [ACTION: EDIT_WEBSITE - Change background to a darker shade]

User: "change the color to blue"
Response: Changing to blue. [ACTION: EDIT_WEBSITE - Change color to blue]

User: "replace image with https://example.com/img.jpg"
Response: Replacing image. [ACTION: EDIT_WEBSITE - Replace image src with https://example.com/img.jpg]

## IMPORTANT:
- Do NOT ask "which element?" - use the selected element context
- Do NOT ask "what shade?" - pick a reasonable default
- Do NOT explain options - just execute the most likely intent"""


SUGGESTION_PROMPTS = {
    ChatMode.TEMPLATE_SELECTION: [
        "Help me choose a template",
        "Show me modern designs",
        "I want something professional"
    ],
    ChatMode.SECTION_BUILDER: [
        "Start building my hero section",
        "Add my services",
        "Include testimonials"
    ],
    ChatMode.FREEFORM_CHAT: [
        "Change the color scheme",
        "Make the text bigger",
        "Add a new section"
    ]
}


class ChatbotOrchestrator:
    """
    Main orchestrator for chatbot interactions.
    Uses OpenRouter API for AI responses.
    """

    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.sessions: Dict[str, ConversationState] = {}
        self.model = "anthropic/claude-3.5-sonnet"
        logger.info("ChatbotOrchestrator initialized")

    def get_or_create_session(self, session_id: str) -> ConversationState:
        """Get existing session or create new one"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationState(session_id=session_id)
            logger.info(f"Created new session: {session_id}")
        return self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Get existing session without creating"""
        return self.sessions.get(session_id)

    def update_session_html(self, session_id: str, html: str) -> bool:
        """Update the current HTML for a session"""
        state = self.sessions.get(session_id)
        if state:
            state.current_html = html
            return True
        return False

    def set_user_profile(self, session_id: str, username: str, profile: Dict) -> None:
        """Set user profile for a session"""
        state = self.get_or_create_session(session_id)
        state.username = username
        state.user_profile = profile

        # Generate intelligent suggestions based on profile
        from mcp_tools.galactus_tools import get_chatbot_suggestions
        suggestions = get_chatbot_suggestions(profile, username)
        state.pending_suggestions = suggestions
        logger.info(f"Generated {len(suggestions.get('template_suggestions', []))} template suggestions for {username}")

    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict] = None
    ) -> AsyncIterator[Dict]:
        """Process incoming chat message and stream response."""
        state = self.get_or_create_session(session_id)

        # Add message to history
        state.conversation_history.append({
            "role": "user",
            "content": message
        })

        # Detect mode switch commands
        new_mode = self._detect_mode_switch(message)
        if new_mode and new_mode != state.mode:
            state.mode = new_mode
            yield {"type": "mode_change", "mode": new_mode.value}
            logger.info(f"Session {session_id} switched to mode: {new_mode.value}")

        # Get system prompt for mode
        system_prompt = self._get_system_prompt(state.mode)

        # Build context-aware prompt
        prompt = self._build_contextual_prompt(state, message, context)

        # Stream response from OpenRouter
        async for chunk in self._stream_response(system_prompt, prompt, state):
            yield chunk

    def _detect_mode_switch(self, message: str) -> Optional[ChatMode]:
        """Detect if user wants to switch modes"""
        message_lower = message.lower()

        if any(kw in message_lower for kw in ["choose template", "pick template", "select template"]):
            return ChatMode.TEMPLATE_SELECTION
        elif any(kw in message_lower for kw in ["build section", "add section", "step by step"]):
            return ChatMode.SECTION_BUILDER
        elif any(kw in message_lower for kw in ["edit", "change", "modify", "help me"]):
            return ChatMode.FREEFORM_CHAT

        return None

    def _get_system_prompt(self, mode: ChatMode) -> str:
        """Get system prompt for current mode"""
        return {
            ChatMode.TEMPLATE_SELECTION: TEMPLATE_AGENT_PROMPT,
            ChatMode.SECTION_BUILDER: SECTION_BUILDER_PROMPT,
            ChatMode.FREEFORM_CHAT: FREEFORM_AGENT_PROMPT
        }[mode]

    def _build_contextual_prompt(
        self,
        state: ConversationState,
        message: str,
        context: Optional[Dict]
    ) -> str:
        """Build prompt with full context"""
        prompt_parts = []

        # Add user profile if available
        if state.user_profile:
            profile_summary = self._summarize_profile(state.user_profile)
            prompt_parts.append(f"USER PROFILE DATA:\n{profile_summary}")

        # Add current website status
        if state.current_html:
            prompt_parts.append(f"CURRENT WEBSITE: Website exists ({len(state.current_html)} bytes)")

        # Add selected template
        if state.selected_template:
            prompt_parts.append(f"SELECTED TEMPLATE: {state.selected_template}")

        # Add context about selected element (IMPORTANT for edits)
        if context:
            if context.get("selected_element"):
                elem = context["selected_element"]
                elem_info = []
                if elem.get("selector"):
                    elem_info.append(f"Selector: {elem['selector']}")
                if elem.get("tag"):
                    elem_info.append(f"Tag: <{elem['tag']}>")
                if elem.get("classes"):
                    classes = elem["classes"] if isinstance(elem["classes"], str) else " ".join(elem["classes"])
                    elem_info.append(f"Classes: {classes}")
                if elem.get("text"):
                    elem_info.append(f"Text: {elem['text'][:100]}")

                prompt_parts.append(f"SELECTED ELEMENT (apply edits to THIS element):\n" + "\n".join(elem_info))

            if context.get("selected_component"):
                prompt_parts.append(f"SELECTED COMPONENT: {context['selected_component']}")

        # Add current message
        prompt_parts.append(f"USER MESSAGE: {message}")

        # Reminder to not ask questions
        prompt_parts.append("REMINDER: Do NOT ask questions. Just execute the edit based on the context above.")

        return "\n\n".join(prompt_parts)

    def _summarize_profile(self, profile: Dict) -> str:
        """Create summary of user profile"""
        parts = []

        if profile.get("name"):
            parts.append(f"Name: {profile['name']}")
        if profile.get("tagline"):
            parts.append(f"Tagline: {profile['tagline']}")
        if profile.get("bio"):
            parts.append(f"Bio: {profile['bio'][:200]}...")

        services = profile.get("services", [])
        if services:
            parts.append(f"Services: {len(services)} services available")

        stats = profile.get("stats", {})
        if stats:
            parts.append(f"Rating: {stats.get('rating', 0)} | Bookings: {stats.get('bookings', 0)}")

        return "\n".join(parts)

    async def _stream_response(
        self,
        system_prompt: str,
        prompt: str,
        state: ConversationState
    ) -> AsyncIterator[Dict]:
        """Stream response from OpenRouter"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.OPENROUTER_API_URL,
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
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 2048,
                        "temperature": 0.7,
                        "stream": False  # Non-streaming for simplicity
                    }
                )

                if response.status_code != 200:
                    logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                    yield {"type": "error", "message": f"API error: {response.status_code}"}
                    yield {"type": "done"}
                    return

                result = response.json()
                full_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Yield the full response as text
                yield {"type": "text", "content": full_response}

                # Parse for suggestions and actions
                suggestions = self._extract_suggestions(full_response, state.mode)
                if suggestions:
                    yield {"type": "suggestions", "items": suggestions}

                actions = self._extract_actions(full_response)
                if actions:
                    yield {"type": "actions", "items": actions}

                # Add to history
                state.conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })

                yield {"type": "done"}

        except Exception as e:
            logger.error(f"Agent streaming error: {str(e)}")
            yield {"type": "error", "message": str(e)}
            yield {"type": "done"}

    def _extract_suggestions(self, response: str, mode: ChatMode) -> List[Dict]:
        """Extract actionable suggestions from response"""
        suggestions = []

        pattern = r'\[SUGGEST:\s*(.+?)\]'
        matches = re.findall(pattern, response)
        for match in matches:
            suggestions.append({"text": match, "type": "suggestion"})

        if not suggestions:
            default_suggestions = SUGGESTION_PROMPTS.get(mode, [])[:3]
            for text in default_suggestions:
                suggestions.append({"text": text, "type": "default"})

        return suggestions

    def _extract_actions(self, response: str) -> List[Dict]:
        """Extract executable actions from response"""
        actions = []

        # Log the response for debugging
        logger.info(f"Extracting actions from response: {response[:500]}...")

        pattern = r'\[ACTION:\s*(\w+)\s*-\s*(.+?)\]'
        matches = re.findall(pattern, response)

        logger.info(f"Found {len(matches)} action matches")

        for action_type, action_data in matches:
            actions.append({
                "type": action_type.upper(),
                "data": action_data.strip()
            })
            logger.info(f"Extracted action: {action_type} - {action_data}")

        # If no actions found but response contains edit-like content, create one
        if not actions and any(kw in response.lower() for kw in ['change', 'update', 'modify', 'replace', 'make']):
            # The AI didn't use the [ACTION:] format, but described an edit
            logger.warning(f"AI response contains edit intent but no [ACTION:] tag. Response: {response[:200]}")

        return actions

    def get_initial_suggestions(self, session_id: str, mode: ChatMode) -> List[Dict]:
        """Get initial suggestions for a mode"""
        state = self.sessions.get(session_id)

        if state and state.pending_suggestions:
            suggestions = state.pending_suggestions

            if mode == ChatMode.TEMPLATE_SELECTION:
                return [
                    {
                        "text": f"Use {t['name']} template",
                        "type": "template",
                        "template_id": t['id'],
                        "description": t['description'],
                        "recommended": t.get('recommended', False)
                    }
                    for t in suggestions.get('template_suggestions', [])[:4]
                ]
            elif mode == ChatMode.SECTION_BUILDER:
                return [
                    {
                        "text": f"Add {s['name']}",
                        "type": "section",
                        "section_id": s['id'],
                        "description": s['description'],
                        "priority": s.get('priority', 'medium')
                    }
                    for s in suggestions.get('section_suggestions', [])[:4]
                ]
            elif mode == ChatMode.FREEFORM_CHAT:
                return [
                    {
                        "text": a['label'],
                        "type": "action",
                        "action": a['action'],
                        "description": a['description']
                    }
                    for a in suggestions.get('quick_actions', [])
                ]

        return [
            {"text": text, "type": "default"}
            for text in SUGGESTION_PROMPTS.get(mode, [])
        ]

    def get_profile_suggestions(self, session_id: str) -> Dict:
        """Get all profile-based suggestions for a session"""
        state = self.sessions.get(session_id)
        if state and state.pending_suggestions:
            return state.pending_suggestions
        return {
            "template_suggestions": [],
            "section_suggestions": [],
            "content_suggestions": [],
            "quick_actions": []
        }

    def set_mode(self, session_id: str, mode: ChatMode) -> bool:
        """Set the chat mode for a session"""
        state = self.sessions.get(session_id)
        if state:
            state.mode = mode
            logger.info(f"Session {session_id} mode set to: {mode.value}")
            return True
        return False

    def mark_section_complete(self, session_id: str, section_name: str) -> None:
        """Mark a section as complete"""
        state = self.sessions.get(session_id)
        if state and section_name not in state.completed_sections:
            state.completed_sections.append(section_name)

    def set_selected_template(self, session_id: str, template_name: str) -> None:
        """Set the selected template"""
        state = self.sessions.get(session_id)
        if state:
            state.selected_template = template_name


# Global orchestrator instance
orchestrator = ChatbotOrchestrator()
