# Archive note schema

Use this schema when calling `scripts/create_archive_note.py` or when adapting the note to an existing knowledge base.

## Input JSON

Required fields:

- `url`: Original URL supplied by the user.
- `title`: Source title or a short verified fallback.

Optional fields:

- `author`: Author, publisher, or account handle.
- `platform`: Examples: `web`, `x`, `github`, `youtube`.
- `published_at`: Source publication time in ISO 8601 when available.
- `archived_at`: Retrieval time in ISO 8601. Defaults to the current UTC time.
- `language`: BCP 47 language tag such as `zh-CN` or `en`.
- `summary`: Faithful source summary.
- `key_points`: Array of concise factual points.
- `excerpts`: Array of short attributed excerpts.
- `source_text`: Full source text only when the user owns it or has permission to preserve it.
- `links`: Array of objects with `label` and `url`.
- `tags`: Array of strings.
- `capture_notes`: Access limitations, missing media, thread boundaries, or extraction caveats.
- `rights_note`: Why full-text preservation is permitted, or the excerpt-only rule used.

Example:

```json
{
  "url": "https://example.com/post?utm_source=newsletter",
  "title": "A practical example",
  "author": "Example Author",
  "platform": "web",
  "published_at": "2026-08-11T09:00:00+08:00",
  "language": "en",
  "summary": "A concise and faithful summary.",
  "key_points": ["First verified point", "Second verified point"],
  "excerpts": ["A short attributed excerpt."],
  "links": [{"label": "Referenced project", "url": "https://github.com/example/project"}],
  "tags": ["reference", "example"],
  "capture_notes": "No media was downloaded.",
  "rights_note": "Excerpt-only archival note."
}
```

## Output Markdown

The script writes YAML frontmatter followed by these sections when data is available:

1. Summary
2. Key points
3. Source excerpts
4. Captured source text
5. Referenced links
6. Archival notes

Store analytical conclusions in a separate note. Link it back to the source note through the canonical URL or the created file path.
