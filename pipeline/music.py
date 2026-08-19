"""Score the video: a music bed per chapter, ducked under the narration.

Why this runs after Resolve rather than inside it: the scripting API exposes
no audio-track or gain control (`TimelineItem.SetProperty` is video transforms
only), so music is mixed onto the rendered master with ffmpeg — the same
reason `pipeline/audio.py` levels narration on the media.

How it sounds:
  * one track per chapter, so a chapter turn is heard as well as seen — the
    library's names map to the halls almost by themselves (Egyptology under
    King Tut)
  * each chapter's bed fades in and out at its own boundaries, so the seam
    lands on the cut rather than drifting across it
  * the whole bed is side-chain compressed against the narration: when Caleb
    speaks the music steps back automatically, and it swells again in the
    gaps. This is why a fixed low volume is the wrong tool — quiet enough to
    talk over is inaudible everywhere else.

What breaks if this is wrong: music buries the narration (threshold/ratio too
gentle), pumps audibly (release too short), or the bed runs past the end of
the video and the file gains silent tail.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .ingest import work_path, analysis_dir, IngestError

MUSIC_DIR = Path(__file__).resolve().parent.parent / "brand" / "design-system" / "Music copy"

# Bed level before ducking, and how hard speech pushes it down.
BED_DB = -19.0
DUCK = "threshold=0.045:ratio=7:attack=15:release=420:makeup=1"
FADE = 1.6          # seconds at each chapter boundary
MIN_MUSIC_SEC = 45  # anything shorter is a sound effect, not a bed

# Files that are neither music nor usable beds.
_SKIP = re.compile(r"ES_Voice|Swoosh|Riser|Whoosh", re.I)
_SFX = re.compile(r"Ambience|Water|Waterfall|Forest", re.I)

# Chapter title keywords -> track name keywords. First match wins; anything
# unmatched falls through to the remaining tracks in library order, so every
# chapter gets its own bed and no track repeats.
AFFINITY = [
    (r"egypt|tut", r"egyptology"),
    (r"butterfly|cockrell", r"five leaves|window"),
    (r"death|natural causes", r"hundred rooms|tearing"),
    (r"americas|dinosaur|maya|inka", r"northern skylight|stand"),
    (r"here|arrival", r"open up|lounge"),
]


def library(dirpath: "Path | None" = None) -> "list[dict]":
    """Every usable music bed in the library, longest first."""
    d = Path(dirpath) if dirpath else MUSIC_DIR
    if not d.is_dir():
        raise IngestError("no music library at %s" % d)
    out = []
    for p in sorted(d.rglob("*.mp3")):
        if _SKIP.search(p.name):
            continue
        dur = _duration(p)
        if dur < MIN_MUSIC_SEC:
            continue
        out.append({"path": str(p), "name": p.stem,
                    "artist": p.parent.parent.name, "duration": dur,
                    "sfx": bool(_SFX.search(p.name))})
    return sorted(out, key=lambda t: (t["sfx"], -t["duration"]))


def _duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0


def assign(chapters: "list[dict]", tracks: "list[dict]") -> "list[dict]":
    """Give each chapter a track: affinity first, then longest unused."""
    beds, used = [], set()
    for ch in chapters:
        title = ch.get("title", "").lower()
        pick = None
        for title_pat, track_pat in AFFINITY:
            if re.search(title_pat, title):
                pick = next((t for t in tracks
                             if re.search(track_pat, t["name"], re.I)
                             and t["path"] not in used and not t["sfx"]), None)
                if pick:
                    break
        if pick is None:
            pick = next((t for t in tracks if t["path"] not in used and not t["sfx"]), None)
        if pick is None:                     # library smaller than the chapter count
            pick = tracks[len(beds) % len(tracks)]
        used.add(pick["path"])
        beds.append(dict(ch, track=pick))
    return beds


def build_bed(beds: "list[dict]", total: float, out_wav: Path, log=print) -> Path:
    """Render the chapter beds into one continuous music track."""
    inputs, filters, labels = [], [], []
    for i, b in enumerate(beds):
        dur = max(b["dur"], 1.0)
        # Start a little into the track: intros are often sparse.
        start = 6.0 if b["track"]["duration"] > dur + 12 else 0.0
        inputs += ["-ss", "%.3f" % start, "-t", "%.3f" % dur, "-i", b["track"]["path"]]
        filters.append(
            "[%d:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            "afade=t=in:st=0:d=%.2f,afade=t=out:st=%.3f:d=%.2f[m%d]"
            % (i, min(FADE, dur / 3), max(dur - FADE, 0.1), min(FADE, dur / 3), i))
        labels.append("[m%d]" % i)
        log("[music] %-30s %-22s %4.0fs  %s"
            % (b["title"][:30], b["track"]["name"][:22], dur, b["track"]["artist"]))
    filters.append("%sconcat=n=%d:v=0:a=1[bed]" % ("".join(labels), len(beds)))
    cmd = (["ffmpeg", "-y", "-loglevel", "error"] + inputs +
           ["-filter_complex", ";".join(filters), "-map", "[bed]",
            "-t", "%.3f" % total, "-c:a", "pcm_s16le", str(out_wav)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("music bed failed: %s" % proc.stderr[-400:])
    return out_wav


def score(slug: str, video: Path, log=print) -> Path:
    """Mix a ducked music bed under a rendered video. Returns the new file."""
    tl = json.loads((analysis_dir(slug) / "timeline_map.json").read_text())
    plan = json.loads((work_path(slug) / "edit_plan.json").read_text())
    beat = {b["id"]: b for b in tl["beats"]}

    chapters = []
    for ch in plan.get("chapters", []):
        bs = [b for b in plan["beats"] if b.get("chapter_id") == ch["id"]]
        if not bs:
            continue
        start = min(beat[b["id"]]["record_s"] for b in bs)
        end = max(beat[b["id"]]["record_e"] for b in bs)
        chapters.append({"id": ch["id"], "title": ch["title"],
                         "start": start, "dur": end - start})
    if not chapters:
        chapters = [{"id": "ALL", "title": slug, "start": 0.0, "dur": tl["duration"]}]

    beds = assign(chapters, library())
    work = work_path(slug)
    bed_wav = build_bed(beds, tl["duration"], work / "music_bed.wav", log=log)

    out = video.with_name(video.stem + "_scored.mp4")
    # asplit gives the narration twice: once to hear, once as the side-chain
    # key that tells the compressor when to duck.
    fc = ("[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
          "asplit=2[voice][key];"
          "[1:a]volume=%.1fdB[bedq];"
          "[bedq][key]sidechaincompress=%s[ducked];"
          "[voice][ducked]amix=inputs=2:normalize=0:duration=first[mix]"
          % (BED_DB, DUCK))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(bed_wav),
           "-filter_complex", fc, "-map", "0:v", "-map", "[mix]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("music mix failed: %s" % proc.stderr[-400:])

    credits = [{"chapter": b["title"], "track": b["track"]["name"],
                "artist": b["track"]["artist"]} for b in beds]
    (work / "music_credits.json").write_text(json.dumps(credits, indent=2))
    log("[music] scored -> %s" % out.name)
    return out
