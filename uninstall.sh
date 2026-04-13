#!/usr/bin/env bash
# uninstall.sh — remove agentic-team global registration
#
# Reverses everything install.sh did. Safe to run even if install was
# never completed or only partially completed.

set -euo pipefail

MCP_NAME="agentic-team"
SKILLS_LINK="$HOME/.claude/commands/agentic-team"

# ---------------------------------------------------------------------------
# Remove MCP server registration
# ---------------------------------------------------------------------------

if command -v claude &>/dev/null && claude mcp list --scope user 2>/dev/null | grep -q "^$MCP_NAME"; then
    claude mcp remove --scope user "$MCP_NAME"
    echo "  MCP server '$MCP_NAME' removed."
else
    echo "  MCP server '$MCP_NAME' not registered — skipping."
fi

# ---------------------------------------------------------------------------
# Remove skills symlink
# ---------------------------------------------------------------------------

if [ -L "$SKILLS_LINK" ]; then
    rm "$SKILLS_LINK"
    echo "  Skills symlink removed: $SKILLS_LINK"
else
    echo "  Skills symlink not found — skipping."
fi

echo ""
echo "agentic-team uninstalled."
