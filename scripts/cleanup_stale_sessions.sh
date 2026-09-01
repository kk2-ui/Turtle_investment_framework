#!/bin/bash
LOG=/tmp/session_cleanup.log

# Count claude processes
CLAUDE_COUNT=$(ps aux | grep -v grep | grep "claude --output-format" | wc -l)
ACTIVE_PID=$(ps aux | grep -v grep | grep "claude.*replay-user-messages" | awk '{print $2}' | head -1)

# If >1 claude process, kill the extra ones (not the active one)
if [ "$CLAUDE_COUNT" -gt 1 ]; then
    for pid in $(ps aux | grep -v grep | grep "claude --output-format" | awk '{print $2}'); do
        if [ "$pid" != "$ACTIVE_PID" ]; then
            kill $pid 2>/dev/null && echo "$(date): Killed extra claude pid $pid" >> $LOG
        fi
    done
fi

# Clear stale agent_session_id from cc-connect session files
SESSION_DIR="$HOME/.cc-connect/sessions"
if [ -d "$SESSION_DIR" ]; then
    for sf in "$SESSION_DIR"/*.json; do
        [ -f "$sf" ] || continue
        python3 -c "
import json
with open('$sf') as f: d = json.load(f)
changed = False
for s in d.get('sessions',{}).values():
    sid = s.get('agent_session_id','')
    if sid and sid != '$ACTIVE_SESSION':
        s['agent_session_id'] = ''
        changed = True
if changed:
    with open('$sf','w') as f: json.dump(d, f, ensure_ascii=False, indent=2)
    print('cleared')
" 2>/dev/null | grep -q "cleared" && echo "$(date): Cleared stale session IDs from $(basename $sf)" >> $LOG
    done
fi
