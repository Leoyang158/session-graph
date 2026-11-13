# 🕸️ session-graph

**See how your Claude Code sessions relate to each other — as an interactive graph.**

**English** · [🇨🇳 中文](README.zh-CN.md)

![session-graph screenshot](docs/screenshot.jpg)

---

## 🤔 Why

To keep context small, or to try a different idea, you split work into many Claude Code sessions. After a while it's hard to remember *which session forked from which*, *what each one was about*, and *which one to go back to*. `session-graph` is a [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills) that draws them as a map.

## ✨ Features

| | |
|---|---|
| 🍴 **Fork tree** | Detects which session was forked from which (even forks of forks), and shows the exact message where they diverged |
| 🌿 **Branch & folder groups** | Groups sessions by git branch, worktree and sub-folder |
| ⏱️ **Timeline** | Dashed arrows show the order sessions were started within a group |
| 📝 **One-line summaries** | Claude writes a short summary per session (cached, so unchanged sessions cost nothing next time) |
| 🟢 **Status** | Running / idle / archived (archived state needs the Claude desktop app) |
| 📏 **Context size** | Tokens in use per session — bigger dot = fuller context |
| 🔍 **Details on click** | First & last prompt, start / last activity, fork point, and how to resume it |
| 🌐 **English / 中文** | The page is in English by default; switch with the 中文 link or `--lang zh` |
| 👀 **Read-only** | Never renames, archives or deletes anything |

## 📦 Install

Requires Python 3.8+ (standard library only) and Claude Code.

```bash
git clone https://github.com/Leoyang158/session-graph.git
cp -r session-graph/session-graph ~/.claude/skills/
```

On Windows PowerShell:

```powershell
git clone https://github.com/Leoyang158/session-graph.git
Copy-Item -Recurse session-graph\session-graph $HOME\.claude\skills\
```

This installs it as a **user-level skill**, available in every project.

## 🚀 Usage

Open Claude Code in your project folder and type:

```
/session-graph
```

Claude collects this project's sessions, writes the summaries, and opens the graph in your browser. The page is saved to `~/.claude/session-graph/<project>/graph.html`.

**Reading the graph:**

- 🟠 **Solid orange arrow:** original session → fork
- 🟣 **Dashed purple arrow:** the next session in time, within the same group
- 🟫 **Boxes:** the project, plus one box per git branch / folder
- 🟢 Running · 🔵 Not running · ⚪ Archived

## ⚙️ How it works

1. `scripts/session_graph.py collect` reads `~/.claude/projects/*/*.jsonl` and keeps the sessions whose working directory is your project (or inside it).
2. **Forks:** a forked transcript copies the original's messages with the same IDs. The script uses those to find each fork's closest ancestor. It decides which side is the original from which one is fully contained in the other, then from how prompt IDs are re-stamped, and finally from file creation time.
3. If the Claude desktop app's session tools are available, Claude adds titles, archived state and app links.
4. Claude writes the one-line summaries, and `render` builds a self-contained HTML page using [vis-network](https://visjs.github.io/vis-network/).

🔒 Everything stays on your machine. The only network request is the page loading vis-network from a CDN.

## 🧪 Testing

`tests/make_testbed.sh` builds a throw-away git project with 8 real sessions (branches, a worktree, and nested and sibling forks) using Haiku, at very low cost. See [TESTING.md](TESTING.md) for the checklist.

## 🚧 Limitations

- Archived state is only known for sessions in the Claude desktop app.
- Sessions started from another session with the desktop app's `start_session` are not linked yet.
- Offline, the graph can't load; the session list still works.
