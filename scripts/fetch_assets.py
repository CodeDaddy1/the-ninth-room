#!/usr/bin/env python3
"""
fetch_assets.py — Curated Curiosities asset fetcher.

Reads a shot list produced by the asset-scout agent and auto-downloads candidate
stock clips for every "stock" shot into one folder per shot, then writes a
manifest (sources, licenses, dimensions) for the editor.

This automates the time-sink — manual searching — and leaves the creative pick
to a human. AI-generated shots are listed in the manifest as TODOs with their
prompt, ready to paste into your video-gen tool of choice.

Setup:
  pip install requests
  export PEXELS_API_KEY=...     # free: https://www.pexels.com/api/
  export PIXABAY_API_KEY=...    # free: https://pixabay.com/api/docs/  (optional)

Usage:
  python fetch_assets.py shot_list.json --out ./assets --per-shot 3
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import requests

PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "")

TIMEOUT = 30


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "shot"


def pexels_search(query: str, orientation: str, want: int):
    """Return a list of candidate dicts from the Pexels video API."""
    if not PEXELS_KEY:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_KEY},
            params={
                "query": query,
                "orientation": orientation,
                "per_page": want,
                "size": "medium",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        out = []
        for v in r.json().get("videos", []):
            # pick the highest-res progressive .mp4 file
            files = sorted(
                v.get("video_files", []),
                key=lambda f: (f.get("width") or 0),
                reverse=True,
            )
            if not files:
                continue
            f = files[0]
            out.append({
                "provider": "pexels",
                "url": f["link"],
                "width": f.get("width"),
                "height": f.get("height"),
                "page": v.get("url"),
                "author": v.get("user", {}).get("name", ""),
                "license": "Pexels License (commercial ok, no attribution required)",
            })
        return out
    except Exception as e:
        print(f"  ! pexels error for '{query}': {e}", file=sys.stderr)
        return []


def pixabay_search(query: str, want: int):
    """Return a list of candidate dicts from the Pixabay video API."""
    if not PIXABAY_KEY:
        return []
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": PIXABAY_KEY, "q": query, "per_page": max(3, want)},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        out = []
        for v in r.json().get("hits", []):
            streams = v.get("videos", {})
            best = streams.get("large") or streams.get("medium") or streams.get("small")
            if not best or not best.get("url"):
                continue
            out.append({
                "provider": "pixabay",
                "url": best["url"],
                "width": best.get("width"),
                "height": best.get("height"),
                "page": v.get("pageURL"),
                "author": v.get("user", ""),
                "license": "Pixabay License (commercial ok, no attribution required)",
            })
        return out
    except Exception as e:
        print(f"  ! pixabay error for '{query}': {e}", file=sys.stderr)
        return []


def download(url: str, dest: Path) -> bool:
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
        return True
    except Exception as e:
        print(f"  ! download failed {url}: {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shot_list", help="JSON file from the asset-scout agent")
    ap.add_argument("--out", default="./assets", help="output directory")
    ap.add_argument("--per-shot", type=int, default=3, help="candidates per shot")
    args = ap.parse_args()

    data = json.loads(Path(args.shot_list).read_text())
    out_root = Path(args.out) / slug(data.get("video_title", "video"))
    out_root.mkdir(parents=True, exist_ok=True)
    default_orient = data.get("default_orientation", "landscape")

    manifest_rows = []
    todo_aigen = []

    for shot in data.get("shots", []):
        sid = shot.get("shot_id", "S")
        stype = shot.get("source_type", "stock")
        print(f"\n[{sid}] {stype} — {shot.get('visual','')[:60]}")

        if shot.get("needs_rights_check"):
            print("  ⚠ flagged for human rights/license review")

        if stype != "stock":
            # Non-stock shots are passed through as actionable TODOs.
            todo_aigen.append(shot)
            manifest_rows.append({
                "shot_id": sid, "timecode": shot.get("timecode", ""),
                "source_type": stype, "status": "TODO",
                "instruction": shot.get("ai_prompt") or shot.get("visual", ""),
                "file": "", "provider": "", "license": "",
                "source_page": "", "needs_rights_check": shot.get("needs_rights_check", False),
            })
            continue

        shot_dir = out_root / f"{sid}_{slug(shot.get('visual','shot'))}"
        shot_dir.mkdir(parents=True, exist_ok=True)
        orient = shot.get("orientation", default_orient)

        candidates = []
        for q in shot.get("queries", []):
            candidates += pexels_search(q, orient, args.per_shot)
            if len(candidates) < args.per_shot:
                candidates += pixabay_search(q, args.per_shot)
            if len(candidates) >= args.per_shot:
                break

        if not candidates:
            print("  (no stock candidates — see fallback)")
            manifest_rows.append({
                "shot_id": sid, "timecode": shot.get("timecode", ""),
                "source_type": "stock", "status": "NO_RESULTS",
                "instruction": shot.get("fallback", ""), "file": "",
                "provider": "", "license": "", "source_page": "",
                "needs_rights_check": shot.get("needs_rights_check", False),
            })
            continue

        for i, c in enumerate(candidates[: args.per_shot], 1):
            fname = f"{sid}_cand{i}_{c['provider']}.mp4"
            dest = shot_dir / fname
            if download(c["url"], dest):
                print(f"  ✓ {fname}  ({c.get('width')}x{c.get('height')})")
                manifest_rows.append({
                    "shot_id": sid, "timecode": shot.get("timecode", ""),
                    "source_type": "stock", "status": "DOWNLOADED",
                    "instruction": shot.get("visual", ""),
                    "file": str(dest.relative_to(out_root)),
                    "provider": c["provider"], "license": c["license"],
                    "source_page": c.get("page", ""),
                    "needs_rights_check": shot.get("needs_rights_check", False),
                })

    # Write manifest
    man_path = out_root / "manifest.csv"
    with open(man_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "shot_id", "timecode", "source_type", "status", "instruction",
            "file", "provider", "license", "source_page", "needs_rights_check",
        ])
        w.writeheader()
        w.writerows(manifest_rows)

    print(f"\nDone. Assets in: {out_root}")
    print(f"Manifest: {man_path}")
    if todo_aigen:
        print(f"{len(todo_aigen)} non-stock shot(s) need generating/creating — "
              f"see rows marked TODO in the manifest.")


if __name__ == "__main__":
    main()
