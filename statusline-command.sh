#!/bin/bash
# Status line: model, context usage, token count, timestamp

input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name')

used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
if [ -n "$used_pct" ]; then
    context_str=$(printf '%.0f%%' "$used_pct")
else
    context_str="n/a"
fi

used_tokens=$(echo "$input" | jq -r '
    (.context_window.current_usage // {}) as $u |
    (($u.input_tokens // 0) + ($u.cache_creation_input_tokens // 0) + ($u.cache_read_input_tokens // 0))
')
max_tokens=$(echo "$input" | jq -r '.context_window.context_window_size // 0')

# Format a token count with a "k" suffix for readability
fmt_tokens() {
    local t="$1"
    if [ "$t" -ge 1000 ]; then
        awk -v t="$t" 'BEGIN { printf "%.1fk", t/1000 }'
    else
        printf '%s' "$t"
    fi
}

tokens_str="$(fmt_tokens "$used_tokens")/$(fmt_tokens "$max_tokens")"

timestamp=$(date +%H:%M:%S)

# Color the context percentage green/yellow/red based on usage
if [ -n "$used_pct" ]; then
    pct_int=${used_pct%.*}
    if [ "$pct_int" -ge 80 ]; then
        context_color='\033[1;31m'   # red
    elif [ "$pct_int" -ge 50 ]; then
        context_color='\033[1;33m'   # yellow
    else
        context_color='\033[1;32m'   # green
    fi
else
    context_color='\033[2m'
fi

sep='\033[2m|\033[0m'
model_c='\033[1;35m'    # bold magenta
tokens_c='\033[1;34m'   # bold blue
time_c='\033[2;37m'     # dim gray

printf "${model_c}%s\033[0m ${sep} Context: ${context_color}%s\033[0m ${sep} Tokens: ${tokens_c}%s\033[0m ${sep} ${time_c}%s\033[0m" \
    "$model" "$context_str" "$tokens_str" "$timestamp"
