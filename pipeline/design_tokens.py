"""Read the brand's design-system tokens so video graphics match everything else.

`brand/design-system/tokens/*.css` is pulled from the "Curated Curiosities
Design System" project on claude.ai/design (Claude Design). Keeping the video
cards on those same tokens is the whole point of the sync: change amber once
in the design system, re-pull, and the next render uses it.

This parses plain CSS custom properties — no CSS engine, no dependency. Values
that reference other variables (`var(--amber-500)`) are resolved one level at
a time until they bottom out in a literal.

What breaks if this is wrong: cards drift off-brand silently (a slightly
different navy is hard to spot in one frame and obvious across a channel), or
a missing token file makes the renderer fall back to the built-in constants.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKENS_DIR = PROJECT_ROOT / "brand" / "design-system" / "tokens"

# Used when the design-system files are absent, so rendering never hard-fails.
FALLBACK = {
    "navy-900": "#0E1B2C",
    "amber-500": "#E8A33D",
    "cream-50": "#F4EFE6",
    "slate-500": "#6B7C93",
}

_VAR_RE = re.compile(r"--([A-Za-z0-9-]+)\s*:\s*([^;]+);")
_REF_RE = re.compile(r"var\(\s*--([A-Za-z0-9-]+)\s*\)")


def load(dirpath: "Path | None" = None) -> "dict[str, str]":
    """All custom properties from every .css file in the tokens dir."""
    d = Path(dirpath) if dirpath else TOKENS_DIR
    tokens: "dict[str, str]" = {}
    if d.is_dir():
        for css in sorted(d.glob("*.css")):
            text = css.read_text()
            # strip comments so `/* @kind color */` never lands in a value
            text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            for name, value in _VAR_RE.findall(text):
                tokens[name] = value.strip()
    if not tokens:
        tokens = dict(FALLBACK)
    return tokens


def resolve(tokens: "dict[str, str]", name: str, default: str = "") -> str:
    """Resolve a token to a literal, following var() references."""
    seen = set()
    value = tokens.get(name, default)
    while True:
        m = _REF_RE.search(value)
        if not m:
            return value.strip()
        ref = m.group(1)
        if ref in seen or ref not in tokens:
            return value.strip()
        seen.add(ref)
        value = value.replace(m.group(0), tokens[ref])


def palette(dirpath: "Path | None" = None) -> "dict[str, str]":
    """The handful of literals the card and caption renderers need."""
    t = load(dirpath)
    return {
        "navy": resolve(t, "navy-900", FALLBACK["navy-900"]),
        "navy_deep": resolve(t, "navy-950", FALLBACK["navy-900"]),
        "amber": resolve(t, "amber-500", FALLBACK["amber-500"]),
        "amber_light": resolve(t, "amber-400", FALLBACK["amber-500"]),
        "cream": resolve(t, "cream-50", FALLBACK["cream-50"]),
        "slate": resolve(t, "slate-500", FALLBACK["slate-500"]),
        "font_display": resolve(t, "font-display", "Didot, serif"),
        "font_sans": resolve(t, "font-sans", '"Avenir Next", sans-serif'),
        "ls_eyebrow": resolve(t, "ls-eyebrow", "0.2em"),
        "lh_tight": resolve(t, "lh-tight", "1.06"),
        "weight_display": resolve(t, "weight-display-bold", "700"),
    }


def hex_to_rgb(value: str) -> "tuple":
    """'#E8A33D' -> (232, 163, 61). Non-hex values raise ValueError."""
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise ValueError("not a hex color: %r" % value)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
