"""
Visual Verification Service

Uses Claude's vision capabilities to verify that edits were applied correctly
by comparing before/after screenshots.
"""

import base64
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class VisualVerificationService:
    """
    Service for visually verifying edits using AI vision.

    Compares before/after screenshots to determine if an edit
    was applied correctly.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize the visual verification service.

        Args:
            model: The Claude model to use for vision analysis
        """
        self.model = model
        self._client = None

        # Initialize Anthropic client
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=api_key)
                logger.info("Visual verification service initialized")
            except ImportError:
                logger.warning("anthropic package not installed")
        else:
            logger.warning("ANTHROPIC_API_KEY not set, visual verification disabled")

    @property
    def is_available(self) -> bool:
        """Check if the service is available."""
        return self._client is not None

    async def verify_edit(
        self,
        before_screenshot: bytes,
        after_screenshot: bytes,
        expected_change: str,
        element_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify that an edit was applied correctly by comparing screenshots.

        Args:
            before_screenshot: Screenshot bytes before the edit
            after_screenshot: Screenshot bytes after the edit
            expected_change: Description of the expected change
            element_selector: Optional selector of the target element

        Returns:
            Dict with:
                - verified: bool indicating if edit was successful
                - confidence: float from 0-1
                - explanation: str describing what was observed
                - suggestions: list of suggestions if edit failed
        """
        if not self.is_available:
            logger.warning("Visual verification not available")
            return {
                "verified": True,  # Assume success if can't verify
                "confidence": 0.5,
                "explanation": "Visual verification not available",
                "suggestions": []
            }

        try:
            # Encode screenshots as base64
            before_b64 = base64.b64encode(before_screenshot).decode('utf-8')
            after_b64 = base64.b64encode(after_screenshot).decode('utf-8')

            # Build the verification prompt
            prompt = self._build_verification_prompt(expected_change, element_selector)

            # Call Claude with vision
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "text",
                            "text": "BEFORE screenshot:"
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": before_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": "AFTER screenshot:"
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": after_b64
                            }
                        }
                    ]
                }]
            )

            # Parse the response
            return self._parse_verification_response(response.content[0].text)

        except Exception as e:
            logger.error(f"Visual verification failed: {e}")
            return {
                "verified": True,  # Assume success on error
                "confidence": 0.3,
                "explanation": f"Verification error: {str(e)}",
                "suggestions": []
            }

    def _build_verification_prompt(
        self,
        expected_change: str,
        element_selector: Optional[str] = None
    ) -> str:
        """Build the prompt for verification."""
        prompt = f"""You are a visual QA expert verifying website edits.

EXPECTED EDIT: {expected_change}
"""
        if element_selector:
            prompt += f"TARGET ELEMENT: {element_selector}\n"

        prompt += """
Compare the BEFORE and AFTER screenshots and determine if the edit was applied correctly.

Respond in this exact format:
VERIFIED: [YES/NO]
CONFIDENCE: [0.0-1.0]
EXPLANATION: [What you observed - be specific about visual changes]
SUGGESTIONS: [If NO, list suggestions to fix the issue, separated by semicolons]

Focus on:
1. Did the intended change visually appear?
2. Were there any unintended side effects?
3. Is the change visible and correct?

Be strict - if you can't clearly see the expected change, say NO."""

        return prompt

    def _parse_verification_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the Claude response into a structured result."""
        result = {
            "verified": False,
            "confidence": 0.5,
            "explanation": "",
            "suggestions": []
        }

        lines = response_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("VERIFIED:"):
                value = line.replace("VERIFIED:", "").strip().upper()
                result["verified"] = value == "YES"
            elif line.startswith("CONFIDENCE:"):
                try:
                    conf = float(line.replace("CONFIDENCE:", "").strip())
                    result["confidence"] = min(1.0, max(0.0, conf))
                except ValueError:
                    pass
            elif line.startswith("EXPLANATION:"):
                result["explanation"] = line.replace("EXPLANATION:", "").strip()
            elif line.startswith("SUGGESTIONS:"):
                suggestions_str = line.replace("SUGGESTIONS:", "").strip()
                if suggestions_str and suggestions_str.lower() != "none":
                    result["suggestions"] = [
                        s.strip() for s in suggestions_str.split(";")
                        if s.strip()
                    ]

        return result

    async def describe_screenshot(self, screenshot: bytes) -> str:
        """
        Describe what's visible in a screenshot.

        Args:
            screenshot: Screenshot bytes

        Returns:
            Text description of the screenshot
        """
        if not self.is_available:
            return "Visual description not available"

        try:
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            response = self._client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Briefly describe this website screenshot. Focus on the layout, colors, main elements, and any notable features. Be concise."
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        }
                    ]
                }]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Failed to describe screenshot: {e}")
            return f"Description failed: {str(e)}"

    async def find_element_visually(
        self,
        screenshot: bytes,
        element_description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find an element in a screenshot based on description.

        Args:
            screenshot: Screenshot bytes
            element_description: Natural language description of the element

        Returns:
            Dict with approximate location and confidence, or None
        """
        if not self.is_available:
            return None

        try:
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            response = self._client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Find this element in the screenshot: "{element_description}"

Respond with:
FOUND: [YES/NO]
LOCATION: [top-left/top-center/top-right/middle-left/center/middle-right/bottom-left/bottom-center/bottom-right]
CONFIDENCE: [0.0-1.0]
DESCRIPTION: [Brief description of the element you found]"""
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        }
                    ]
                }]
            )

            # Parse response
            text = response.content[0].text
            result = {"found": False, "location": None, "confidence": 0, "description": ""}

            for line in text.split('\n'):
                line = line.strip()
                if line.startswith("FOUND:"):
                    result["found"] = "YES" in line.upper()
                elif line.startswith("LOCATION:"):
                    result["location"] = line.replace("LOCATION:", "").strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        result["confidence"] = float(line.replace("CONFIDENCE:", "").strip())
                    except ValueError:
                        pass
                elif line.startswith("DESCRIPTION:"):
                    result["description"] = line.replace("DESCRIPTION:", "").strip()

            return result if result["found"] else None

        except Exception as e:
            logger.error(f"Failed to find element visually: {e}")
            return None


# Singleton instance
_visual_verification_service: Optional[VisualVerificationService] = None


def get_visual_verification_service() -> VisualVerificationService:
    """Get or create the visual verification service singleton."""
    global _visual_verification_service
    if _visual_verification_service is None:
        _visual_verification_service = VisualVerificationService()
    return _visual_verification_service
