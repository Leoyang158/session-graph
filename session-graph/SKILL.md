---
name: session-graph
description: Show an interactive graph of the Claude Code sessions in the current project — how they are grouped by git branch / worktree, their order in time, one-line summaries, running/archived state and context size. Use when the user runs /session-graph or asks to see, map, or visualize their sessions and how they relate.
---

# Session Graph

Builds an interactive HTML page that maps every Claude Code session of the **current project** (sessions whose working directory is the project or inside it).

- **Relationships:**
  - **Fork** (solid orange arrow, original → fork): detected from conversation records the two transcripts share; the closest ancestor wins for nested forks. The digest marks these as `FORK of <id> after: <prompt>`.
  - **Branch / folder:** sessions are grouped by git branch and by sub-directory/worktree.
  - **Time order:** inside a group a dashed arrow links each session to the next one.
- **Each node:** title, start / last activity, one-line summary, running, context size (tokens of the last turn; also the dot size), archived.
- **Read-only.** Never rename, archive, or delete sessions from this skill.

Script: `~/.claude/skills/session-graph/scripts/session_graph.py` (Python 3.8+, stdlib only; use `python` on Windows, `python3` elsewhere).
All output goes to `~/.claude/session-graph/<project-slug>/` (call it `OUT`): `desktop.json`, `sessions.json`, `summaries.json`, `graph.html`.
`collect` prints the exact data path (`OUT/sessions.json`) on its first lines.

## Steps

1. **Project** = the current working directory unless the user names another folder. Pass it as `--cwd` to both commands.

2. **Desktop metadata (only if the Claude desktop app's session tools exist).** If `mcp__ccd_session_mgmt__list_sessions` is available (load it with ToolSearch if it is deferred):
   - call `list_sessions` with `{"include_archived": true, "limit": 200}`, and `get_session` with `"self"` (the current session is excluded from the list);
   - write both results as one JSON array to `OUT/desktop.json`.
   This supplies titles, archived state and app links. Without it, archived shows as "未知" — that's fine; say so in one line.

3. **Collect:**
   ```
   python ~/.claude/skills/session-graph/scripts/session_graph.py collect --cwd "<project>" [--desktop "OUT/desktop.json"]
   ```
   It prints a digest: for every session that needs a (new) summary, its id, title, first and last prompt.

4. **Summaries.** For each session in the digest, write a one-line summary (≤ 40 characters, in the user's language) of what the session is about and where it got to — based only on the digest's title/first/last prompt. For a `FORK`, summarize what it does differently after the fork point (it shares its first prompt with the original, so the first prompt alone can't tell them apart). Merge into `OUT/summaries.json`, keeping existing entries:
   ```json
   {"<session id>": {"summary": "…", "turns": <turns from digest>}}
   ```
   Skip this step if the digest says `need summary: 0`.

5. **Render:**
   ```
   python ~/.claude/skills/session-graph/scripts/session_graph.py render --cwd "<project>"
   ```
   Then show `OUT/graph.html` to the user: in the Claude desktop app open it in the built-in browser (`preview_start` with its `file:///` URL); otherwise add `--open` to the render command to use the default browser.

6. **Report** in 2–4 lines: how many sessions, how they split into groups, which forks exist (original → fork), which are running, and the largest-context ones. Don't paste the whole list — the page has it.

## Notes

- Transcripts live in `~/.claude/projects/*/*.jsonl` (or `$CLAUDE_CONFIG_DIR/projects`). Sub-agent transcripts in sub-folders are ignored.
- "Running" = a live CLI process in `~/.claude/sessions/*.json`, or `isRunning` from the desktop app.
- Desktop rows have no CLI session id; they are matched on working directory + title, falling back to timestamps.
- The page loads vis-network from cdn.jsdelivr.net; offline, only the session list works.
