#!/usr/bin/env bash
# Build a throw-away git project with 8 real Claude Code sessions for testing session-graph.
# Needs: git, the `claude` CLI (logged in). Uses Haiku with one-line answers to keep cost low.
# Usage: tests/make_testbed.sh [target-dir]   (default: ../session-graph-testbed)
set -euo pipefail
T="${1:-$(cd "$(dirname "$0")/../.." && pwd)/session-graph-testbed}"
[ -e "$T" ] && { echo "already exists: $T" >&2; exit 1; }

mkdir -p "$T/docs" && cd "$T"
git init -q -b main
echo "# Todo App (session-graph testbed)" > README.md
echo "# notes" > docs/notes.md
printf ".worktrees/\n" > .gitignore
git add -A && git -c user.name=test -c user.email=test@example.com commit -qm init
git branch feature/auth
git worktree add -q .worktrees/ui -b experiment/ui

run() {  # prints the new session id
  claude -p --model haiku --output-format json "$@" |
    python -c "import json,sys; print(json.load(sys.stdin)['session_id'])"
}

S1=$(run "我们在做一个 todo app。先只用一句话回答：todo 的数据结构应该有哪些字段？")
run --resume "$S1" "好。再用一句话：存储先用 JSON 文件可以吗？" >/dev/null
S2=$(run --resume "$S1" --fork-session "换个思路：如果改用 SQLite 存储，一句话说优缺点。")
git checkout -q feature/auth
run "我们要给 todo app 加登录功能。一句话：用 session cookie 还是 JWT？" >/dev/null
run "一句话：登录功能的单元测试应该覆盖哪些情况？" >/dev/null
git checkout -q main
(cd .worktrees/ui && run "我们在试验 todo app 的新 UI。一句话：列表用卡片还是表格？" >/dev/null)
(cd docs && run "一句话：README 里应该写哪些使用说明？" >/dev/null)
run --resume "$S1" "一句话：JSON 文件放在哪个目录比较合适？" >/dev/null           # original keeps going
run --resume "$S2" --fork-session "如果坚持用 SQLite，一句话：用 ORM 还是直接写 SQL？" >/dev/null  # fork of a fork
git checkout -q feature/auth
run --resume "$S1" --fork-session "回到数据结构：一句话，todo 要不要加 userId 字段来支持多用户登录？" >/dev/null  # 2nd fork, other branch
git checkout -q main

echo "testbed ready: $T"
echo "open a Claude session in that folder and run /session-graph"
