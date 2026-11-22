# Lessons

One line per mistake pattern. After a correction, add an entry or bump its count and `last` date.
Format: `- <area> (seen N, first YYYY-MM-DD, last YYYY-MM-DD): <the mistake pattern> -> <the rule that prevents it>`

On the first working day of each month, every lesson seen 2+ becomes a check in
`scripts/lessons_proof.py` (with a breaker in `--selftest`), and its entry moves below as a one-line pointer.

## Open

(none yet: the repo has one commit and no corrections on record, 2026-11-22)

## Promoted to checks

These were written as checks up front, when the practice was brought into this repo
(2026-11-22), from the rules the pages already keep. Each is `scripts/lessons_proof.py <check>`.

- eol: no tracked text file is CRLF or mixed in the index, and `.gitattributes` keeps `* text=auto eol=lf`.
- encoding: text files are valid UTF-8; every page declares `<meta charset="utf-8">` in its first 1024 bytes.
- links: every relative href/src in the pages resolves to a tracked file; no root-absolute links (Pages serves under a project path).
- legal_links: `index.html` and `callback.html` link `eula.html` and `privacy.html`; the EULA and privacy pages link each other.
- callback: `callback.html` keeps no-referrer and noindex, reads code/realmId/state/error, strips the code from the URL, and never sends or stores it (no fetch/XHR/beacon/form/external script/storage/innerHTML).
- self_contained: no page loads anything from another site or uses cookies or storage; `.nojekyll` stays tracked.
