"""
NOIR SIGNAL Theme for TraceCraft TUI.

A high-contrast, late-1930s detective terminal aesthetic.
Sparse. Confident. Menacingly calm.

Design Philosophy:
- Information first, drama second
- Dark canvas, surgical highlights
- Rhythm over density
- Every screen tells a story
"""

from __future__ import annotations

# =============================================================================
# COLOR PALETTE
# =============================================================================

# Base Colors
BACKGROUND = "#0B0E11"  # Near-black with blue undertone
SURFACE = "#12161C"  # Slight lift for panels/frames
TEXT_PRIMARY = "#E6E6E6"  # Warm white
TEXT_MUTED = "#8B949E"  # Metadata, timestamps, helper text

# Accent Colors (use sparingly)
ACCENT_AMBER = "#F5C542"  # Selection, focus, active states - "the streetlight"
DANGER_RED = "#C44536"  # Errors, destructive actions only
SUCCESS_GREEN = "#3FA796"  # Confirmation states, never celebratory
INFO_BLUE = "#4C83FF"  # External references or links (rare)

# Derived Colors
BORDER = "#2D333B"  # Subtle borders
BORDER_FOCUS = ACCENT_AMBER  # Focus state borders
SURFACE_HIGHLIGHT = "#1C2128"  # Hover/selection background

# =============================================================================
# SYMBOLS (ASCII/Unicode only - no emojis)
# =============================================================================

SYM_NAV = "›"  # Navigation indicator
SYM_BULLET = "•"  # Bullet points
SYM_SEPARATOR = "—"  # Short dash separator
SYM_CLOSE = "×"  # Close or cancel
SYM_CHECK = "+"  # Checkmark/success (not a real checkmark)
SYM_ERROR = "×"  # Error indicator
SYM_EXPAND = "+"  # Expandable
SYM_COLLAPSE = "-"  # Collapsible
SYM_SELECTED = ">"  # Selected item

# Step type indicators (Unicode symbols - visually distinct)
STEP_AGENT = "◆"  # Filled diamond - coordination/central
STEP_LLM = "◉"  # Circle with dot - thinking/brain
STEP_TOOL = "▶"  # Play arrow - action/execution
STEP_RETRIEVAL = "◀"  # Back arrow - fetching/pulling
STEP_MEMORY = "▬"  # Rectangle - storage
STEP_GUARDRAIL = "◇"  # Hollow diamond - protection
STEP_EVALUATION = "◈"  # Diamond with center - assessment
STEP_WORKFLOW = "▷"  # Hollow triangle - flow/process
STEP_ERROR = "✕"  # X mark - failure

# =============================================================================
# CSS VARIABLES (Textual format)
# =============================================================================

# Base CSS that should be included in all components
BASE_CSS = f"""
/* NOIR SIGNAL Theme Variables */
$background: {BACKGROUND};
$surface: {SURFACE};
$primary: {ACCENT_AMBER};
$primary-darken-1: #D4A836;
$primary-darken-2: #B38F2D;
$secondary: {TEXT_MUTED};
$text: {TEXT_PRIMARY};
$text-muted: {TEXT_MUTED};
$error: {DANGER_RED};
$success: {SUCCESS_GREEN};
$warning: {ACCENT_AMBER};
$accent: {ACCENT_AMBER};
$border: {BORDER};
$surface-highlight: {SURFACE_HIGHLIGHT};
"""

# =============================================================================
# COMMON CSS PATTERNS
# =============================================================================

PANEL_CSS = f"""
background: {SURFACE};
border: solid {BORDER};
"""

HEADER_CSS = f"""
text-style: bold;
color: {TEXT_PRIMARY};
"""

MUTED_TEXT_CSS = f"""
color: {TEXT_MUTED};
"""

FOCUS_CSS = f"""
border: solid {ACCENT_AMBER};
"""

# =============================================================================
# SEMANTIC TEXT STYLES (for Rich Text objects)
# =============================================================================

# These are inline style strings to use with Rich Text .append(text, style=XXX)
# This ensures consistency across all widgets without hardcoding colors

TEXT_STYLE_PRIMARY = f"#{TEXT_PRIMARY[1:]}"  # Remove # and re-add for consistency
TEXT_STYLE_MUTED = f"#{TEXT_MUTED[1:]}"
TEXT_STYLE_ACCENT = f"#{ACCENT_AMBER[1:]}"
TEXT_STYLE_DANGER = f"#{DANGER_RED[1:]}"
TEXT_STYLE_SUCCESS = f"#{SUCCESS_GREEN[1:]}"
TEXT_STYLE_INFO = f"#{INFO_BLUE[1:]}"

# Combined styles (style + modifier)
TEXT_STYLE_PRIMARY_BOLD = f"{TEXT_PRIMARY} bold"
TEXT_STYLE_MUTED_DIM = f"{TEXT_MUTED} dim"
TEXT_STYLE_ACCENT_DIM = f"{ACCENT_AMBER} dim"
TEXT_STYLE_DANGER_BOLD = f"{DANGER_RED} bold"
TEXT_STYLE_INFO_DIM = f"{INFO_BLUE} dim"

# Panel and border styles
PANEL_BORDER_DEFAULT = BORDER
PANEL_BORDER_FOCUS = ACCENT_AMBER
PANEL_BORDER_DANGER = DANGER_RED
PANEL_BORDER_INFO = INFO_BLUE
PANEL_BORDER_SUCCESS = SUCCESS_GREEN
PANEL_BACKGROUND = f"on {SURFACE}"

# =============================================================================
# COPY STYLE HELPERS
# =============================================================================


def format_status(message: str) -> str:
    """Format a status message in noir style. Short. Declarative."""
    return message.rstrip(".") + "."


def format_error(message: str) -> str:
    """Format an error message. No exclamation points."""
    return message.rstrip(".!") + "."


# =============================================================================
# WIDGET HELPER FUNCTIONS
# =============================================================================


def truncate_with_ellipsis(text: str, max_length: int = 40) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_duration(ms: float) -> str:
    """Format duration in human-readable form."""
    if ms < 1:
        return f"{ms * 1000:.0f}us"
    elif ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = int(ms / 60000)
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.1f}s"


def format_tokens(count: int) -> str:
    """Format token count."""
    if count >= 1000000:
        return f"{count / 1000000:.1f}M"
    elif count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)


# =============================================================================
# TEXTUAL THEME CSS
# =============================================================================

# Complete theme CSS for the main app
APP_THEME_CSS = f"""
/* ============================================
   NOIR SIGNAL - TraceCraft Theme
   ============================================ */

/* Global defaults */
Screen {{
    background: {BACKGROUND};
}}

/* Standard widget overrides */
Static {{
    color: {TEXT_PRIMARY};
}}

Label {{
    color: {TEXT_PRIMARY};
}}

Button {{
    background: {SURFACE};
    color: {TEXT_PRIMARY};
    border: solid {BORDER};
    text-style: bold;
}}

Button:hover {{
    background: {SURFACE_HIGHLIGHT};
    border: solid {ACCENT_AMBER};
}}

Button:focus {{
    background: {SURFACE_HIGHLIGHT};
    border: solid {ACCENT_AMBER};
    color: {ACCENT_AMBER};
}}

Button.-primary {{
    background: {ACCENT_AMBER};
    color: {BACKGROUND};
}}

Button.-primary:hover {{
    background: #D4A836;
}}

Input {{
    background: {SURFACE};
    color: {TEXT_PRIMARY};
    border: solid {BORDER};
}}

Input:focus {{
    border: solid {ACCENT_AMBER};
}}

Input > .input--placeholder {{
    color: {TEXT_MUTED};
}}

OptionList {{
    background: {SURFACE};
    border: solid {BORDER};
}}

OptionList:focus {{
    border: solid {ACCENT_AMBER};
}}

OptionList > .option-list--option {{
    color: {TEXT_PRIMARY};
}}

OptionList > .option-list--option-highlighted {{
    background: {SURFACE_HIGHLIGHT};
    color: {ACCENT_AMBER};
}}

Tree {{
    background: {SURFACE};
}}

Tree:focus {{
    border: solid {ACCENT_AMBER};
}}

Tree > .tree--cursor {{
    background: {SURFACE_HIGHLIGHT};
    color: {ACCENT_AMBER};
}}

Tree > .tree--highlight {{
    background: {SURFACE_HIGHLIGHT};
}}

Header {{
    background: {SURFACE};
    color: {TEXT_PRIMARY};
    text-style: bold;
}}

Footer {{
    background: {SURFACE};
    color: {TEXT_MUTED};
}}

Footer > .footer--key {{
    background: {BACKGROUND};
    color: {ACCENT_AMBER};
}}

Footer > .footer--description {{
    color: {TEXT_MUTED};
}}

/* Scrollbars */
Scrollbar {{
    background: {BACKGROUND};
}}

Scrollbar > .scrollbar--bar {{
    background: {BORDER};
}}

Scrollbar > .scrollbar--bar:hover {{
    background: {TEXT_MUTED};
}}

/* Notification toasts */
Toast {{
    background: {SURFACE};
    border: solid {BORDER};
    color: {TEXT_PRIMARY};
}}

Toast.-information {{
    border: solid {INFO_BLUE};
}}

Toast.-warning {{
    border: solid {ACCENT_AMBER};
}}

Toast.-error {{
    border: solid {DANGER_RED};
}}
"""
