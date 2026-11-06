#!/usr/bin/env bash
# Non-stream openai-chat through WISP_LLM_STREAM=false.
# One whole chat.completion body per round: the wire body carries
# "stream": false and no stream_options, the two tool calls of round
# one stay two records with their own ids, usage lands, and the final
# answer renders. Fixture: tests/fixtures/fake_llm_sse.py mode
# json_two, which also answers 400 when a request still asks for a
# stream, so a body gate regression fails the run.
# Usage: bash tests/test_wisp_run_nonstream.sh

set -u

WISP="$(cd "$(dirname "$0")/.." && pwd)/wisp/wisp"
FIXTURE="$(cd "$(dirname "$0")" && pwd)/fixtures/fake_llm_sse.py"

TESTDIR="$(mktemp -d)"
trap 'chmod -R u+w "$TESTDIR" 2>/dev/null; rm -rf "$TESTDIR"' EXIT
export WISP_SESSIONS_ROOT="$TESTDIR/sessions"
export FAKE_LLM_CAPTURE="$TESTDIR/requests.txt"

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

count() {  # pattern file -> match count; 0 when the file is absent
    local n
    n="$(grep -cF "$1" "$2" 2>/dev/null)"
    [ -n "$n" ] && echo "$n" || echo 0
}

: > "$TESTDIR/port.txt"
python3 "$FIXTURE" json_two >> "$TESTDIR/port.txt" 2> "$TESTDIR/fixture.err" &
FAKE_PID=$!
PORT=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    port="$(tr -d '[:space:]' < "$TESTDIR/port.txt" 2>/dev/null)"
    case "$port" in
        ""|*[!0-9]*) ;;
        *) PORT="$port"; break ;;
    esac
    kill -0 "$FAKE_PID" 2>/dev/null || break
    sleep 0.2
done

if [ -n "$PORT" ]; then
    export WISP_LLM_URL="http://127.0.0.1:$PORT"
    export WISP_LLM_API_KEY=fake-key
    export WISP_LLM_STREAM=false
    C="$($WISP new --name ns -m test-model)"
    $WISP run -d "$C" > "$TESTDIR/out.txt" 2> "$TESTDIR/err.txt" <<'PROMPT'
do the task
PROMPT
    rc=$?

    # Round one: prompt, two tool calls, two results. Round two: the
    # stop answer. Two commit lines, two assistant records.
    if [ "$rc" -eq 0 ] \
       && [ "$(count ' commit records=' "$C/wisp.log")" -eq 2 ] \
       && [ "$(count '"type": "user"' "$C/wisp.jsonl")" -eq 1 ] \
       && [ "$(count '"type": "assistant"' "$C/wisp.jsonl")" -eq 2 ] \
       && [ "$(count ' mode=json payloads=1 ' "$C/wisp.log")" -eq 2 ]; then
        check "1: two non-stream rounds exit 0 and commit" 0
    else
        check "1: two non-stream rounds exit 0 and commit" 1
    fi

    # Both wire bodies ask for no stream and carry no stream_options.
    stream_false="$(grep -oF '"stream": false' "$TESTDIR/requests.txt" \
                    2>/dev/null | wc -l | tr -d '[:space:]')"
    if [ "$stream_false" = "2" ] \
       && [ "$(count 'stream_options' "$TESTDIR/requests.txt")" -eq 0 ] \
       && [ "$(count '"stream": true' "$TESTDIR/requests.txt")" -eq 0 ]; then
        check "2: the wire body sends stream false, no stream_options" 0
    else
        check "2: the wire body sends stream false, no stream_options" 1
    fi

    # Two unindexed calls arrive in one reply; the position index the
    # adapter adds keeps them apart.
    if [ "$(count '"type": "tool"' "$C/wisp.jsonl")" -eq 2 ] \
       && grep -qF '"call_id": "call_1"' "$C/wisp.jsonl" \
       && grep -qF '"call_id": "call_2"' "$C/wisp.jsonl" \
       && grep -qF "first-call" "$C/wisp.jsonl" \
       && grep -qF "second-call" "$C/wisp.jsonl"; then
        check "3: both calls of one whole reply run as records" 0
    else
        check "3: both calls of one whole reply run as records" 1
    fi

    # The usage chunk of each round lands in wisp.usage.
    if [ "$(count '"prompt_tokens": 11' "$C/wisp.usage")" -eq 2 ] \
       && [ "$(count '"cached_tokens": 3' "$C/wisp.usage")" -eq 2 ] \
       && [ "$(count '"completion_tokens": 7' "$C/wisp.usage")" -eq 2 ]; then
        check "4: usage carries prompt, cached and completion tokens" 0
    else
        check "4: usage carries prompt, cached and completion tokens" 1
    fi

    $WISP render-past -d "$C" > "$TESTDIR/past.txt" 2>/dev/null
    if [ "$($WISP response -d "$C")" = "the fake final answer" ] \
       && grep -qF "the fake final answer" "$TESTDIR/past.txt" \
       && grep -qF "[bash " "$TESTDIR/past.txt"; then
        check "5: response and render-past show the answer" 0
    else
        check "5: response and render-past show the answer" 1
    fi
else
    for n in 1 2 3 4 5; do
        check "$n: fixture did not start" 1
    done
fi

kill "$FAKE_PID" 2>/dev/null
wait "$FAKE_PID" 2>/dev/null

echo "----------------------------------------"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
