#!/bin/bash

if [ -z "$BASH_VERSION" ]; then
  echo "install.sh requires bash - run it as ./install.sh or 'bash install.sh', not 'sh install.sh'." >&2
  exit 1
fi

function link_claude_file() {
  target=$1;
  link=$2;

  echo "Linking $target -> $link"
  mkdir -p $(dirname $link);
  ln -sf $target $link;
}

# Adding ~/.local/bin to PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc;
  export PATH="$HOME/.local/bin:$PATH";
fi

# Ensuring script can work
if ! command -v curl &> /dev/null; then
  echo "Please install curl for this script to work.";
  exit 1;
fi

if ! command -v git &> /dev/null; then
  echo "Please install git for this script to work.";
  exit 1;
fi

if ! command -v claude &> /dev/null; then
  echo "Please install claude for this script to work.";
  exit 1;
else
  claude auth status | grep "\"loggedIn\"\:\ false" 2>&1 >/dev/null;
  if [ "$?" == "0" ]; then
    claude setup-token;
#    echo "Please authenticate with claude before running this script."
#    exit 1;
  fi
fi

# Point /go-contained + the handoff hook at this checkout's contained-claude
# submodule, and source the hook itself.
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd);

if [ ! -x "$SCRIPT_DIR/contained-claude/sandbox.sh" ]; then
  echo "contained-claude submodule not initialized, running git submodule update --init...";
  (cd "$SCRIPT_DIR" && git submodule update --init contained-claude);
fi

if [ -x "$SCRIPT_DIR/contained-claude/sandbox.sh" ]; then
  # Replace (not just append-if-missing) any existing export line, so
  # re-running install.sh after moving/re-cloning the repo actually updates
  # the path instead of leaving a stale one in place.
  CLAUDE_SANDBOX_EXPORT_LINE="export CLAUDE_SANDBOX_SCRIPT=\"$SCRIPT_DIR/contained-claude/sandbox.sh\"";
  if grep -q '^export CLAUDE_SANDBOX_SCRIPT=' ~/.bashrc 2>/dev/null; then
    sed -i "s|^export CLAUDE_SANDBOX_SCRIPT=.*|$CLAUDE_SANDBOX_EXPORT_LINE|" ~/.bashrc;
  else
    echo "$CLAUDE_SANDBOX_EXPORT_LINE" >> ~/.bashrc;
  fi

  HOOK_LINE='[ -f "$HOME/.claude/contained-handoff-hook.sh" ] && source "$HOME/.claude/contained-handoff-hook.sh"';
  grep -qxF "$HOOK_LINE" ~/.bashrc 2>/dev/null || echo "$HOOK_LINE" >> ~/.bashrc;

  # Alias for calling contained-claude's sandbox.sh directly (e.g. to start
  # a fresh sandboxed session, not just resume one via /go-contained).
  CONTAINED_CLAUDE_ALIAS_LINE='alias contained-claude="$CLAUDE_SANDBOX_SCRIPT"';
  if grep -q '^alias contained-claude=' ~/.bashrc 2>/dev/null; then
    sed -i "s|^alias contained-claude=.*|$CONTAINED_CLAUDE_ALIAS_LINE|" ~/.bashrc;
  else
    echo "$CONTAINED_CLAUDE_ALIAS_LINE" >> ~/.bashrc;
  fi
else
  echo "warning: contained-claude/sandbox.sh is still missing after submodule init - /go-contained will not work until this is fixed." >&2;
fi

# Install uv & graphify
if ! command -v graphify &> /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh;
  uv tool install graphifyy;
fi

# Install plannotator cli
if ! command -v plannotator &> /dev/null; then
  curl -fsSL https://plannotator.ai/install.sh | bash -s -- --non-interactive --minimal
fi

# Add and update all marketplaces
claude plugin marketplace add backnotprop/plannotator;

# Install all plugins
xargs -a claude_plugins -n1 -r claude plugin install;

# Link all files
while read -r target link; do
  link_claude_file $target $link;
done < claude_links
