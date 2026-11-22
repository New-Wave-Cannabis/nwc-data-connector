# nwc-data-connector

Public GitHub Pages site for the New Wave Cannabis data connector: `index.html`, `callback.html` (OAuth
redirect), `eula.html`, `privacy.html`. These are public legal and OAuth pages: change their content only
on purpose.

Before pushing: `python3 scripts/lessons_proof.py --selftest && python3 scripts/lessons_proof.py`
(CI runs both). Scripts are Python stdlib only. Work on a branch and open a PR; never push to `main`.

## Lessons loop

@tasks/lessons.md

- After any correction, add an entry to `tasks/lessons.md` or bump its `seen` count and `last` date.
- On the first working day of each month, every lesson seen 2+ becomes a check in
  `scripts/lessons_proof.py` with a breaker in `--selftest`, and its entry is replaced by a one-line
  pointer under "Promoted to checks".
