#!/bin/bash

if [ -z "$BASH_VERSION" ]; then
  echo "install.sh requires bash - run it as ./install.sh or 'bash install.sh', not 'sh install.sh'." >&2
  exit 1
fi

if ! command -v git &> /dev/null; then
  echo "Please install git for this script to work.";
  exit 1;
fi

# Bootstrap: if this isn't running from inside an actual claudemaxxing
# checkout (e.g. fetched standalone via `curl | bash`, or downloaded on its
# own without the rest of the repo), clone the full repo into
# ~/.claudemaxxing and re-exec install.sh from there, so every relative path
# below (claude_links, claude_plugins, claude-tainer/, etc.) resolves
# correctly. Running install.sh from within an already-cloned checkout
# (anywhere on disk) skips this entirely and behaves as before.
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd);

if [ ! -f "$SCRIPT_DIR/claude_links" ]; then
  CLAUDEMAXXING_DIR="$HOME/.claudemaxxing";
  if [ -f "$CLAUDEMAXXING_DIR/claude_links" ]; then
    echo "Found existing claudemaxxing checkout at $CLAUDEMAXXING_DIR, using it.";
  elif [ -e "$CLAUDEMAXXING_DIR" ]; then
    echo "$CLAUDEMAXXING_DIR already exists but doesn't look like a claudemaxxing checkout - remove or rename it, then re-run." >&2;
    exit 1;
  else
    echo "Cloning claudemaxxing into $CLAUDEMAXXING_DIR...";
    git clone --recurse-submodules https://github.com/XenonIsAwesome/claudemaxxing.git "$CLAUDEMAXXING_DIR" || exit 1;
  fi
  exec bash "$CLAUDEMAXXING_DIR/install.sh" "$@";
fi

# claude_links stores its link sources as paths relative to the repo root
# (e.g. `misc/settings.json`), so make sure we're actually running from
# there regardless of where install.sh was invoked from.
cd "$SCRIPT_DIR" || exit 1;

function link_claude_file() {
  target="$SCRIPT_DIR/$1";
  link="$HOME/.claude/$2";

  echo "Linking $target -> $link"
  mkdir -p $(dirname $link);
  ln -sf "$target" "$link";
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

if ! command -v claude &> /dev/null; then
  echo "Please install claude for this script to work.";
  exit 1;
else
  claude auth status | grep "\"loggedIn\"\:\ false" 2>&1 >/dev/null;
  if [ "$?" == "0" ]; then
    echo "Please authenticate with claude before running this script."
    exit 1;
  fi
fi

# Point /claude-tainer + the handoff hook at this checkout's claude-tainer
# submodule, and source the hook itself.
if [ ! -x "$SCRIPT_DIR/claude-tainer/sandbox.sh" ]; then
  echo "claude-tainer submodule not initialized, running git submodule update --init...";
  (cd "$SCRIPT_DIR" && git submodule update --init claude-tainer);
fi

if [ -x "$SCRIPT_DIR/claude-tainer/sandbox.sh" ]; then
  # Replace (not just append-if-missing) any existing export line, so
  # re-running install.sh after moving/re-cloning the repo actually updates
  # the path instead of leaving a stale one in place.
  CLAUDE_SANDBOX_EXPORT_LINE="export CLAUDE_SANDBOX_SCRIPT=\"$SCRIPT_DIR/claude-tainer/sandbox.sh\"";
  if grep -q '^export CLAUDE_SANDBOX_SCRIPT=' ~/.bashrc 2>/dev/null; then
    sed -i "s|^export CLAUDE_SANDBOX_SCRIPT=.*|$CLAUDE_SANDBOX_EXPORT_LINE|" ~/.bashrc;
  else
    echo "$CLAUDE_SANDBOX_EXPORT_LINE" >> ~/.bashrc;
  fi

  HOOK_LINE='[ -f "$HOME/.claude/claude-tainer-handoff-hook.sh" ] && source "$HOME/.claude/claude-tainer-handoff-hook.sh"';
  grep -qxF "$HOOK_LINE" ~/.bashrc 2>/dev/null || echo "$HOOK_LINE" >> ~/.bashrc;

  # Alias for calling claude-tainer's sandbox.sh directly (e.g. to start
  # a fresh sandboxed session, not just resume one via /claude-tainer).
  CONTAINED_CLAUDE_ALIAS_LINE='alias claude-tainer="$CLAUDE_SANDBOX_SCRIPT"';
  if grep -q '^alias claude-tainer=' ~/.bashrc 2>/dev/null; then
    sed -i "s|^alias claude-tainer=.*|$CONTAINED_CLAUDE_ALIAS_LINE|" ~/.bashrc;
  else
    echo "$CONTAINED_CLAUDE_ALIAS_LINE" >> ~/.bashrc;
  fi
else
  echo "warning: claude-tainer/sandbox.sh is still missing after submodule init - /claude-tainer will not work until this is fixed." >&2;
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
xargs -a "$SCRIPT_DIR/claude_plugins" -n1 -r claude plugin install;

# Link all files
while read -r target link; do
  link_claude_file $target $link;
done < "$SCRIPT_DIR/claude_links"
