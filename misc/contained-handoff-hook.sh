# Sourced from ~/.bashrc (see install.sh). Bash-only: relies on
# PROMPT_COMMAND and on ~/.bashrc actually being sourced by the interactive
# shell in play - zsh/fish, or a shell that doesn't source ~/.bashrc, won't
# pick this up, and /go-contained's handoff will silently never resume.
#
# Checks for a pending session handoff written by the /go-contained command
# for THIS terminal (keyed by tty, so concurrent handoffs in other terminals
# don't clobber each other) and, if present, fresh, and the original process
# has actually exited, resumes it inside contained-claude on the next prompt.
_claude_contained_handoff_check() {
  local tty_id
  tty_id=$(tty 2>/dev/null | tr -c 'A-Za-z0-9' '_')
  [ -n "$tty_id" ] || return 0

  local f="$HOME/.claude/.contained-handoff.$tty_id"
  [ -f "$f" ] || return 0

  local session_id dir pid ts now
  { IFS= read -r session_id; IFS= read -r dir; IFS= read -r pid; IFS= read -r ts; } < "$f"
  rm -f "$f"

  if [ -z "$session_id" ] || [ -z "$dir" ] || [ ! -d "$dir" ]; then
    echo "contained-claude: handoff file was malformed, skipping." >&2
    return 0
  fi

  now=$(date +%s)
  if [ -n "$ts" ] && [ $(( now - ts )) -gt 3600 ]; then
    echo "contained-claude: handoff for session $session_id is over an hour old, skipping (stale)." >&2
    return 0
  fi

  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "contained-claude: session $session_id's original process ($pid) is still running, not resuming (avoids a double-resume race)." >&2
    return 0
  fi

  if [ -z "$CLAUDE_SANDBOX_SCRIPT" ] || [ ! -x "$CLAUDE_SANDBOX_SCRIPT" ]; then
    echo "contained-claude: CLAUDE_SANDBOX_SCRIPT is not set/executable, can't resume $session_id in the sandbox." >&2
    return 0
  fi

  echo "contained-claude: resuming session $session_id inside the sandbox..."
  ( cd "$dir" && "$CLAUDE_SANDBOX_SCRIPT" -r "$session_id" )
}

# PROMPT_COMMAND can be a plain string or, since bash 5.1, an array (used by
# tools like direnv/starship/atuin) - handle both so we don't clobber other
# tools' hooks by collapsing an array back into a scalar.
if declare -p PROMPT_COMMAND 2>/dev/null | grep -q '^declare -a'; then
  case " ${PROMPT_COMMAND[*]} " in
    *" _claude_contained_handoff_check "*) ;;
    *) PROMPT_COMMAND+=(_claude_contained_handoff_check) ;;
  esac
else
  case ";${PROMPT_COMMAND:-};" in
    *";_claude_contained_handoff_check;"*) ;;
    *) PROMPT_COMMAND="_claude_contained_handoff_check${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
  esac
fi
