"""Read the brand's design-system tokens so video graphics match everything else.

`brand/design-system/tokens/*.css` is pulled from the **The Ninth Room Design
System** project on claude.ai/design (project id
`4b8bb4a4-b234-45ed-aa84-b35ce761648b`). Keeping the video cards on those same
tokens is the whole point of the sync: change yellow once in the design system,
re-pull, and the next render uses it.

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
# These are the Cyanotype four: base, the one thing to look at, verified, type.
FALLBACK = {
    "navy-900": "#0B2340",
    "navy-800": "#173456",
    "chalk": "#EAF4FF",
    "yellow": "#FFE04D",
    "cyan": "#38E1F0",
    "slate-300": "#8FB3D6",
    "slate-400": "#7C9BBC",
    "slate-500": "#5F81A6",
    "font-display": "'Bricolage Grotesque',system-ui,sans-serif",
    "font-serif": "'Newsreader',Georgia,serif",
    "font-ui": "'Manrope',system-ui,sans-serif",
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
    """The handful of literals the card and caption renderers need.

    Cyanotype names first. The four legacy keys (`amber`, `cream`, `navy_deep`,
    `font_sans`) are kept as ALIASES onto their Ninth Room equivalents so any
    caller written against the old Curated Curiosities palette still gets a
    correct, on-brand colour instead of silently falling back to the retired
    navy/amber/cream.

    What breaks if this is wrong: a renderer paints the old brand and the drift
    is invisible in one frame but obvious across a channel.
    """
    t = load(dirpath)
    navy = resolve(t, "navy-900", FALLBACK["navy-900"])
    yellow = resolve(t, "yellow", FALLBACK["yellow"])
    chalk = resolve(t, "chalk", FALLBACK["chalk"])
    display = resolve(t, "font-display", FALLBACK["font-display"])
    return {
        # Cyanotype
        "navy": navy,
        "navy_800": resolve(t, "navy-800", FALLBACK["navy-800"]),
        "chalk": chalk,
        "yellow": yellow,
        "cyan": resolve(t, "cyan", FALLBACK["cyan"]),
        "slate": resolve(t, "slate-400", FALLBACK["slate-400"]),
        "slate_support": resolve(t, "slate-300", FALLBACK["slate-300"]),
        "font_display": display,
        "font_serif": resolve(t, "font-serif", FALLBACK["font-serif"]),
        "font_ui": resolve(t, "font-ui", FALLBACK["font-ui"]),
        "ls_eyebrow": resolve(t, "track-eyebrow", ".24em"),
        "lh_tight": resolve(t, "leading-display", "1.04"),
        "weight_display": resolve(t, "weight-display", "800"),
        # legacy aliases — see docstring
        "navy_deep": navy,
        "amber": yellow,
        "amber_light": yellow,
        "cream": chalk,
        "font_sans": display,
    }


def hex_to_rgb(value: str) -> "tuple":
    """'#E8A33D' -> (232, 163, 61). Non-hex values raise ValueError."""
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise ValueError("not a hex color: %r" % value)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
