#!/usr/bin/env bash
# Tests for per-round commits in wisp run.
# Cases 1-6, driven by fixtures/fake_llm_sse.py modes (the spec
# amendment: wisp talks HTTP through urllib, so the fake curl PATH
# shim cannot intercept it; the SSE fixture does).
# Usage: bash tests/test_wisp_per_round_commit.sh

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

count() {  # pattern file -> match count; 0 when the file is absent
    local n
    n="$(grep -c "$1" "$2" 2>/dev/null)"
    [ -n "$n" ] && echo "$n" || echo 0
}

FAKE_PID=""

start_fake() { # mode
    # The parent truncates the port file first: the bg child appends,
    # and a stale number from a previous fixture can never pass.
    : > "$TESTDIR/port.txt"
    python3 "$FIXTURE" "$1" \
        >> "$TESTDIR/port.txt" 2> "$TESTDIR/port.err.txt" &
    FAKE_PID=$!
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
        port="$(tr -d '[:space:]' < "$TESTDIR/port.txt" 2>/dev/null)"
        case "$port" in
            ""|*[!0-9]*) ;;
            *)  export WISP_LLM_URL="http://127.0.0.1:$port/v1/chat/completions"
                return 0 ;;
        esac
        kill -0 "$FAKE_PID" 2>/dev/null || return 1
        sleep 0.2
    done
    return 1
}

stop_fake() {
    kill "$FAKE_PID" 2>/dev/null
    wait "$FAKE_PID" 2>/dev/null
    FAKE_PID=""
    sleep 0.2
}

await_commits() { # dir want commits
    local dir="$1" want="$2"
    for _ in $(seq 1 100); do
        if [ "$(count ' commit records=' "$dir/wisp.log")" -ge "$want" ]; then
            return 0
        fi
        sleep 0.2
    done
    return 1
}

export WISP_LLM_API_KEY=fake-key

# --- case 1: a two-round turn writes two commit lines ------------------

C1=""
if start_fake tworound; then
    C1="$($WISP new --name t1 -m test-model)"
    $WISP run -d "$C1" > "$TESTDIR/out1.txt" 2> "$TESTDIR/err1.txt" <<'PROMPT1'
do the task
PROMPT1
    rc1=$?
    # Round one is [prompt, bash tool call, tool result]: records=3.
    # Round two is the stop answer: records=1.
    if [ "$rc1" -eq 0 ] \
       && [ "$(count ' commit records=3$' "$C1/wisp.log")" -eq 1 ] \
       && [ "$(count ' commit records=1$' "$C1/wisp.log")" -eq 1 ] \
       && [ "$(count ' commit records=' "$C1/wisp.log")" -eq 2 ] \
       && [ "$(count '"type": "user"' "$C1/wisp.jsonl")" -eq 1 ] \
       && [ "$(count '"type": "assistant"' "$C1/wisp.jsonl")" -eq 2 ] \
       && [ "$(count '"type": "tool"' "$C1/wisp.jsonl")" -eq 1 ] \
       && [ "$($WISP response -d "$C1")" = "the fake final answer" ]; then
        check "1: two-round turn writes two commit lines" 0
    else
        check "1: two-round turn writes two commit lines" 1
    fi
else
    check "1: two-round turn writes two commit lines" 1
fi
stop_fake

# --- case 2: a kill after round one leaves a loadable log -------

C2=""
if start_fake hang; then
    C2="$($WISP new --name t2 -m test-model)"
    printf 'do the task\n' > "$TESTDIR/prompt2.txt"
    $WISP run -d "$C2" < "$TESTDIR/prompt2.txt" \
        > "$TESTDIR/out2.txt" 2> "$TESTDIR/err2.txt" &
    RUN_PID=$!
    if await_commits "$C2" 1; then
        kill "$RUN_PID" 2>/dev/null
        wait "$RUN_PID" 2>/dev/null
        $WISP render-past -d "$C2" > "$TESTDIR/past2.txt" 2>/dev/null
        rc2=$?
        # Round one is on disk [prompt, tool call, result]; the hung
        # round two never landed: one commit line, no final answer.
        if [ "$rc2" -eq 0 ] \
           && grep -qF "[bash " "$TESTDIR/past2.txt" \
           && grep -qF "committed-round-one" "$TESTDIR/past2.txt" \
           && [ "$(count ' commit records=' "$C2/wisp.log")" -eq 1 ] \
           && ! grep -qF "fake final answer" "$C2/wisp.jsonl" \
           && [ "$(count '"type": "user"' "$C2/wisp.jsonl")" -eq 1 ] \
           && [ "$(count '"type": "tool"' "$C2/wisp.jsonl")" -eq 1 ]; then
            check "2: kill mid-turn leaves a loadable log" 0
        else
            check "2: kill mid-turn leaves a loadable log" 1
        fi
    else
        kill "$RUN_PID" 2>/dev/null
        wait "$RUN_PID" 2>/dev/null
        check "2: kill mid-turn leaves a loadable log" 1
    fi
else
    check "2: kill mid-turn leaves a loadable log" 1
fi
stop_fake

# --- case 3: a reload drops the partial trailing round -----------

# The hang cannot land a partial round on disk; a kill between the
# commit write of the assistant record and its tool records can. Craft
# that on-disk state: round one intact from case 1 plus one dangling
# assistant tool-call record, then reload and run to completion.

if start_fake default; then
    C3="$($WISP new --name t3 -m test-model)"
    python3 - "$C1/wisp.jsonl" "$C3/wisp.jsonl" <<'PYPARTIAL'
import json, sys
recs = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
user = next(r for r in recs if r.get("type") == "user")
call = next(r for r in recs if r.get("type") == "assistant"
            and any(b.get("type") == "tool_call"
                    for b in r.get("output") or []))
tool = next(r for r in recs if r.get("type") == "tool")
with open(sys.argv[2], "w") as fh:
    for rec in (user, call, tool, call):
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
PYPARTIAL
    $WISP run -d "$C3" > "$TESTDIR/out3.txt" 2> "$TESTDIR/err3.txt" <<'PROMPT3'
finish the task
PROMPT3
    rc3=$?
    if [ "$rc3" -eq 0 ] \
       && [ "$(count '"type": "tool"' "$C3/wisp.jsonl")" -eq 1 ] \
       && [ "$($WISP response -d "$C3")" = "the child answer" ]; then
        check "3: reload drops the partial trailing round" 0
    else
        check "3: reload drops the partial trailing round" 1
    fi
else
    check "3: reload drops the partial trailing round" 1
fi
stop_fake

# --- case 5: the separator law holds ------------------------------

cp "$C1/wisp.jsonl" "$TESTDIR/sep.before"
$WISP render-past -d "$C1" > "$TESTDIR/past5.txt" 2>/dev/null
rc5=$?
$WISP response -d "$C1" > "$TESTDIR/resp5.txt" 2>/dev/null
rc5b=$?
if [ "$rc5" -eq 0 ] \
   && [ "$rc5b" -eq 0 ] \
   && cmp -s "$TESTDIR/sep.before" "$C1/wisp.jsonl"; then
    check "5: separator law holds on a read-only reload" 0
else
    check "5: separator law holds on a read-only reload" 1
fi

echo "----------------------------------------"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
