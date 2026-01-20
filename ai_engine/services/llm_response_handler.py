"""
LLM Response Handler - Filter non-text parts from LLM responses
"""

import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class LLMResponseHandler:
    """
    Handle LLM responses and filter non-text components
    """

    # List of non-text component types to filter
    EXCLUDED_PARTS = [
        'thought_signature',
        'thought',
        'thinking',
        'internal_monologue',
        'metadata',
        'debug_info'
    ]

    @staticmethod
    def filter_response(response: Union[str, List, Dict]) -> str:
        """
        Filter non-text parts from LLM response

        Args:
            response: LLM response (can be string, list, or dict)

        Returns:
            Filtered text response
        """
        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            return LLMResponseHandler._filter_dict_response(response)

        if isinstance(response, list):
            return LLMResponseHandler._filter_list_response(response)

        # Fallback: convert to string
        return str(response)

    @staticmethod
    def _filter_dict_response(response_dict: Dict) -> str:
        """Filter dictionary response"""
        text_parts = []

        for key, value in response_dict.items():
            # Skip excluded keys
            if key in LLMResponseHandler.EXCLUDED_PARTS:
                logger.debug(f"Skipping non-text component: {key}")
                continue

            # Handle nested content
            if isinstance(value, str):
                if value.strip():
                    text_parts.append(value)
            elif isinstance(value, (list, dict)):
                # Recursively filter nested structures
                filtered = LLMResponseHandler.filter_response(value)
                if filtered.strip():
                    text_parts.append(filtered)
            elif isinstance(value, (int, float, bool)):
                # Include simple data types
                text_parts.append(str(value))

        return ' '.join(text_parts)

    @staticmethod
    def _filter_list_response(response_list: List) -> str:
        """Filter list response"""
        text_parts = []

        for item in response_list:
            if isinstance(item, str):
                if item.strip():
                    text_parts.append(item)
            elif isinstance(item, dict):
                # Check if this dict is a non-text component
                if len(item) == 1 and list(item.keys())[0] in LLMResponseHandler.EXCLUDED_PARTS:
                    logger.debug(f"Skipping non-text component: {list(item.keys())[0]}")
                    continue

                # Recursively filter
                filtered = LLMResponseHandler.filter_response(item)
                if filtered.strip():
                    text_parts.append(filtered)
            elif isinstance(item, list):
                filtered = LLMResponseHandler.filter_response(item)
                if filtered.strip():
                    text_parts.append(filtered)

        return ' '.join(text_parts)

    @staticmethod
    def handle_response(response: Any, log_warnings: bool = True) -> str:
        """
        Main entry point for handling LLM responses

        Args:
            response: Raw LLM response
            log_warnings: Whether to log warnings about filtered components

        Returns:
            Cleaned text response
        """
        if not response:
            return ""

        # Check for non-text parts before filtering
        non_text_parts = LLMResponseHandler._detect_non_text_parts(response)

        if non_text_parts and log_warnings:
            logger.warning(
                f"Detected non-text parts in LLM response: {non_text_parts}. "
                f"These will be filtered out."
            )

        # Filter and return
        filtered_text = LLMResponseHandler.filter_response(response)

        if not filtered_text.strip():
            logger.warning("After filtering, response contains no text content")
            return ""

        logger.info(f"LLM response filtered and cleaned ({len(filtered_text)} chars)")
        return filtered_text.strip()

    @staticmethod
    def _detect_non_text_parts(response: Any) -> List[str]:
        """Detect what non-text parts are in the response"""
        detected = []

        if isinstance(response, dict):
            for key in response.keys():
                if key in LLMResponseHandler.EXCLUDED_PARTS:
                    detected.append(key)
        elif isinstance(response, list):
            for item in response:
                if isinstance(item, dict):
                    for key in item.keys():
                        if key in LLMResponseHandler.EXCLUDED_PARTS:
                            detected.append(key)

        return list(set(detected))

    @staticmethod
    def clean_html(html: str) -> str:
        """Clean HTML content - remove markdown code blocks if present"""
        html = html.strip()

        # Remove markdown code blocks
        if html.startswith("```html"):
            html = html[7:]
        elif html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]

        return html.strip()
