#!/usr/bin/env bash
# SessionStart hook: bootstrap the Python environment for a git WORKTREE.
#
# A freshly created git worktree does not inherit a usable environment, all by
# design:
#   * .venv/  and  uv.lock  are gitignored, so they never propagate.
#   * agent-skills/ is a git submodule, left uninitialized in a new worktree.
# The Hatch build hook (hatch_build.py) bundles agent-skills/blockscout-analysis
# into the wheel at build time, so the editable install — and therefore every
# `uv run pytest|ruff|python` — FAILS with "Bundled skill entrypoint not found"
# until the submodule is checked out.
#
# This hook performs that one-time setup automatically. It is deliberately
# scoped to LINKED worktrees only (never the main working tree, which the
# developer sets up normally) and is a fast, silent no-op once the worktree is
# ready, so it is safe to run on every session start.
#
# No `set -e`: a bootstrap failure must not hard-block session startup. Problems
# are detected explicitly and reported as context so the agent knows what to do.

# --- Host-only. Inside the devcontainer dependencies are system-wide. --------
[ -f /.dockerenv ] && exit 0

command -v git >/dev/null 2>&1 || exit 0
command -v uv  >/dev/null 2>&1 || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$ROOT" || exit 0

# --- Act only in a LINKED worktree, never the main working tree. -------------
# In the main tree --git-common-dir and --git-dir resolve to the same path; in a
# linked worktree --git-dir points at .git/worktrees/<name> while the common dir
# stays at the main .git.
common_abs="$(cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd)"
git_abs="$(cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd)"
[ -n "$common_abs" ] && [ "$common_abs" = "$git_abs" ] && exit 0

# --- Share the developer's local, gitignored files from the main worktree. ---
# .env (secrets/config) and .claude/settings.local.json (local permissions) are
# gitignored, so they don't propagate into a worktree. Symlink them to the main
# checkout so every worktree shares one source of truth. Claude Code seeds a
# *copy* of settings.local.json into each worktree at creation; replacing that
# identical copy with a symlink is safe. A copy that has DIVERGED from main is
# left untouched rather than clobbered, to avoid silent data loss.
MAIN_ROOT="$(dirname "$common_abs")"
if [ -d "$MAIN_ROOT" ] && [ "$MAIN_ROOT" != "$ROOT" ]; then
    link_shared() {
        local rel="$1" src="$MAIN_ROOT/$1"
        [ -e "$src" ] || return 0                                   # main has nothing to share
        [ -L "$rel" ] && [ "$(readlink "$rel")" = "$src" ] && return 0   # already linked → silent
        if [ -f "$rel" ] && [ ! -L "$rel" ] && ! cmp -s "$rel" "$src"; then
            echo "[worktree-bootstrap] Note: $rel differs from the main worktree's copy — left as-is (not symlinked)."
            return 0
        fi
        mkdir -p "$(dirname "$rel")"
        ln -snf "$src" "$rel" && echo "[worktree-bootstrap] Linked $rel from the main worktree."
    }
    link_shared .env
    link_shared .claude/settings.local.json
fi

# --- Already bootstrapped? Fast, silent no-op. -------------------------------
if [ -f agent-skills/blockscout-analysis/SKILL.md ] \
    && [ -x .venv/bin/pytest ] && [ -x .venv/bin/ruff ] \
    && .venv/bin/python -c "import blockscout_mcp_server" >/dev/null 2>&1; then
    exit 0
fi

# --- Bootstrap. --------------------------------------------------------------
echo "[worktree-bootstrap] Setting up this worktree's Python environment…"

if [ ! -f agent-skills/blockscout-analysis/SKILL.md ]; then
    if ! sub_out="$(git submodule update --init --recursive agent-skills 2>&1)"; then
        echo "[worktree-bootstrap] WARNING: could not initialize the agent-skills submodule (network?):"
        echo "$sub_out" | tail -n 3
        echo "[worktree-bootstrap] Re-run '.claude/hooks/bootstrap-worktree.sh' once connectivity is restored."
        exit 0
    fi
fi

[ -x .venv/bin/python ] || uv venv >/dev/null 2>&1

# [test] brings pytest + pytest-asyncio + pytest-cov + pytest-timeout;
# [dev] brings ruff + PyYAML. -q keeps the package list out of session context.
if ! install_out="$(uv pip install -q --python .venv -e ".[test,dev]" 2>&1)"; then
    echo "[worktree-bootstrap] WARNING: editable install failed:"
    echo "$install_out" | tail -n 5
    echo "[worktree-bootstrap] Re-run '.claude/hooks/bootstrap-worktree.sh' to retry."
    exit 0
fi

if .venv/bin/python -c "import blockscout_mcp_server" >/dev/null 2>&1; then
    echo "[worktree-bootstrap] Done: worktree-local .venv ready ($(.venv/bin/pytest --version 2>&1 | head -n1), $(.venv/bin/ruff --version 2>&1)). Run tools with 'uv run <tool>' or '.venv/bin/<tool>'."
else
    echo "[worktree-bootstrap] WARNING: project still not importable after install. Re-run '.claude/hooks/bootstrap-worktree.sh'."
fi
exit 0
