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

S1=$(run "We're building a todo app. In one sentence: which fields should a todo item have?")
run --resume "$S1" "OK. In one sentence: is a JSON file fine for storage to start with?" >/dev/null
S2=$(run --resume "$S1" --fork-session "Different idea: what are the pros and cons of SQLite for storage instead? One sentence.")
git checkout -q feature/auth
run "We're adding login to the todo app. In one sentence: session cookies or JWT?" >/dev/null
run "In one sentence: which cases should the login unit tests cover?" >/dev/null
git checkout -q main
(cd .worktrees/ui && run "We're trying a new UI for the todo app. In one sentence: cards or a table for the list?" >/dev/null)
(cd docs && run "In one sentence: what usage instructions belong in the README?" >/dev/null)
run --resume "$S1" "In one sentence: which directory should the JSON file live in?" >/dev/null           # original keeps going
run --resume "$S2" --fork-session "If we stick with SQLite, in one sentence: an ORM or plain SQL?" >/dev/null  # fork of a fork
git checkout -q feature/auth
run --resume "$S1" --fork-session "Back to the data model, in one sentence: should todos get a userId field for multi-user login?" >/dev/null  # 2nd fork, other branch
git checkout -q main

echo "testbed ready: $T"
echo "open a Claude session in that folder and run /session-graph"
