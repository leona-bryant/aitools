#!/usr/bin/env python3
"""Create a traceable Markdown archive note from structured JSON input."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref_src",
    "s",
    "si",
    "spm",
    "t",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON file path, or - for stdin")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_payload(source: str) -> dict:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    for field in ("url", "title"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    return payload


def canonicalize_url(raw_url: str) -> str:
    parts = urlsplit(raw_url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError("url must be an absolute HTTP(S) URL")
    hostname = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_KEYS:
            continue
        query.append((key, value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), hostname, path, urlencode(query, doseq=True), ""))


def slugify(title: str, canonical_url: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")[:72]
    if slug:
        return slug
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:10]
    return f"source-{digest}"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def normalized_list(payload: dict, key: str) -> list[str]:
    value = payload.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be an array of strings")
    return [item.strip() for item in value if item.strip()]


def render_note(payload: dict, canonical_url: str, archived_at: str) -> str:
    title = payload["title"].strip()
    author = str(payload.get("author") or "unknown").strip()
    platform = str(payload.get("platform") or "web").strip()
    published_at = str(payload.get("published_at") or "unknown").strip()
    language = str(payload.get("language") or "unknown").strip()
    tags = normalized_list(payload, "tags")
    key_points = normalized_list(payload, "key_points")
    excerpts = normalized_list(payload, "excerpts")

    lines = [
        "---",
        f"title: {yaml_string(title)}",
        f"source_url: {yaml_string(payload['url'].strip())}",
        f"canonical_url: {yaml_string(canonical_url)}",
        f"author: {yaml_string(author)}",
        f"platform: {yaml_string(platform)}",
        f"published_at: {yaml_string(published_at)}",
        f"archived_at: {yaml_string(archived_at)}",
        f"language: {yaml_string(language)}",
        f"tags: {json.dumps(tags, ensure_ascii=False)}",
        "---",
        "",
        f"# {title}",
        "",
        f"> Source: [{canonical_url}]({canonical_url})",
    ]

    summary = str(payload.get("summary") or "").strip()
    if summary:
        lines.extend(["", "## Summary", "", summary])
    if key_points:
        lines.extend(["", "## Key points", ""])
        lines.extend(f"- {point}" for point in key_points)
    if excerpts:
        lines.extend(["", "## Source excerpts", ""])
        for excerpt in excerpts:
            quoted = "\n> ".join(excerpt.splitlines())
            lines.append(f"> {quoted}")
            lines.append("")

    source_text = str(payload.get("source_text") or "").strip()
    if source_text:
        lines.extend(["", "## Captured source text", "", source_text])

    links = payload.get("links", []) or []
    if not isinstance(links, list):
        raise ValueError("links must be an array")
    rendered_links = []
    for item in links:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            raise ValueError("each link must contain a string url")
        label = str(item.get("label") or item["url"]).strip()
        rendered_links.append(f"- [{label}]({item['url'].strip()})")
    if rendered_links:
        lines.extend(["", "## Referenced links", "", *rendered_links])

    notes = []
    for key, label in (("capture_notes", "Capture"), ("rights_note", "Rights")):
        value = str(payload.get(key) or "").strip()
        if value:
            notes.append(f"- **{label}:** {value}")
    if notes:
        lines.extend(["", "## Archival notes", "", *notes])

    return "\n".join(lines).rstrip() + "\n"


def find_duplicate(output_dir: Path, canonical_url: str) -> Path | None:
    needle = f"canonical_url: {yaml_string(canonical_url)}"
    if not output_dir.exists():
        return None
    for path in output_dir.rglob("*.md"):
        try:
            if needle in path.read_text(encoding="utf-8", errors="ignore")[:65536]:
                return path
        except OSError:
            continue
    return None


def main() -> int:
    args = parse_args()
    try:
        payload = read_payload(args.input)
        canonical_url = canonicalize_url(payload["url"])
        archived_at = str(payload.get("archived_at") or dt.datetime.now(dt.timezone.utc).isoformat())
        date_prefix = archived_at[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", archived_at) else dt.date.today().isoformat()
        markdown = render_note(payload, canonical_url, archived_at)
        duplicate = find_duplicate(args.output_dir, canonical_url)
        if duplicate:
            print(json.dumps({"status": "duplicate", "path": str(duplicate), "canonical_url": canonical_url}, ensure_ascii=False))
            return 0
        if args.dry_run:
            sys.stdout.write(markdown)
            return 0

        args.output_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(payload["title"], canonical_url)
        target = args.output_dir / f"{date_prefix}__{slug}.md"
        if target.exists():
            digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:8]
            target = args.output_dir / f"{date_prefix}__{slug}--{digest}.md"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(markdown, encoding="utf-8", newline="\n")
        temporary.replace(target)
        print(json.dumps({"status": "created", "path": str(target), "canonical_url": canonical_url}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
