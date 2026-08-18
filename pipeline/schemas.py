"""Hand-rolled validators for the pipeline's JSON artifacts.

Same pattern as v1: each validate_*(data) returns a list of error strings —
empty list means valid. Stdlib only, no jsonschema dependency. Agents and
Python stages both run these before trusting a file; a failed validation is a
stop-the-line error, never a warning.

What breaks if this is wrong: a malformed artifact flows downstream and the
failure surfaces far from its cause (e.g. a bad take id only exploding in the
FCPXML writer).
"""
from __future__ import annotations

from typing import Any

FILE_KINDS = ("video", "audio")
FILE_CLASSES = ("speech", "broll")


def _req(errors: "list[str]", obj: "dict[str, Any]", key: str, typ: type, where: str) -> bool:
    """Require obj[key] to exist and be of type typ; record an error if not."""
    if key not in obj:
        errors.append("%s: missing '%s'" % (where, key))
        return False
    if not isinstance(obj[key], typ):
        errors.append("%s: '%s' should be %s, got %s"
                      % (where, key, typ.__name__, type(obj[key]).__name__))
        return False
    return True


def validate_catalog(data: "dict[str, Any]") -> "list[str]":
    """analysis/catalog.json — the probe + classification of every raw file."""
    errors: "list[str]" = []
    _req(errors, data, "slug", str, "catalog")
    if not _req(errors, data, "files", list, "catalog"):
        return errors
    if not data["files"]:
        errors.append("catalog: 'files' is empty — no footage found")
    names = set()
    for i, f in enumerate(data["files"]):
        where = "catalog.files[%d]" % i
        if not isinstance(f, dict):
            errors.append(where + ": not an object")
            continue
        _req(errors, f, "name", str, where)
        _req(errors, f, "path", str, where)
        _req(errors, f, "duration", (int, float), where)  # type: ignore[arg-type]
        if _req(errors, f, "kind", str, where) and f["kind"] not in FILE_KINDS:
            errors.append("%s: kind '%s' not in %s" % (where, f["kind"], FILE_KINDS))
        if _req(errors, f, "class", str, where) and f["class"] not in FILE_CLASSES:
            errors.append("%s: class '%s' not in %s" % (where, f["class"], FILE_CLASSES))
        if f.get("class") == "speech":
            if not f.get("words_file"):
                errors.append(where + ": speech file has no words_file")
        if isinstance(f.get("duration"), (int, float)) and f["duration"] <= 0:
            errors.append(where + ": duration must be > 0")
        n = f.get("name")
        if n in names:
            errors.append("%s: duplicate file name '%s'" % (where, n))
        names.add(n)
    return errors


def validate_words(data: "list[Any]") -> "list[str]":
    """<file>.words.json — whisper word timings: [{"w","s","e"}, ...]."""
    errors: "list[str]" = []
    if not isinstance(data, list):
        return ["words: not a list"]
    prev_end = 0.0
    for i, w in enumerate(data):
        where = "words[%d]" % i
        if not isinstance(w, dict):
            errors.append(where + ": not an object")
            continue
        _req(errors, w, "w", str, where)
        ok_s = _req(errors, w, "s", (int, float), where)  # type: ignore[arg-type]
        ok_e = _req(errors, w, "e", (int, float), where)  # type: ignore[arg-type]
        if ok_s and ok_e:
            if w["e"] < w["s"]:
                errors.append(where + ": end before start")
            if w["s"] < prev_end - 0.5:  # whisper can jitter slightly; big regressions are real errors
                errors.append(where + ": starts %.2fs before previous word ends" % (prev_end - w["s"]))
            prev_end = max(prev_end, float(w["e"]))
    return errors
