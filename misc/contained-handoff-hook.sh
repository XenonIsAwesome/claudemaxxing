# Sourced from ~/.bashrc (see install.sh). Checks for a pending session
# handoff written by the /go-contained command and, if present, resumes it
# inside contained-claude on the very next shell prompt in this terminal.
_claude_contained_handoff_check() {
  local f="$HOME/.claude/.contained-handoff"
  [ -f "$f" ] || return 0

  local session_id dir
  { IFS= read -r session_id; IFS= read -r dir; } < "$f"
  rm -f "$f"

  if [ -z "$session_id" ] || [ -z "$dir" ] || [ ! -d "$dir" ]; then
    echo "contained-claude: handoff file was malformed, skipping." >&2
    return 0
  fi
  if [ -z "$CLAUDE_SANDBOX_SCRIPT" ] || [ ! -x "$CLAUDE_SANDBOX_SCRIPT" ]; then
    echo "contained-claude: CLAUDE_SANDBOX_SCRIPT is not set/executable, can't resume $session_id in the sandbox." >&2
    return 0
  fi

  echo "contained-claude: resuming session $session_id inside the sandbox..."
  ( cd "$dir" && "$CLAUDE_SANDBOX_SCRIPT" -r "$session_id" )
}

case ";${PROMPT_COMMAND:-};" in
  *";_claude_contained_handoff_check;"*) ;;
  *) PROMPT_COMMAND="_claude_contained_handoff_check${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
esac
