"""
Design Context Extractor

Extracts design metadata from generated HTML to preserve design consistency during editing.
Parses fonts, colors, sections, and design tokens from the HTML/CSS.
"""

import re
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse


def extract_design_context(html: str, template_id: str = "unknown") -> dict:
    """
    Parse generated HTML to extract design metadata.

    Args:
        html: The generated HTML string
        template_id: The template ID used for generation

    Returns:
        Dictionary containing design context metadata
    """
    soup = BeautifulSoup(html, 'html.parser')

    return {
        "template_id": template_id,
        "fonts": extract_fonts(soup),
        "colors": extract_colors(soup, html),
        "sections": extract_sections(soup),
        "tokens": extract_design_tokens(soup),
    }


def extract_fonts(soup: BeautifulSoup) -> dict:
    """
    Extract Google Fonts from <link> tags.

    Returns:
        Dict with 'display' and 'body' font families
    """
    fonts = {
        "display": None,
        "body": None,
        "all_fonts": []
    }

    # Find Google Fonts links
    font_links = soup.find_all('link', href=re.compile(r'fonts\.googleapis\.com'))

    for link in font_links:
        href = link.get('href', '')

        # Parse family parameter from Google Fonts URL
        # Format: https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@400;500
        if 'family=' in href:
            # Extract all family parameters
            families = re.findall(r'family=([^&]+)', href)
            for family_param in families:
                # Handle multiple families separated by &family=
                font_parts = family_param.split('&family=')
                for part in font_parts:
                    # Extract font name (before : or +)
                    font_name = part.split(':')[0].replace('+', ' ')
                    if font_name and font_name not in fonts["all_fonts"]:
                        fonts["all_fonts"].append(font_name)

    # Also check for @import statements in style tags
    style_tags = soup.find_all('style')
    for style in style_tags:
        if style.string:
            imports = re.findall(r"@import\s+url\(['\"]?([^'\"]+)['\"]?\)", style.string)
            for import_url in imports:
                if 'fonts.googleapis.com' in import_url:
                    families = re.findall(r'family=([^&\)]+)', import_url)
                    for family in families:
                        font_name = family.split(':')[0].replace('+', ' ')
                        if font_name and font_name not in fonts["all_fonts"]:
                            fonts["all_fonts"].append(font_name)

    # Categorize fonts based on common patterns
    display_fonts = ['Playfair Display', 'Fraunces', 'Space Grotesk', 'Clash Display',
                     'Syne', 'Cabinet Grotesk', 'Satoshi', 'Poppins', 'Montserrat',
                     'Bebas Neue', 'Oswald', 'Abril Fatface', 'Cormorant']
    body_fonts = ['DM Sans', 'Plus Jakarta Sans', 'Outfit', 'Manrope', 'Source Serif Pro',
                  'Inter', 'Roboto', 'Open Sans', 'Lato', 'Nunito', 'Work Sans']

    for font in fonts["all_fonts"]:
        if not fonts["display"] and any(df.lower() in font.lower() for df in display_fonts):
            fonts["display"] = font
        elif not fonts["body"] and any(bf.lower() in font.lower() for bf in body_fonts):
            fonts["body"] = font

    # If we couldn't categorize, use first two fonts
    if not fonts["display"] and len(fonts["all_fonts"]) > 0:
        fonts["display"] = fonts["all_fonts"][0]
    if not fonts["body"] and len(fonts["all_fonts"]) > 1:
        fonts["body"] = fonts["all_fonts"][1]
    elif not fonts["body"] and fonts["display"]:
        fonts["body"] = fonts["display"]

    return fonts


def extract_colors(soup: BeautifulSoup, html: str) -> dict:
    """
    Extract color palette from CSS variables and inline styles.

    Returns:
        Dict with color categories (primary, accent, background, text, etc.)
    """
    colors = {
        "primary": None,
        "accent": None,
        "background": None,
        "text": None,
        "surface": None,
        "all_colors": {}
    }

    # Find CSS variables in style tags
    style_tags = soup.find_all('style')
    css_content = '\n'.join([s.string or '' for s in style_tags])

    # Pattern for CSS custom properties (variables)
    # Matches: --color-primary: #xxx or --primary: #xxx or --bg-color: rgb(...)
    var_patterns = [
        r'--([\w-]+):\s*(#[0-9a-fA-F]{3,8})',  # Hex colors
        r'--([\w-]+):\s*(rgb\([^)]+\))',         # RGB colors
        r'--([\w-]+):\s*(rgba\([^)]+\))',        # RGBA colors
        r'--([\w-]+):\s*(hsl\([^)]+\))',         # HSL colors
    ]

    for pattern in var_patterns:
        matches = re.findall(pattern, css_content)
        for var_name, color_value in matches:
            colors["all_colors"][var_name] = color_value

            # Categorize based on variable name
            var_lower = var_name.lower()
            if 'primary' in var_lower and not colors["primary"]:
                colors["primary"] = color_value
            elif 'accent' in var_lower and not colors["accent"]:
                colors["accent"] = color_value
            elif ('background' in var_lower or 'bg' in var_lower) and not colors["background"]:
                colors["background"] = color_value
            elif ('text' in var_lower or 'foreground' in var_lower) and not colors["text"]:
                colors["text"] = color_value
            elif 'surface' in var_lower and not colors["surface"]:
                colors["surface"] = color_value

    # Also look for Tailwind @theme definitions
    theme_match = re.search(r'@theme\s*\{([^}]+)\}', css_content)
    if theme_match:
        theme_content = theme_match.group(1)
        theme_vars = re.findall(r'--([\w-]+):\s*([^;]+);', theme_content)
        for var_name, value in theme_vars:
            value = value.strip()
            if value.startswith('#') or value.startswith('rgb') or value.startswith('hsl'):
                colors["all_colors"][var_name] = value

    # Fallback: Look for common color patterns in body/html styles
    if not colors["background"]:
        body = soup.find('body')
        if body and body.get('class'):
            classes = ' '.join(body.get('class', []))
            # Check for Tailwind bg classes
            bg_match = re.search(r'bg-\[([^\]]+)\]', classes)
            if bg_match:
                colors["background"] = bg_match.group(1)
            elif 'bg-black' in classes or 'bg-gray-900' in classes or 'bg-zinc-900' in classes:
                colors["background"] = "#0a0a0a"
            elif 'bg-white' in classes:
                colors["background"] = "#ffffff"

    return colors


def extract_sections(soup: BeautifulSoup) -> list:
    """
    Identify page sections from DOM structure.

    Returns:
        List of section identifiers in order
    """
    sections = []

    # Find semantic elements
    section_elements = soup.find_all(['header', 'nav', 'main', 'section', 'footer', 'aside'])

    for element in section_elements:
        section_info = {
            "tag": element.name,
            "id": element.get('id'),
            "classes": element.get('class', []),
            "type": None
        }

        # Try to identify section type from id, class, or content
        identifier = (element.get('id') or '') + ' ' + ' '.join(element.get('class', []))
        identifier = identifier.lower()

        if 'hero' in identifier or 'banner' in identifier:
            section_info["type"] = "hero"
        elif 'service' in identifier:
            section_info["type"] = "services"
        elif 'testimonial' in identifier or 'review' in identifier:
            section_info["type"] = "testimonials"
        elif 'about' in identifier:
            section_info["type"] = "about"
        elif 'contact' in identifier:
            section_info["type"] = "contact"
        elif 'footer' in identifier or element.name == 'footer':
            section_info["type"] = "footer"
        elif 'header' in identifier or element.name == 'header':
            section_info["type"] = "header"
        elif 'nav' in identifier or element.name == 'nav':
            section_info["type"] = "navigation"
        elif 'pricing' in identifier:
            section_info["type"] = "pricing"
        elif 'feature' in identifier or 'benefit' in identifier:
            section_info["type"] = "features"
        elif 'cta' in identifier or 'call-to-action' in identifier:
            section_info["type"] = "cta"
        elif 'faq' in identifier:
            section_info["type"] = "faq"
        else:
            section_info["type"] = element.name

        sections.append(section_info)

    return sections


def extract_design_tokens(soup: BeautifulSoup) -> dict:
    """
    Extract design tokens from Tailwind classes and CSS.

    Returns:
        Dict with spacing, border-radius, shadow patterns
    """
    tokens = {
        "spacing_strategy": "unknown",
        "border_radius": "unknown",
        "shadow_style": "unknown",
        "common_classes": []
    }

    # Collect all classes from the document
    all_classes = []
    for element in soup.find_all(class_=True):
        all_classes.extend(element.get('class', []))

    # Count class occurrences
    class_counts = {}
    for cls in all_classes:
        class_counts[cls] = class_counts.get(cls, 0) + 1

    # Analyze spacing patterns
    spacing_classes = [c for c in all_classes if re.match(r'p[xy]?-\d+|m[xy]?-\d+', c)]
    if spacing_classes:
        # Check for generous vs tight spacing
        large_spacing = sum(1 for c in spacing_classes if any(s in c for s in ['24', '32', '20', '16']))
        small_spacing = sum(1 for c in spacing_classes if any(s in c for s in ['2', '4', '1', '3']))

        if large_spacing > small_spacing:
            tokens["spacing_strategy"] = "generous"
        elif small_spacing > large_spacing:
            tokens["spacing_strategy"] = "tight"
        else:
            tokens["spacing_strategy"] = "balanced"

    # Analyze border radius patterns
    radius_classes = [c for c in all_classes if c.startswith('rounded')]
    if radius_classes:
        if any('rounded-full' in c for c in radius_classes):
            tokens["border_radius"] = "full"
        elif any('rounded-2xl' in c or 'rounded-3xl' in c for c in radius_classes):
            tokens["border_radius"] = "large"
        elif any('rounded-lg' in c or 'rounded-xl' in c for c in radius_classes):
            tokens["border_radius"] = "medium"
        elif any('rounded-md' in c or 'rounded' in c for c in radius_classes):
            tokens["border_radius"] = "small"
        elif any('rounded-none' in c for c in radius_classes):
            tokens["border_radius"] = "none"

    # Analyze shadow patterns
    shadow_classes = [c for c in all_classes if c.startswith('shadow')]
    if shadow_classes:
        if any('shadow-2xl' in c or 'shadow-xl' in c for c in shadow_classes):
            tokens["shadow_style"] = "dramatic"
        elif any('shadow-lg' in c or 'shadow-md' in c for c in shadow_classes):
            tokens["shadow_style"] = "standard"
        elif any('shadow-sm' in c or 'shadow' == c for c in shadow_classes):
            tokens["shadow_style"] = "subtle"
        elif any('shadow-none' in c for c in shadow_classes):
            tokens["shadow_style"] = "none"

    # Get most common utility classes (excluding basic ones)
    common = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    tokens["common_classes"] = [c for c, count in common if count > 2]

    return tokens


def format_design_context_for_prompt(design_context: dict) -> str:
    """
    Format design context as a string suitable for including in AI prompts.

    Args:
        design_context: The extracted design context dictionary

    Returns:
        Formatted string for prompt inclusion
    """
    lines = ["## DESIGN CONTEXT (Extracted from current website)"]

    # Template
    if design_context.get("template_id"):
        lines.append(f"\n### Template: {design_context['template_id']}")

    # Typography
    fonts = design_context.get("fonts", {})
    if fonts.get("display") or fonts.get("body"):
        lines.append("\n### Typography")
        if fonts.get("display"):
            lines.append(f"- Display font: {fonts['display']}")
        if fonts.get("body"):
            lines.append(f"- Body font: {fonts['body']}")
        lines.append("- DO NOT introduce new fonts")

    # Colors
    colors = design_context.get("colors", {})
    if any(colors.get(k) for k in ["primary", "accent", "background", "text"]):
        lines.append("\n### Color Palette")
        if colors.get("primary"):
            lines.append(f"- Primary: {colors['primary']}")
        if colors.get("accent"):
            lines.append(f"- Accent: {colors['accent']}")
        if colors.get("background"):
            lines.append(f"- Background: {colors['background']}")
        if colors.get("text"):
            lines.append(f"- Text: {colors['text']}")
        lines.append("- ONLY use colors from this palette unless asked otherwise")

    # Sections
    sections = design_context.get("sections", [])
    if sections:
        section_types = [s.get("type", s.get("tag")) for s in sections if s.get("type") or s.get("tag")]
        if section_types:
            lines.append(f"\n### Page Structure")
            lines.append(f"Sections: {' → '.join(section_types)}")
            lines.append("- Maintain section order unless explicitly asked to change")

    # Design tokens
    tokens = design_context.get("tokens", {})
    if tokens:
        lines.append("\n### Design Tokens")
        if tokens.get("spacing_strategy") != "unknown":
            lines.append(f"- Spacing: {tokens['spacing_strategy']}")
        if tokens.get("border_radius") != "unknown":
            lines.append(f"- Border radius: {tokens['border_radius']}")
        if tokens.get("shadow_style") != "unknown":
            lines.append(f"- Shadows: {tokens['shadow_style']}")

    return '\n'.join(lines)
