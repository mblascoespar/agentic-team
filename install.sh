#!/usr/bin/env bash
# install.sh — make agentic-team available globally across all projects
#
# What this does:
#   1. Registers the MCP server with Claude Code (user scope)
#   2. Symlinks the skills directory into ~/.claude/commands/
#
# Run once from the cloned repo. Re-running is safe (idempotent).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_NAME="agentic-team"
MCP_SERVER="$REPO_DIR/engine/mcp_server.py"
SKILLS_SOURCE="$REPO_DIR/.claude/commands"
SKILLS_LINK="$HOME/.claude/commands/agentic-team"

# ---------------------------------------------------------------------------
# Pre-flight: claude CLI must be present
# ---------------------------------------------------------------------------

if ! command -v claude &>/dev/null; then
    echo "ERROR: 'claude' CLI not found." >&2
    echo "Install Claude Code first: https://claude.ai/code" >&2
    exit 1
fi

if ! command -v python3 &>/dev/null && ! command -v uv &>/dev/null; then
    echo "ERROR: neither 'python3' nor 'uv' found." >&2
    echo "Install Python 3 or uv before running this script." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Register MCP server (idempotent)
# ---------------------------------------------------------------------------

if claude mcp list --scope user 2>/dev/null | grep -q "^$MCP_NAME"; then
    echo "  MCP server '$MCP_NAME' already registered — skipping."
else
    if command -v uv &>/dev/null; then
        claude mcp add --scope user "$MCP_NAME" -- uv run python "$MCP_SERVER"
    else
        claude mcp add --scope user "$MCP_NAME" -- python3 "$MCP_SERVER"
    fi
    echo "  MCP server '$MCP_NAME' registered."
fi

# ---------------------------------------------------------------------------
# Symlink skills (idempotent)
# ---------------------------------------------------------------------------

mkdir -p "$HOME/.claude/commands"

if [ -L "$SKILLS_LINK" ]; then
    echo "  Skills symlink already exists — skipping."
elif [ -e "$SKILLS_LINK" ]; then
    echo "ERROR: $SKILLS_LINK exists but is not a symlink. Remove it manually and re-run." >&2
    exit 1
else
    ln -s "$SKILLS_SOURCE" "$SKILLS_LINK"
    echo "  Skills symlinked: $SKILLS_LINK -> $SKILLS_SOURCE"
fi

echo ""
echo "agentic-team installed."
echo ""
echo "To use in a project:"
echo "  1. Copy templates/CLAUDE.md to your project root"
echo "  2. Open Claude Code in your project"
echo "  3. Run /brainstorm to start"
