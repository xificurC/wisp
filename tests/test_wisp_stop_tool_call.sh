#!/usr/bin/env bash
# End-to-end test for the premature stream end: tool-call deltas that
# close with finish_reason stop. The loop must run the tools, ask
# again, and finish the turn. No dropped line may appear: nothing is
# lost. Usage: bash tests/test_wisp_stop_tool_call.sh

set -u

WISP="$(cd "$(dirname "$0")/.." && pwd)/wisp/wisp"
FIXTURE="$(cd "$(dirname "$0")" && pwd)/fixtures/fake_llm_sse.py"

TESTDIR="$(mktemp -d)"
trap 'chmod -R u+w "$TESTDIR" 2>/dev/null; rm -rf "$TESTDIR"' EXIT
export WISP_SESSIONS_ROOT="$TESTDIR/sessions"

pass=0
fail=0

check() {
    local name="$1" got="$2"
    if [ "$got" = "0" ]; then
        echo "PASS: $name"
        pass=$((pass + 1))
    else
        echo "FAIL: $name"
        fail=$((fail + 1))
    fi
}

count() {
    local pattern="$1" path="$2"
    if [ ! -f "$path" ]; then
        echo 0
        return
    fi
    grep -cF "$pattern" "$path"
}

python3 "$FIXTURE" 0 stopcall > "$TESTDIR/port" 2> "$TESTDIR/fixture.err" &
FAKE_PID=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -s "$TESTDIR/port" ] && break
    sleep 0.3
done
PORT="$(head -1 "$TESTDIR/port")"

if [ -n "$PORT" ]; then
    export WISP_LLM_URL="http://127.0.0.1:$PORT"
    export WISP_LLM_API_KEY="k"
    export WISP_LLM_API="openai-chat"
    C1="$($WISP new --name t1 -m test-model)"
    $WISP run -d "$C1" > "$TESTDIR/out.txt" 2> "$TESTDIR/err.txt" <<'PROMPT'
do the task
PROMPT
    rc=$?
    if [ "$rc" -eq 0 ] \
       && grep -qF "stop-call-round" "$C1/wisp.jsonl" \
       && grep -qF "the fake final answer" "$C1/wisp.jsonl" \
       && [ "$($WISP response -d "$C1")" = "the fake final answer" ] \
       && [ "$(count ' dropped ' "$C1/wisp.log")" -eq 0 ]; then
        check "stop finish with tool calls runs the tools and finishes" 0
    else
        echo "--- err.txt:"; cat "$TESTDIR/err.txt"
        echo "--- jsonl types:"; python3 - "$C1/wisp.jsonl" <<'PY'
import json, sys
print([json.loads(l).get("type") for l in open(sys.argv[1]) if l.strip()])
PY
        check "stop finish with tool calls runs the tools and finishes" 1
    fi
else
    echo "fixture did not start:"; cat "$TESTDIR/fixture.err"
    check "stop finish with tool calls runs the tools and finishes" 1
fi

kill "$FAKE_PID" 2>/dev/null
wait "$FAKE_PID" 2>/dev/null

echo "----------------------------------------"
[ "$fail" -eq 0 ] && echo "pass=$pass fail=0" || echo "pass=$pass fail=$fail"
exit "$fail"
