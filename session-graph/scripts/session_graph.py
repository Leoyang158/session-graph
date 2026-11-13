#!/usr/bin/env python3
"""Build an interactive relationship graph of the Claude Code sessions of one project.

Stdlib only. Two subcommands:

  collect  Scan ~/.claude/projects/*/*.jsonl, keep the sessions whose working
           directory is the project (or inside it), merge optional desktop-app
           metadata, write sessions.json and print a compact digest that Claude
           uses to write one-line summaries.

  render   Read sessions.json (+ optional summaries.json) and write a
           self-contained interactive HTML page.

Relationship model (prototype): sessions are grouped by git branch and by
sub-directory / worktree inside the project. Within a group they are ordered
by start time.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import sys
from pathlib import Path

CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
TAG_RE = re.compile(r"<(system-reminder|command-[a-z-]+|local-command-[a-z-]+|ide_[a-z_]+)[^>]*>.*?</\1>", re.S)
ANY_TAG_RE = re.compile(r"</?[a-zA-Z_][\w-]*[^>]*>")


# ---------------------------------------------------------------- helpers
def norm_path(p: str | None) -> str:
    if not p:
        return ""
    p = os.path.normpath(os.path.abspath(p))
    return p.lower() if os.name == "nt" else p


def is_inside(child: str, parent: str) -> bool:
    if not child or not parent:
        return False
    return child == parent or child.startswith(parent.rstrip("\\/") + os.sep)


def parse_ts(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def clean_text(t: str) -> str:
    t = TAG_RE.sub(" ", t)
    t = ANY_TAG_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def message_text(msg: dict) -> str:
    c = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(c, str):
        return clean_text(c)
    if isinstance(c, list):
        parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
        return clean_text(" ".join(parts))
    return ""


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = wintypes.DWORD()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def live_session_ids() -> dict[str, str]:
    """sessionId -> status ('busy'/'idle'/...) for CLI processes still alive."""
    out: dict[str, str] = {}
    for f in glob.glob(str(CLAUDE_HOME / "sessions" / "*.json")):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        sid, pid = d.get("sessionId"), d.get("pid")
        if sid and isinstance(pid, int) and pid_alive(pid):
            out[sid] = d.get("status") or "running"
    return out


# ---------------------------------------------------------------- parsing
def parse_session(path: Path) -> dict | None:
    s = {
        "id": path.stem, "file": str(path), "cwds": [], "branch": None,
        "start": None, "end": None, "customTitle": None, "aiTitle": None,
        "agentName": None, "firstPrompt": None, "lastPrompt": None,
        "userTurns": 0, "context": 0, "entrypoint": None, "model": None,
        "_msgs": {},  # uuid -> {ts, type, promptId, text}; insertion order = file order
    }
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("isSidechain"):
                continue
            t = d.get("type")
            ts = d.get("timestamp")
            if t in ("user", "assistant", "attachment") and d.get("uuid"):
                # conversation records: a fork copies these with the same uuid
                s["_msgs"][d["uuid"]] = {"ts": ts, "type": t, "promptId": d.get("promptId"), "text": None}
            if ts:
                s["start"] = s["start"] or ts
                s["end"] = ts
            cwd = d.get("cwd") or d.get("relocatedCwd")
            if cwd and cwd not in s["cwds"]:
                s["cwds"].append(cwd)
            if d.get("gitBranch"):
                s["branch"] = d["gitBranch"]
            if d.get("entrypoint"):
                s["entrypoint"] = d["entrypoint"]
            if t == "custom-title" and d.get("customTitle"):
                s["customTitle"] = d["customTitle"]
            elif t == "ai-title" and d.get("aiTitle"):
                s["aiTitle"] = d["aiTitle"]
            elif t == "agent-name" and d.get("agentName"):
                s["agentName"] = d["agentName"]
            elif t == "last-prompt" and d.get("lastPrompt"):
                # can be stale in forked sessions; only a fallback
                s["_lastPromptRecord"] = clean_text(str(d["lastPrompt"]))
            elif t == "user" and not d.get("isMeta"):
                origin = (d.get("origin") or {}).get("kind")
                if origin not in (None, "human"):
                    continue
                txt = message_text(d.get("message") or {})
                if txt:
                    if d.get("uuid") in s["_msgs"]:
                        s["_msgs"][d["uuid"]]["text"] = txt
                    s["userTurns"] += 1
                    s["firstPrompt"] = s["firstPrompt"] or txt
                    s["lastPrompt"] = txt
            elif t == "assistant":
                m = d.get("message") or {}
                u = m.get("usage") or {}
                total = sum(int(u.get(k) or 0) for k in (
                    "input_tokens", "cache_creation_input_tokens",
                    "cache_read_input_tokens", "output_tokens"))
                if total:
                    s["context"] = total
                if m.get("model"):
                    s["model"] = m["model"]
    if not s["start"]:
        return None
    fallback = s.pop("_lastPromptRecord", None)
    s["lastPrompt"] = s["lastPrompt"] or fallback
    s["title"] = s["customTitle"] or s["agentName"] or s["aiTitle"]
    s["titleFromPrompt"] = not s["title"]
    s["title"] = s["title"] or (s["firstPrompt"] or s["id"])[:60]
    return s


def file_birth(path: str) -> float:
    st = os.stat(path)
    return getattr(st, "st_birthtime", None) or (st.st_ctime if os.name == "nt" else st.st_mtime)


def fork_direction(a: dict, b: dict, shared: set) -> tuple[dict, dict] | None:
    """Return (parent, child) for two sessions sharing conversation records, or None."""
    own_a = [u for u in a["_msgs"] if u not in shared]
    own_b = [u for u in b["_msgs"] if u not in shared]
    if not own_a and not own_b:
        return None  # identical copies, nothing to tell
    # 1. a session whose whole conversation is inside the other one is the original
    if not own_a:
        return a, b
    if not own_b:
        return b, a
    # 2. a fork re-stamps the copied prompts with the promptId of its own first new prompt
    def restamped(s: dict, own: list) -> bool:
        own_ids = {s["_msgs"][u]["promptId"] for u in own} - {None}
        copied = {s["_msgs"][u]["promptId"] for u in shared if s["_msgs"][u]["type"] == "user"} - {None}
        return bool(copied) and copied <= own_ids
    ra, rb = restamped(a, own_a), restamped(b, own_b)
    if ra != rb:
        return (b, a) if ra else (a, b)
    if ra and rb:
        return None  # both are forks of a common ancestor: siblings, not parent/child
    # 3. fall back to file creation time: the fork's file is newer
    return (a, b) if file_birth(a["file"]) <= file_birth(b["file"]) else (b, a)


def detect_forks(sessions: list[dict]) -> None:
    """Set forkOf / forkShared / forkPoint / forkAt on forked sessions (closest ancestor wins)."""
    best: dict[str, tuple[int, dict, set]] = {}
    keys = {s["id"]: set(s["_msgs"]) for s in sessions}
    for i, a in enumerate(sessions):
        for b in sessions[i + 1:]:
            shared = keys[a["id"]] & keys[b["id"]]
            if not shared:
                continue
            pc = fork_direction(a, b, shared)
            if not pc:
                continue
            parent, child = pc
            if len(shared) > best.get(child["id"], (0,))[0]:
                best[child["id"]] = (len(shared), parent, shared)
    by_id = {s["id"]: s for s in sessions}
    for cid, (n, parent, shared) in best.items():
        child = by_id[cid]
        last_shared = [m for u, m in child["_msgs"].items() if u in shared]
        prompts = [m["text"] for m in last_shared if m["text"]]
        child["forkOf"] = parent["id"]
        child["forkShared"] = n
        child["forkPoint"] = prompts[-1] if prompts else None
        child["forkAt"] = next((m["ts"] for m in reversed(last_shared) if m["ts"]), None)
        # copied records keep the original timestamps; the fork really starts at its first new record
        own_ts = [m["ts"] for u, m in child["_msgs"].items() if u not in shared and m["ts"]]
        if own_ts:
            child["start"] = min(own_ts)


def load_desktop(path: str | None) -> list[dict]:
    if not path:
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"warning: cannot read desktop metadata {path}: {e}", file=sys.stderr)
        return []
    if isinstance(data, dict):
        data = data.get("sessions") or [data]
    return [d for d in data if isinstance(d, dict)]


def match_desktop(s: dict, desktop: list[dict], used: set[int]) -> dict | None:
    """Desktop rows carry no CLI session id: match on cwd + title, then on time."""
    cwds = {norm_path(c) for c in s["cwds"]}
    titles = {x.lower() for x in (s["customTitle"], s["agentName"], s["aiTitle"]) if x}
    start, end = parse_ts(s["start"]), parse_ts(s["end"])
    best = None
    for i, d in enumerate(desktop):
        if i in used or norm_path(d.get("cwd")) not in cwds:
            continue
        if (d.get("title") or "").lower() in titles:
            best = i
            break
        created, last = parse_ts(d.get("createdAt")), parse_ts(d.get("lastActivityAt"))
        if created and start and abs((created - start).total_seconds()) < 120:
            best = i
            break
        if last and end and abs((last - end).total_seconds()) < 120 and best is None:
            best = i
    if best is None:
        return None
    used.add(best)
    return desktop[best]


# ---------------------------------------------------------------- commands
def cmd_collect(a: argparse.Namespace) -> None:
    project = norm_path(a.cwd)
    desktop = load_desktop(a.desktop)
    live = live_session_ids()
    used: set[int] = set()
    sessions = []
    for f in sorted(glob.glob(str(CLAUDE_HOME / "projects" / "*" / "*.jsonl"))):
        s = parse_session(Path(f))
        if not s or not any(is_inside(norm_path(c), project) for c in s["cwds"]):
            continue
        main_cwd = s["cwds"][-1]
        rel = (os.path.relpath(os.path.abspath(main_cwd), os.path.abspath(a.cwd))
               if is_inside(norm_path(main_cwd), project) else main_cwd)
        s["location"] = "." if rel in (".", "") else rel
        branch = s["branch"] if s["branch"] and s["branch"] != "HEAD" else None
        s["group"] = f"{branch or '(no branch)'}" + ("" if s["location"] == "." else f" @ {s['location']}")
        s["running"] = s["id"] in live
        s["status"] = live.get(s["id"])
        s["archived"] = None  # unknown without desktop metadata
        d = match_desktop(s, desktop, used)
        if d:
            s["desktopId"] = d.get("sessionId")
            s["title"] = d.get("title") or s["title"]
            if "isArchived" in d:
                s["archived"] = bool(d["isArchived"])
            if "isRunning" in d:
                s["running"] = bool(d["isRunning"]) or s["running"]
            s["link"] = d.get("link")
        sessions.append(s)
    detect_forks(sessions)
    for s in sessions:
        del s["_msgs"]
    sessions.sort(key=lambda x: x["start"])
    out = {"project": a.cwd, "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
           "desktopMetadata": bool(desktop), "sessions": sessions}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    cache = load_summaries(str(Path(a.out).parent / "summaries.json"))
    todo = [s for s in sessions if cache.get(s["id"], {}).get("turns") != s["userTurns"]]
    print(f"project: {a.cwd}\nsessions: {len(sessions)}  (data -> {a.out})")
    print(f"need summary: {len(todo)}  (cached & unchanged: {len(sessions) - len(todo)})\n")
    for s in todo:
        print(f"id={s['id']}  group={s['group']}  turns={s['userTurns']}  ctx={s['context']}")
        if s.get("forkOf"):
            print(f"  FORK of {s['forkOf']} after: {(s.get('forkPoint') or '')[:a.chars]}")
        print(f"  title: {s['title']}")
        print(f"  first: {(s['firstPrompt'] or '')[:a.chars]}")
        print(f"  last : {(s['lastPrompt'] or '')[:a.chars]}\n")


def load_summaries(path: str | None) -> dict[str, dict]:
    """summaries.json: {id: "text"} or {id: {"summary": "text", "turns": n}}."""
    if not path or not Path(path).exists():
        return {}
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"warning: cannot read {path}: {e}", file=sys.stderr)
        return {}
    return {k: (v if isinstance(v, dict) else {"summary": v}) for k, v in raw.items()}


def cmd_render(a: argparse.Namespace) -> None:
    data = json.loads(Path(a.data).read_text(encoding="utf-8"))
    summaries = load_summaries(a.summaries)
    for s in data["sessions"]:
        written = summaries.get(s["id"], {}).get("summary")
        s["summary"] = written or (s.get("firstPrompt") or "")[:120]
        if written and s.get("titleFromPrompt") and not s.get("desktopId"):
            s["title"] = written  # untitled session: the summary is a better label than the raw prompt
        for k in ("firstPrompt", "lastPrompt"):
            if s.get(k):
                s[k] = s[k][:400]
        s.pop("file", None)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    page = tpl.replace("__TITLE__", html.escape(Path(data["project"]).name or data["project"]))
    page = page.replace("__LANG__", a.lang).replace("__DATA__", payload)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(page, encoding="utf-8")
    print(f"wrote {a.out}")
    if a.open:
        import webbrowser
        webbrowser.open(Path(a.out).resolve().as_uri())


def default_out_dir(cwd: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd))
    return CLAUDE_HOME / "session-graph" / slug


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect")
    c.add_argument("--cwd", default=os.getcwd(), help="project directory (default: current)")
    c.add_argument("--desktop", help="JSON from the desktop app's list_sessions (+ get_session self)")
    c.add_argument("--out", help="sessions.json path (default: ~/.claude/session-graph/<slug>/sessions.json)")
    c.add_argument("--chars", type=int, default=240, help="prompt chars shown in the digest")

    r = sub.add_parser("render")
    r.add_argument("--cwd", default=os.getcwd())
    r.add_argument("--data")
    r.add_argument("--summaries")
    r.add_argument("--out")
    r.add_argument("--open", action="store_true", help="open the page in the default browser")
    r.add_argument("--lang", choices=["en", "zh"], default="en", help="page language (switchable on the page too)")

    a = p.parse_args()
    base = default_out_dir(a.cwd)
    if a.cmd == "collect":
        a.out = a.out or str(base / "sessions.json")
        cmd_collect(a)
    else:
        a.data = a.data or str(base / "sessions.json")
        a.summaries = a.summaries or str(base / "summaries.json")
        a.out = a.out or str(base / "graph.html")
        cmd_render(a)


if __name__ == "__main__":
    main()
