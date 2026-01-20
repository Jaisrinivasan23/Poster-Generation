"""
Email template generation router - FastAPI version
Migrated from: frontend/app/api/generate/route.ts
"""
import re
import os
import httpx
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from anthropic import Anthropic

router = APIRouter()

# ============================================================================
# SYSTEM PROMPT - EXACT COPY FROM TYPESCRIPT
# ============================================================================

SYSTEM_PROMPT = """You are an expert HTML email template designer. You create production-ready email templates optimized for SuprSend notification infrastructure that work across ALL email clients.

## SUPRSEND PLATFORM REQUIREMENTS

### Variable Syntax (SuprSend/Handlebars)
- Simple variables: {{variableName}}
- Nested variables: {{user.profile.name}} or {{order.items.total}}
- Variables with spaces: {{event.[first name]}}
- URLs and links: Use TRIPLE braces {{{url}}} to avoid HTML escaping
- Default values: {{default variableName "fallback value"}}

### SuprSend Handlebars Helpers
- {{default variable "default_value"}} - Fallback if variable is null/undefined
- {{lowercase string}} - Convert to lowercase
- {{uppercase string}} - Convert to uppercase
- {{capitalize string}} - Capitalize first character
- {{#if condition}}...{{/if}} - Conditional blocks
- {{#each array}}...{{/each}} - Loop through arrays

### SuprSend Global Variables (DOUBLE braces - built-in)
These are platform-provided variables, use exactly as shown:
- {{$hosted_preference_url}} - Unsubscribe/preference center URL (REQUIRED in footer)
- {{$workflow_run_id}} - Workflow tracking ID (if applicable)
Note: Global variables start with $ and use DOUBLE braces (not triple).

### CRITICAL: Variable Mismatch Warning
If a variable doesn't match the payload data, SuprSend will NOT send that notification.

## HTML EMAIL CONSTRAINTS

### Layout Architecture
- Use TABLE-BASED layouts exclusively. Never use flexbox, CSS grid, or float.
- Maximum content width: 600px
- All layout tables MUST have: cellpadding="0" cellspacing="0" border="0" role="presentation"

### Size Limits
- Total HTML under 102KB (Gmail clips larger)
- Style blocks under 8KB

### CSS Rules
SAFE: background-color, color, font-family, font-size, font-weight, text-align, padding, border, width, height, vertical-align

FORBIDDEN: flex, grid, position, float, calc(), CSS variables, transform, animation, display:flex, display:grid

IMPORTANT: Never use "display: flex" or "display: grid" - these do NOT work in email clients!

### Font Stack (with Google Fonts)
PRIMARY FONTS (use with web-safe fallbacks):
- Headlines: "Montserrat", "Poppins", "DM Sans", Arial, sans-serif (weight: 600-700)
- Body: "Inter", "Roboto", "Open Sans", Arial, sans-serif (weight: 400)
- Luxury/Editorial: "Playfair Display", "Merriweather", Georgia, serif

Include Google Fonts link in <head>:
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">

### MSO Conditionals
Multi-column layouts MUST include MSO ghost tables for Outlook.

### MOBILE RESPONSIVENESS (CRITICAL)

The email MUST be fully responsive. Include these responsive styles in <style> block:

@media screen and (max-width: 600px) {
    .email-container {
        width: 100% !important;
        max-width: 100% !important;
    }
    .fluid {
        width: 100% !important;
        max-width: 100% !important;
        height: auto !important;
    }
    .stack-column {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    .stack-column-center {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        text-align: center !important;
    }
    .center-on-mobile {
        text-align: center !important;
        display: block !important;
        margin-left: auto !important;
        margin-right: auto !important;
        float: none !important;
    }
    .hide-on-mobile {
        display: none !important;
    }
    .mobile-padding {
        padding-left: 16px !important;
        padding-right: 16px !important;
    }
    h1 { font-size: 28px !important; line-height: 1.2 !important; }
    h2 { font-size: 24px !important; line-height: 1.2 !important; }
    h3 { font-size: 20px !important; line-height: 1.3 !important; }
}

RESPONSIVE TABLE STRUCTURE:
- Main container: class="email-container" with width="600" AND style="max-width: 600px; width: 100%;"
- Images: class="fluid" with style="max-width: 100%; height: auto;"
- Multi-column layouts: Use class="stack-column" on td elements that should stack
- Padding: Add class="mobile-padding" to cells that need adjusted padding on mobile

ICON ELEMENTS (NO FLEXBOX, NO EMOJIS):

IMPORTANT: Never use emojis as icons - they hurt email deliverability and look unprofessional.

Use hosted PNG icons from these email-safe icon services:

1. **Google Material Icons (PNG)** - Most reliable:
   https://fonts.gstatic.com/s/i/materialicons/{icon_name}/v1/24px.svg
   Or use: https://img.icons8.com/material/{size}/{color}/{icon_name}.png

2. **Icons8 API** - Great variety, customizable:
   https://img.icons8.com/fluency/48/{icon_name}.png
   https://img.icons8.com/color/48/{icon_name}.png
   https://img.icons8.com/ios-filled/48/{color}/{icon_name}.png

3. **Iconify CDN** (PNG format):
   https://api.iconify.design/mdi/{icon_name}.svg?width=48&height=48&color=%23ffffff

Common icon names: checkmark, star, trophy, heart, home, user, email, phone, calendar, clock,
shield, lock, gift, cart, credit-card, thumbs-up, rocket, lightning, medal, crown

ICON PATTERN (table-based, with hosted image):
<table role="presentation" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td width="48" height="48" style="background-color: #2c5282; border-radius: 8px; text-align: center; vertical-align: middle;">
      <img src="https://img.icons8.com/ios-filled/24/ffffff/checkmark.png" width="24" height="24" alt="" style="display: block; margin: 0 auto;">
    </td>
  </tr>
</table>

ALTERNATIVE - Icon without background (cleaner look):
<img src="https://img.icons8.com/fluency/48/checkmark.png" width="48" height="48" alt="" style="display: block;">

NEVER use:
- Emojis (🏆❤️🏠) - hurt deliverability, render inconsistently
- display:flex or display:grid
- Inline SVG (breaks in Outlook)

## MODERN EMAIL DESIGN SYSTEM

### Design Philosophy
Create emails that look like they were designed by a professional agency, NOT generated by AI.
Each email must have a CLEAR VISUAL IDENTITY that is memorable and distinctive.

### Typography (CRITICAL - This Makes or Breaks Design)
SIZE HIERARCHY (dramatic contrast REQUIRED):
- Hero headline: 36-48px (bold, commanding)
- Section headlines: 24-28px
- Body text: 16-18px
- Small text/captions: 12-14px
- Line height: 1.5-1.6 for body text

ALIGNMENT:
- LEFT-ALIGN body text (easier to read than centered)
- Headlines can be centered or left-aligned based on layout
- NEVER center long paragraphs

### Color Application (Use Brand Colors BOLDLY)
- PRIMARY COLOR: Use the brand's primary color boldly - for backgrounds, headlines, NOT just tiny accents
- SECONDARY: Use for backgrounds, section dividers, or large text areas
- ACCENT: Reserve EXCLUSIVELY for CTA buttons - make them POP against everything else
- Backgrounds: Don't default to #ffffff - try light tints of brand colors (e.g., primary color at 5-10% opacity)
- Text: #1a1a1a on light backgrounds, #ffffff on dark (HIGH CONTRAST always)

### Layout Patterns

HERO SECTION OPTIONS (pick one, commit to it):
1. Full-width image with bold text overlay (dramatic)
2. Split layout: image on one side, text on other (modern)
3. Text-only with massive typography on colored background (minimal, elegant)
4. Solid brand-color background with centered headline (clean, bold)

CONTENT SECTIONS:
- Use full-width color blocks to separate sections visually
- Vary padding: 48-60px for major sections, 24-32px for subsections
- Create visual rhythm through VARIED spacing (not equal everywhere)
- Max 65 characters per line for readability

### SPACING RULES (CRITICAL - Follow Exactly)

SECTION PADDING (outer table cells):
- Hero section: padding="48" or style="padding: 48px 24px;"
- Content sections: padding="40" or style="padding: 40px 24px;"
- Footer: padding="32" or style="padding: 32px 24px;"
- Mobile-safe horizontal: always 24px left/right minimum

BETWEEN ELEMENTS (inside sections):
- After headline: 16-20px margin-bottom
- After paragraph: 16px margin-bottom
- Before CTA button: 24-32px margin-top
- Between feature items: 24px minimum

ICON + TEXT LAYOUTS (Feature Lists):
When showing icons with text (like feature lists), use this EXACT pattern with HOSTED ICONS (no emojis!):

<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 24px;">
  <tr>
    <td width="64" valign="top" style="padding-right: 16px;">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td width="48" height="48" style="background-color: #2c5282; border-radius: 8px; text-align: center; vertical-align: middle;">
            <img src="https://img.icons8.com/ios-filled/24/ffffff/checkmark.png" width="24" height="24" alt="" style="display: block; margin: 0 auto;">
          </td>
        </tr>
      </table>
    </td>
    <td valign="top">
      <h4 style="margin: 0 0 8px 0; font-family: 'Montserrat', Arial, sans-serif; font-size: 18px; font-weight: 600; color: #1a1a1a;">Feature Title</h4>
      <p style="margin: 0; font-family: 'Inter', Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #4a4a4a;">Feature description goes here.</p>
    </td>
  </tr>
</table>

ICON URL PATTERNS (choose appropriate icon):
- Checkmark: https://img.icons8.com/ios-filled/24/ffffff/checkmark.png
- Star: https://img.icons8.com/ios-filled/24/ffffff/star.png
- Trophy: https://img.icons8.com/ios-filled/24/ffffff/trophy.png
- Heart: https://img.icons8.com/ios-filled/24/ffffff/heart.png
- Shield: https://img.icons8.com/ios-filled/24/ffffff/shield.png
- Lightning: https://img.icons8.com/ios-filled/24/ffffff/lightning-bolt.png
- Home: https://img.icons8.com/ios-filled/24/ffffff/home.png
- User: https://img.icons8.com/ios-filled/24/ffffff/user.png
- Clock: https://img.icons8.com/ios-filled/24/ffffff/clock.png
- Gift: https://img.icons8.com/ios-filled/24/ffffff/gift.png

For colored icons without background:
- https://img.icons8.com/fluency/48/checkmark.png (colorful)
- https://img.icons8.com/color/48/checkmark.png (flat color)

RULES:
- Icon cell: width="64", valign="top", padding-right: 16px
- Nested table for icon with td having background-color
- Icon image: 24px inside 48px colored cell
- Text cell: valign="top" to align with icon top
- Wrapper table: margin-bottom: 24px for spacing between items
- NEVER use emojis - always use hosted PNG icons

IMAGE + TEXT LAYOUTS:
- Gap between image and text below: 24px minimum
- Image should be display:block to remove extra spacing
- Use style="margin-bottom: 24px;" on image wrapper cell

VERTICAL SPACING BETWEEN SECTIONS:
- Add spacer rows between major sections: <tr><td height="24"></td></tr>
- Or use padding-bottom on section's outer cell

COMMON SPACING MISTAKES TO AVOID:
❌ Icon and text misaligned (not using valign="top")
❌ No gap between icon and text (missing padding-right)
❌ Cramped feature items (less than 24px between rows)
❌ Text touching image (no margin after image)
❌ Inconsistent section padding

### CTA DESIGN (ONE Primary CTA Per Email)
- Minimum size: 200px wide, 50px tall
- Padding: 16px 40px (generous, not cramped)
- Border-radius: 4-8px (slightly rounded, not pill-shaped)
- Background: ACCENT color (must contrast strongly with section background)
- Text: Action-specific verbs ("Start Free Trial", "Get 50% Off", "Claim Your Spot")
- ONE primary CTA per email section - don't compete for attention

### Visual Hierarchy (What Eyes See First)
1. FIRST: Hero headline or hero image
2. SECOND: Value proposition or key message
3. THIRD: CTA button (unmissable)
4. FOURTH: Supporting content below the fold

### DESIGN ANTI-PATTERNS (NEVER GENERATE THESE)
❌ Arial or Helvetica as the ONLY font
❌ #1a73e8 (Google blue) or #6366f1 (generic purple) as primary color
❌ Three-column icon grids (cliché, looks like every other email)
❌ "Click here", "Learn more", "Submit" button text
❌ Centered body paragraphs
❌ Equal spacing everywhere (no visual rhythm)
❌ Gray backgrounds with gray text (low contrast)
❌ Tiny CTA buttons (under 44px tall)
❌ Multiple competing CTAs in same section
❌ Generic stock photo vibes
❌ Purple-to-blue gradients (AI slop signature)
❌ Icons/images misaligned with text (missing valign="top")
❌ No gap between icon and text (cramped look)
❌ Text directly touching images (no margin/padding)
❌ Inconsistent padding between sections
❌ Using display:flex or display:grid (BREAKS in email clients!)
❌ Fixed pixel widths without max-width: 100%
❌ Missing responsive media queries
❌ Non-fluid images (missing class="fluid" and max-width: 100%)
❌ EMOJIS AS ICONS (🏆❤️🏠) - hurts deliverability, looks unprofessional

### DESIGN REQUIREMENTS (ALWAYS INCLUDE)
✅ Dramatic headline typography (36px+ for hero)
✅ Clear visual hierarchy (obvious what to look at first/second/third)
✅ Strategic white space (generous padding, room to breathe)
✅ ONE unmissable CTA per major section
✅ Brand color used prominently (backgrounds, headlines - not just buttons)
✅ Professional, agency-quality aesthetic
✅ Mobile-first stacking (looks good on small screens)
✅ At least one full-width colored section (breaks up white monotony)
✅ Proper icon+text alignment (valign="top", padding-right on icon cell)
✅ Consistent vertical rhythm (24px between items, 40-48px between sections)
✅ Images with display:block and proper margin-bottom
✅ Responsive media queries in <style> block
✅ class="email-container" on main table with width="600" style="max-width: 600px; width: 100%;"
✅ class="fluid" on all images with style="max-width: 100%; height: auto;"
✅ Icons using HOSTED PNG images from Icons8 (NOT emojis, NOT display:flex divs)
✅ Icon URLs from: https://img.icons8.com/ios-filled/24/ffffff/{icon-name}.png

## HANDLEBARS FOR SUPRSEND

### URL Variables (TRIPLE BRACES)
- {{{ctaUrl}}} - Call-to-action URL
- {{{trackingUrl}}} - Tracking links
- {{{logoUrl}}} - Logo image URL
Note: For unsubscribe, use the global variable {{$hosted_preference_url}} (double braces)

### Text Variables (DOUBLE BRACES)
- {{recipientName}} - Recipient name
- {{default recipientName "there"}} - With fallback
- {{order.id}}, {{order.total}} - Order data

## IMAGE RESOURCES

### High-Quality Image Sources (CRITICAL FOR PROFESSIONAL RESULTS)

**IMPORTANT**: Image quality directly impacts email perception. Use these optimized patterns:

1. **Unsplash Direct URLs (PREFERRED - Highest Quality)**:
   Use specific photo IDs with quality parameters:
   https://images.unsplash.com/photo-{photo_id}?w={width}&h={height}&fit=crop&q=85&auto=format

   **Curated photo IDs for common uses:**
   - Professional/Business: photo-1560472354-b33ff0c44a43, photo-1552664730-d307ca884978, photo-1573497019940-1c28c88b4f3e
   - Technology/SaaS: photo-1531297484001-80022131f5a1, photo-1518770660439-4636190af475, photo-1550751827-4bd374c3f58b
   - E-commerce/Products: photo-1441986300917-64674bd600d8, photo-1472851294608-062f824d29cc
   - Food/Restaurant: photo-1504674900247-0877df9cc836, photo-1493770348161-369560ae357d
   - Health/Fitness: photo-1571019613454-1cb2f99b2d8b, photo-1517836357463-d25dfeac3438
   - Travel/Lifestyle: photo-1488646953014-85cb44e25828, photo-1503220317375-aaad61436b1b
   - Team/People: photo-1522071820081-009f0129c71c, photo-1600880292203-757bb62b4baf

   Example: https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=600&h=300&fit=crop&q=85&auto=format

2. **Unsplash Source with Keywords** (Good for specific topics):
   https://source.unsplash.com/featured/{width}x{height}/?{keywords}

   **Tips for better results:**
   - Use 2-3 specific keywords: office,professional,modern
   - Add context words: team,meeting NOT just "people"
   - Avoid single generic words

   Example: https://source.unsplash.com/featured/600x300/?startup,office,modern

3. **Picsum** (LAST RESORT - for truly generic placeholders):
   https://picsum.photos/seed/{descriptive-seed}/{width}/{height}
   Only use if no specific image type fits.

### Icons (Email-Safe PNG from Icons8)
- White icons: https://img.icons8.com/ios-filled/24/ffffff/{icon-name}.png
- Colored icons: https://img.icons8.com/fluency/48/{icon-name}.png
- Common names: checkmark, star, trophy, heart, shield, lightning-bolt, home, user, clock, gift

### Social Media Logos (ALWAYS use official or reliable sources)
- Twitter/X: https://img.icons8.com/ios-filled/24/ffffff/twitterx.png
- Facebook: https://img.icons8.com/ios-filled/24/ffffff/facebook-new.png
- Instagram: https://img.icons8.com/ios-filled/24/ffffff/instagram-new.png
- LinkedIn: https://img.icons8.com/ios-filled/24/ffffff/linkedin.png
- YouTube: https://img.icons8.com/ios-filled/24/ffffff/youtube-play.png

### CRITICAL: If user provides specific image URLs in their prompt, USE THEM EXACTLY!
If the user mentions URLs like "use this logo: https://..." or "hero image from https://...", use those exact URLs.

Always include: alt, width, height, style="display:block;border:0;"

## OUTPUT REQUIREMENTS
1. Generate COMPLETE, VALID HTML only (no markdown fences)
2. Start with <!DOCTYPE html>, end with </html>
3. Use triple braces {{{url}}} for custom URL variables
4. Use {{$hosted_preference_url}} for unsubscribe link in footer (SuprSend global - DOUBLE braces)
5. Include preheader text
6. Compatible with SuprSend's HTML code editor

## BLOCK STRUCTURE (REQUIRED)
Wrap each major section with HTML comment markers for editing:
<!-- BLOCK:header -->...<!-- /BLOCK:header -->
<!-- BLOCK:hero -->...<!-- /BLOCK:hero -->
<!-- BLOCK:content -->...<!-- /BLOCK:content -->
<!-- BLOCK:cta -->...<!-- /BLOCK:cta -->
<!-- BLOCK:footer -->...<!-- /BLOCK:footer -->
Include these markers around each logical section of the email.

## SELF-VALIDATION CHECKLIST (MUST PASS BEFORE OUTPUT)

Before outputting ANY HTML, mentally verify each of these. If ANY fails, FIX IT before outputting:

### 1. NO FORBIDDEN CSS
- [ ] No "display: flex" anywhere in the HTML
- [ ] No "display: grid" anywhere in the HTML
- [ ] No "position: absolute/relative/fixed"
- [ ] No "float: left/right"

### 2. ICON + TEXT ALIGNMENT
- [ ] Every icon uses a nested TABLE with TD having background-color (NOT a div with display:flex)
- [ ] Every icon cell has valign="top"
- [ ] Every text cell next to icon has valign="top"
- [ ] Icon cell has padding-right: 16px for gap
- [ ] Each feature item table has margin-bottom: 24px

### 3. SECTION SEPARATION
- [ ] Hero section has clear bottom boundary (padding-bottom or different background)
- [ ] Content section has different background OR clear padding-top (40px+)
- [ ] No text from one section flows into another section
- [ ] Each BLOCK marker wraps a visually distinct section

### 4. RESPONSIVE STRUCTURE
- [ ] Main table has class="email-container" with style="max-width: 600px; width: 100%;"
- [ ] All images have class="fluid" with style="max-width: 100%; height: auto;"
- [ ] Media queries in <style> block for mobile

### 5. TABLE STRUCTURE
- [ ] All layout tables have: role="presentation" cellspacing="0" cellpadding="0" border="0"
- [ ] All images have: alt, width, height, style="display: block;"

If you find ANY violation during this check, FIX IT in your output. Do not output broken HTML."""


# ============================================================================
# IMAGE PROMPT SYSTEM - EXACT COPY FROM TYPESCRIPT
# ============================================================================

IMAGE_PROMPT_SYSTEM = """You are an AI image prompt specialist. Analyze the HTML email and generate detailed prompts for each placeholder image.

Return a JSON array:
[
  {
    "id": "unique-identifier",
    "location": "where in email",
    "placeholder": "Lorem Picsum URL",
    "dimensions": { "width": 600, "height": 300 },
    "aiPrompt": "detailed, specific generation prompt",
    "style": "visual style description",
    "notes": "additional context"
  }
]

Make prompts SPECIFIC - avoid generic stock photo descriptions. Return ONLY JSON."""


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class DesignTokens(BaseModel):
    colorPalette: Optional[Dict[str, str]] = None
    typography: Optional[Dict[str, str]] = None
    layout: Optional[Dict[str, str]] = None
    aesthetic: Optional[Dict[str, Any]] = None
    components: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None


class GenerateRequest(BaseModel):
    apiKey: str
    openRouterApiKey: Optional[str] = None
    description: str
    emailType: str
    brandName: str
    primaryColor: Optional[str] = ""
    secondaryColor: Optional[str] = ""
    accentColor: Optional[str] = None
    tone: str = "professional"
    industry: Optional[str] = None
    designTokens: Optional[DesignTokens] = None
    generationMode: str = "fast"  # 'fast' or 'tasty'
    modelProvider: str = "anthropic"  # 'anthropic' or 'openrouter'
    openRouterModel: str = "google/gemini-3-pro-preview"


class GenerateResponse(BaseModel):
    html: str
    variables: List[str]
    imagePrompts: Optional[List[Dict[str, Any]]] = None
    validation: Optional[Dict[str, Any]] = None


# ============================================================================
# HELPER FUNCTIONS - EXACT LOGIC FROM TYPESCRIPT
# ============================================================================

async def call_openrouter(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 8192
) -> str:
    """Call OpenRouter API - same logic as TypeScript callOpenRouter()"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Email Forge",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        )
        
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="OpenRouter API key is invalid or expired")
        if response.status_code == 402:
            raise HTTPException(status_code=402, detail="OpenRouter account has insufficient credits")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="OpenRouter rate limit exceeded")
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            raise HTTPException(
                status_code=response.status_code,
                detail=error_data.get("error", {}).get("message", f"OpenRouter API error ({response.status_code})")
            )
        
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def build_design_reference_section(tokens: DesignTokens) -> str:
    """Build design reference section - same logic as TypeScript buildDesignReferenceSection()"""
    sections = []
    
    sections.append("""## 🎯 DESIGN REFERENCE - RECREATE THIS DESIGN (FROM UPLOADED IMAGE)

**⚠️ CRITICAL REQUIREMENT: You are NOT just "inspired by" this design - you MUST RECREATE it as closely as possible.**

The user has uploaded a reference design image. Your job is to:
1. **REPLICATE the exact layout structure** - same sections in same order
2. **COPY the visual hierarchy** - if they have a big hero, you have a big hero
3. **MATCH the spacing and proportions** - dense sections stay dense, airy stays airy
4. **USE their exact colors** - don't pick your own colors
5. **FOLLOW their component choices** - if they have icons in circles, you have icons in circles

Think of this as a design handoff from a designer - your goal is pixel-perfect recreation within email constraints.""")

    if tokens.summary:
        sections.append(f"""
### 📋 Design Analysis
{tokens.summary}

**Your email MUST visually match this description.**""")

    if tokens.colorPalette:
        cp = tokens.colorPalette
        sections.append(f"""
### 🎨 Color Palette (USE THESE EXACT HEX CODES - DO NOT SUBSTITUTE)
| Role | Color |
|------|-------|
| Primary | {cp.get('primary', '#000000')} |
| Secondary | {cp.get('secondary', '#666666')} |
| Accent/CTA | {cp.get('accent', '#007AFF')} |
| Background | {cp.get('background', '#FFFFFF')} |
| Text | {cp.get('text', '#000000')} |
| Muted Text | {cp.get('mutedText', '#666666')} |

**⚠️ Do NOT use any colors not listed above. Do NOT default to generic blue (#007AFF) if accent is specified.**""")

    if tokens.typography:
        t = tokens.typography
        size_contrast_text = "BIG headlines, smaller body" if t.get('sizeContrast') == 'high' else "subtle size differences" if t.get('sizeContrast') == 'low' else "clear hierarchy"
        sections.append(f"""
### 📝 Typography (MATCH EXACTLY)
- **Headline Style**: {t.get('headlineStyle', 'bold sans-serif')} - replicate this exact style
- **Body Style**: {t.get('bodyStyle', 'clean sans-serif')} - match the reading feel
- **Headline Weight**: {t.get('headlineWeight', 'bold')} - use this weight
- **Size Contrast**: {t.get('sizeContrast', 'medium')} - {size_contrast_text}""")

    if tokens.layout:
        layout = tokens.layout
        structure = layout.get('structure', 'single-column')
        structure_text = "create card sections with borders/shadows" if structure == 'card-grid' else "use table columns" if structure == 'multi-column' else "stack sections vertically"
        alignment = layout.get('alignment', 'left')
        alignment_text = "CENTER all content" if alignment == 'center' else "LEFT align content"
        density = layout.get('density', 'balanced')
        density_text = "lots of whitespace, airy feel" if density == 'spacious' else "tight spacing, dense information" if density == 'compact' else "balanced padding"
        hero_style = layout.get('heroStyle', 'text-only')
        hero_text = "MUST have full-width hero image" if hero_style == 'full-bleed-image' else "MUST have image + text side by side" if hero_style == 'split-hero' else "MUST have gradient background header" if hero_style == 'gradient-banner' else "text-focused hero section"
        
        sections.append(f"""
### 📐 Layout Structure (REPLICATE THIS EXACT PATTERN)
- **Structure**: {structure} {structure_text}
- **Alignment**: {alignment} {alignment_text}
- **Density**: {density} {density_text}
- **Hero Style**: {hero_style} {hero_text}

**⚠️ The layout pattern is the skeleton of the design - you MUST follow it exactly.**""")

    if tokens.aesthetic:
        a = tokens.aesthetic
        direction = a.get('direction', 'modern')
        direction_text = "very clean, lots of white space, subtle" if direction == 'minimalist' else "strong colors, big elements, confident" if direction == 'bold' else "fun, rounded shapes, friendly colors" if direction == 'playful' else "clean and contemporary"
        mood = a.get('mood', 'professional')
        distinctive = a.get('distinctiveElements', [])
        
        sections.append(f"""
### ✨ Visual Aesthetic (CAPTURE THIS EXACT MOOD)
- **Direction**: {direction} - {direction_text}
- **Mood**: {mood} - the email should FEEL {mood}
- **Distinctive Elements**: {', '.join(distinctive) if distinctive else 'none'} - {'INCLUDE THESE ELEMENTS' if distinctive else ''}""")

    if tokens.components:
        c = tokens.components
        sections.append(f"""
### 🧩 Component Checklist (MANDATORY)
| Component | Required | How to Implement |
|-----------|----------|------------------|
| Hero Image | {'✅ YES - MUST INCLUDE' if c.get('hasHeroImage') else '❌ NO'} | {'Full-width image in hero section' if c.get('hasHeroImage') else 'Text-only hero'} |
| Feature Icons | {'✅ YES - MUST INCLUDE' if c.get('hasFeatureIcons') else '❌ NO'} | {'Use Icons8 PNGs in colored circles' if c.get('hasFeatureIcons') else 'No icons needed'} |
| Social Links | {'✅ YES - MUST INCLUDE' if c.get('hasSocialLinks') else '❌ NO'} | {'Footer social icons' if c.get('hasSocialLinks') else 'Skip social section'} |
| CTA Button | ✅ ALWAYS | Style: {c.get('ctaStyle', 'rounded')} corners |
| Section Dividers | {'✅ YES' if c.get('dividerStyle', 'none') != 'none' else '❌ NO'} | {'Use <hr> or border-bottom' if c.get('dividerStyle') == 'line' else 'Use padding/margins' if c.get('dividerStyle') == 'space' else 'No dividers'} |""")

    sections.append("""
---
## 🚨 DESIGN RECREATION CHECKLIST (Verify before outputting)
Before generating, mentally check:
- [ ] Does my layout match the reference's section order?
- [ ] Am I using the exact colors from the palette above?
- [ ] Does my hero section match their hero style?
- [ ] If they have icons, do I have icons in similar style?
- [ ] Is my spacing/density similar to theirs?
- [ ] Would someone looking at both see them as the "same design"?

**The generated email should be a FAITHFUL RECREATION that could pass as part of the same campaign as the reference image.**""")

    return "\n".join(sections)


def build_generation_prompt(
    description: str,
    email_type: str,
    brand_name: str,
    primary_color: str,
    secondary_color: str,
    accent_color: Optional[str],
    tone: str,
    industry: Optional[str],
    design_tokens: Optional[DesignTokens],
    mode: str
) -> str:
    """Build generation prompt - same logic as TypeScript buildGenerationPrompt()"""
    
    # Email type guidance with design direction
    type_guidance = {
        "marketing": """Focus on engagement and conversion.
    DESIGN: Bold hero section with dramatic headline (40px+), full-width brand-colored background, ONE unmissable CTA button.
    Use aspirational imagery. Create urgency through visual hierarchy, not just copy.""",
        "transactional": """Focus on clarity and trust.
    DESIGN: Clean, structured layout. Primary color in header only. White/light content area for readability.
    Information hierarchy through typography size (order number BIG, details smaller). Subtle, professional.""",
        "notification": """Focus on urgency and action.
    DESIGN: Compact, punchy layout. Bold primary-colored banner at top. Get to the point immediately.
    Single prominent CTA. No fluff imagery - functional design.""",
        "newsletter": """Focus on content organization and scannability.
    DESIGN: Clear section breaks with alternating backgrounds (brand color tints).
    Strong headlines for each section. Card-style content blocks. Multiple entry points but clear hierarchy.""",
    }

    # Tone-specific design guidance
    tone_design_guidance = {
        "professional": """DESIGN DIRECTION: Clean, structured, authoritative.
    - Typography: Sans-serif (Montserrat/Inter), generous letter-spacing
    - Colors: Deep, muted brand colors - no bright neons
    - Layout: Structured grid, perfectly aligned elements
    - Imagery: Professional photography, no illustrations
    - Spacing: Generous, airy, premium feel""",
        "friendly": """DESIGN DIRECTION: Warm, approachable, conversational.
    - Typography: Rounded sans-serif (Poppins/DM Sans), relaxed sizes
    - Colors: Warm tones, approachable palette, soft gradients OK
    - Layout: Relaxed alignment, comfortable spacing
    - Imagery: Lifestyle photos, people smiling, relatable scenes
    - Spacing: Comfortable, not too tight or too sparse""",
        "luxurious": """DESIGN DIRECTION: Elegant, sophisticated, premium.
    - Typography: Serif headlines (Playfair Display), refined spacing, thin weights
    - Colors: Black, gold, deep jewel tones (emerald, burgundy), minimal palette
    - Layout: Maximum white space, editorial quality, asymmetric balance
    - Imagery: Aspirational, high-end photography, artistic composition
    - Spacing: VERY generous - luxury = breathing room""",
        "playful": """DESIGN DIRECTION: Fun, energetic, creative.
    - Typography: Bold, varied sizes, dynamic weights (DM Sans bold)
    - Colors: Vibrant, bold combinations, high saturation
    - Layout: Dynamic, unexpected elements, slight asymmetry OK
    - Imagery: Illustrated style OK, bright photography, action shots
    - Spacing: Varied rhythm, some sections tight, some open""",
        "minimal": """DESIGN DIRECTION: Clean, essential, focused.
    - Typography: Simple sans-serif, lots of space between lines
    - Colors: Monochromatic or strict two-color palette
    - Layout: Maximum white space, essential elements only
    - Imagery: Minimal or none - let typography do the work
    - Spacing: EXTREME white space - emptiness is intentional""",
        "bold": """DESIGN DIRECTION: Striking, confident, attention-grabbing.
    - Typography: Extra bold headlines (700+), strong contrast, BIG sizes (48px+)
    - Colors: High contrast combinations, bold brand primary everywhere
    - Layout: Full-width color blocks, dramatic sections, strong visual weight
    - Imagery: Impactful, dramatic photography, strong compositions
    - Spacing: Strategic - tight where impactful, generous for drama""",
    }

    tone_guidance = tone_design_guidance.get(tone, tone_design_guidance["professional"])

    # Build design reference section if design tokens are provided
    design_reference_section = ""
    if design_tokens:
        design_reference_section = build_design_reference_section(design_tokens)

    # Build color guidance
    design_colors = design_tokens.colorPalette if design_tokens else None
    has_colors = primary_color or secondary_color or accent_color or design_colors
    
    if has_colors:
        color_section = f"""## Brand Colors (User Specified)
{f'- Primary Color: {primary_color} (USE BOLDLY - backgrounds, headlines, not just accents)' if primary_color else ''}
{f'- Secondary Color: {secondary_color} (for section backgrounds, dividers)' if secondary_color else ''}
{f'- Accent Color: {accent_color} (ONLY for CTA buttons - make them pop)' if accent_color else ''}"""
    else:
        color_section = f"""## Brand Colors (AI CHOOSE)
No specific colors provided. YOU MUST choose a distinctive, modern color palette that:
- Matches the "{tone}" tone perfectly
- Is appropriate for {industry or 'the'} industry
- AVOIDS generic blues (#1a73e8, #3b82f6) and purples (#6366f1, #8b5cf6)
- Creates strong visual identity
- Includes: primary (bold, for backgrounds/headlines), secondary (subtle, for sections), accent (CTA buttons only)
Be creative and intentional with your color choices!"""

    # Mode-specific image handling
    if mode == "fast":
        mode_guidance = """## IMAGE MODE: FAST (Minimal Images)
**IMPORTANT: Use images SPARINGLY in this version.**
- ONLY include images that are absolutely necessary and specific:
  - Brand logo (if user provided URL)
  - Social media icons (Twitter, Facebook, LinkedIn, etc.)
  - Simple icons for features (use Icons8 PNG URLs)
- NO hero images unless the user specifically provided one
- NO decorative images or stock photos
- NO placeholder images that would need replacement
- Focus on typography, color blocks, and clean design instead of images
- If you must show a product, use a simple colored box placeholder with text describing what goes there
- The email should look COMPLETE and professional without any images that need replacing"""
    else:
        mode_guidance = """## IMAGE MODE: TASTY (Rich Visuals) - CREATE A VISUALLY STUNNING EMAIL

**CRITICAL: This is TASTY mode - you MUST create a visually rich, magazine-quality email design.**

### 🚫 BANNED LAYOUTS (DO NOT USE)

**NEVER use the "icon-left, text-right" two-column pattern:**
```
❌ WRONG - Wastes space, looks dated:
| [icon] | Title here          |
|        | Description text... |
```

**INSTEAD, use these SPACE-EFFICIENT patterns:**

### ✅ APPROVED FEATURE SECTION LAYOUTS

**PATTERN 1: Full-Width Feature Cards (PREFERRED)**
Each feature gets its own full-width section with:
- Full-width feature image (600x250) at top
- Title below image (24px, bold)
- Description (16px)
- Optional CTA button

**PATTERN 2: Centered Icon Badge + Text Stack**
Icon centered above text, no side-by-side

**PATTERN 3: Three-Column Icon Grid (for 3+ small features)**
Icons in a row, text below each

**PATTERN 4: Bullet List with Checkmarks (Simple Features)**
For simple feature lists, use text checkmarks or colored bullets

### IMAGE REQUIREMENTS (EVERY FEATURE NEEDS AN IMAGE)

**CRITICAL: In Tasty mode, each major feature MUST have its own image.**

**Minimum image requirements:**
- 1 hero image (600x400)
- 1 image per feature section (600x250 or 600x300)
- Aim for 3-5 total images in the email

**Use Unsplash for high-quality photos:**
https://images.unsplash.com/photo-{id}?w=600&h=300&fit=crop&q=85&auto=format

**For EVERY placeholder image, add AI generation prompt:**
```html
<!-- IMAGE_PROMPT: id="feature-1" dimensions="600x300" prompt="Modern dashboard interface showing analytics charts and metrics, clean UI design, light theme, professional" -->
<img src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&h=300&fit=crop&q=85" width="600" height="300" alt="Dashboard" style="display: block; width: 100%;">
```

### OUTPUT REQUIREMENTS
- Email MUST look like a professionally designed marketing email
- NOT a plain text email with minimal styling
- Include IMAGE_PROMPT comments for ALL placeholder images
- Every image needs: id, dimensions, detailed prompt for AI generation"""

    return f"""Generate a SuprSend-compatible HTML email template:

## Purpose
{description}

## Email Type: {email_type.upper()}
{type_guidance.get(email_type, '')}

## Brand
- Name: {brand_name}
- Tone: {tone}
{f'- Industry: {industry}' if industry else ''}

{color_section}
{f'{design_reference_section}' if design_reference_section else ''}
{mode_guidance}

## TONE-SPECIFIC DESIGN (FOLLOW CLOSELY)
{tone_guidance}

## SuprSend Requirements
1. Complete, production-ready HTML
2. Table-based layout (600px max)
3. MSO conditionals for multi-column
4. Use {{{{variables}}}} for text, {{{{{{urls}}}}}} for custom links (triple braces)
5. Use {{{{$hosted_preference_url}}}} for unsubscribe link (SuprSend global - DOUBLE braces)
6. Lorem Picsum placeholders with descriptive seeds
7. Include preheader text
8. WRAP EACH SECTION with block markers: <!-- BLOCK:type -->...<!-- /BLOCK:type -->

## Block Markers (REQUIRED)
Use these comment markers around each section:
- <!-- BLOCK:header --> for logo/brand header
- <!-- BLOCK:hero --> for hero image/headline
- <!-- BLOCK:content --> for main content
- <!-- BLOCK:cta --> for call-to-action buttons
- <!-- BLOCK:features --> for feature lists (if applicable)
- <!-- BLOCK:footer --> for footer with unsubscribe

Generate the HTML now. Remember: Custom URLs use triple braces {{{{{{url}}}}}}, but unsubscribe uses {{{{$hosted_preference_url}}}}!"""


def clean_html_output(html: str) -> str:
    """Clean HTML output - same logic as TypeScript cleanHtmlOutput()"""
    # Remove markdown code fences
    html = re.sub(r'^```html\s*\n?', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\n?```\s*$', '', html, flags=re.IGNORECASE)
    html = re.sub(r'^```\s*\n?', '', html, flags=re.IGNORECASE)
    
    # Find DOCTYPE and trim before it
    doctype_index = html.find('<!DOCTYPE')
    if doctype_index > 0:
        html = html[doctype_index:]
    
    # Find closing </html> and trim after it
    html_end_index = html.rfind('</html>')
    if html_end_index != -1:
        html = html[:html_end_index + 7]
    
    return html.strip()


def extract_variables(html: str) -> List[str]:
    """Extract variables from HTML - same logic as TypeScript extractVariables()"""
    variables = set()
    
    # Triple braces (URLs)
    triple_pattern = re.compile(r'\{\{\{([^}]+)\}\}\}')
    for match in triple_pattern.finditer(html):
        var_name = clean_var_name(match.group(1))
        if var_name:
            variables.add(var_name)
    
    # Double braces
    double_pattern = re.compile(r'\{\{([^{}]+)\}\}')
    for match in double_pattern.finditer(html):
        var_name = clean_var_name(match.group(1))
        if var_name:
            variables.add(var_name)
    
    return sorted(list(variables))


def clean_var_name(raw: str) -> Optional[str]:
    """Clean variable name - same logic as TypeScript cleanVarName()"""
    var_name = raw.strip()
    
    # Skip control structures
    if var_name.startswith('#') or var_name.startswith('/') or var_name == 'else':
        return None
    
    # Handle helpers like "default varName 'fallback'"
    if ' ' in var_name:
        parts = var_name.split()
        if len(parts) >= 2:
            var_name = parts[1].replace('"', '').replace("'", '')
    
    # Skip reserved words
    if var_name in ['this', 'true', 'false', 'null', 'undefined']:
        return None
    
    # Skip SuprSend global variables (they start with $)
    if var_name.startswith('$'):
        return None
    
    return var_name.replace('"', '').replace("'", '') or None


def validate_email(html: str) -> Dict[str, Any]:
    """Validate email HTML - same logic as TypeScript validateEmail()"""
    warnings = []
    errors = []
    total_size = len(html.encode('utf-8'))
    
    if total_size > 102 * 1024:
        warnings.append(f"Size ({total_size // 1024}KB) exceeds Gmail limit (102KB)")
    
    # CRITICAL ERRORS
    if re.search(r'display\s*:\s*flex', html, re.IGNORECASE):
        errors.append("CRITICAL: display:flex detected - breaks in email clients. Use table-based layout.")
    
    if re.search(r'display\s*:\s*grid', html, re.IGNORECASE):
        errors.append("CRITICAL: display:grid detected - breaks in email clients. Use table-based layout.")
    
    if re.search(r'position\s*:\s*(absolute|relative|fixed)', html, re.IGNORECASE):
        errors.append("CRITICAL: CSS position detected - not supported in email clients.")
    
    if re.search(r'float\s*:\s*(left|right)', html, re.IGNORECASE):
        errors.append("CRITICAL: CSS float detected - breaks in Outlook.")
    
    if not re.search(r'<table', html, re.IGNORECASE):
        errors.append("No table layout detected - email will break in Outlook")
    
    # Check for responsive classes
    if 'email-container' not in html:
        warnings.append('Missing class="email-container" - email may not be responsive')
    
    # Check for media queries
    if not re.search(r'@media', html, re.IGNORECASE):
        warnings.append('No media queries found - email may not be mobile responsive')
    
    # Check images have required attributes
    images = re.findall(r'<img[^>]*>', html, re.IGNORECASE)
    for i, img in enumerate(images):
        if not re.search(r'alt=', img, re.IGNORECASE):
            warnings.append(f'Image {i + 1} missing alt attribute')
        if not re.search(r'style=["\'][^"\']*display\s*:\s*block', img, re.IGNORECASE):
            warnings.append(f'Image {i + 1} missing display:block style')
    
    return {
        "isValid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }


# ============================================================================
# API ENDPOINT
# ============================================================================

@router.post("/generate", response_model=GenerateResponse)
async def generate_email(request: GenerateRequest):
    """
    Generate email HTML template.
    Migrated from: frontend/app/api/generate/route.ts
    """
    try:
        # Build the user prompt
        user_prompt = build_generation_prompt(
            description=request.description,
            email_type=request.emailType,
            brand_name=request.brandName,
            primary_color=request.primaryColor or "",
            secondary_color=request.secondaryColor or "",
            accent_color=request.accentColor,
            tone=request.tone,
            industry=request.industry,
            design_tokens=request.designTokens,
            mode=request.generationMode,
        )
        
        html_content = ""
        
        # Generate HTML based on provider
        if request.modelProvider == "openrouter":
            if not request.openRouterApiKey:
                raise HTTPException(status_code=400, detail="OpenRouter API key is required")
            
            html_content = await call_openrouter(
                api_key=request.openRouterApiKey,
                model=request.openRouterModel,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=8192,
            )
        else:
            # Use Anthropic
            client = Anthropic(api_key=request.apiKey)
            
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            
            if response.content and response.content[0].type == "text":
                html_content = response.content[0].text
        
        # Clean and validate HTML
        html_content = clean_html_output(html_content)
        variables = extract_variables(html_content)
        validation = validate_email(html_content)
        
        # Generate image prompts for tasty mode
        image_prompts = None
        if request.generationMode == "tasty":
            try:
                client = Anthropic(api_key=request.apiKey)
                
                image_response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=IMAGE_PROMPT_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": f"Analyze this email HTML and generate image prompts:\n\n{html_content}"
                    }],
                )
                
                if image_response.content and image_response.content[0].type == "text":
                    import json
                    try:
                        prompt_text = image_response.content[0].text
                        # Clean markdown fences
                        prompt_text = re.sub(r'^```json\s*\n?', '', prompt_text, flags=re.IGNORECASE)
                        prompt_text = re.sub(r'\n?```\s*$', '', prompt_text, flags=re.IGNORECASE)
                        image_prompts = json.loads(prompt_text)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                # Image prompt generation is optional
                pass
        
        return GenerateResponse(
            html=html_content,
            variables=variables,
            imagePrompts=image_prompts,
            validation=validation,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid API key")
        raise HTTPException(status_code=500, detail=f"Generation failed: {error_msg}")
