#!/usr/bin/env bash
# Tests for wisp new --parent: the two-way session linkage.
# Cases 1-6 plus the not-a-list case.
# No LLM traffic: these cases run wisp new only.
# Usage: bash tests/test_wisp_sub_recipe.sh

set -u

WISP="$(cd "$(dirname "$0")/.." && pwd)/wisp/wisp"

TESTDIR="$(mktemp -d)"
SERVER_PID=""
trap 'kill "$SERVER_PID" 2>/dev/null; chmod -R u+w "$TESTDIR" 2>/dev/null; rm -rf "$TESTDIR"' EXIT
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

# --- case 1: the child setup carries the real parent path ----------------

P1="$($WISP new --name parent1 -m test-model)"
C1="$($WISP new --name child1 -m test-model --parent "$P1")"
python3 - "$C1/wisp.run.json" "$P1" <<'PY'
import json, os, sys
try:
    setup = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    sys.exit(1)
sys.exit(0 if setup.get("parent") == os.path.realpath(sys.argv[2]) else 1)
PY
check "1: child setup carries the real parent path" "$?"

# --- case 2: the child id lands under children; earlier keys survive -----

P2="$($WISP new --name parent2 -m test-model -t high)"
C2="$($WISP new --name child2 -m test-model --parent "$P2")"
python3 - "$P2/wisp.run.json" "$C2/wisp.run.json" "$P2" <<'PY'
import json, os, sys
try:
    parent = json.load(open(sys.argv[1]))
    child = json.load(open(sys.argv[2]))
except (OSError, ValueError):
    sys.exit(1)
ok = (parent.get("model") == "test-model"
      and parent.get("thinking") == "high"
      and parent.get("children") == ["child2"]
      and child.get("parent") == os.path.realpath(sys.argv[3]))
sys.exit(0 if ok else 1)
PY
check "2: child id under children; parent keys survive" "$?"

# --- case 3: a second child appends ---------------------------------------

$WISP new --name child3 -m test-model --parent "$P2" > /dev/null
python3 - "$P2/wisp.run.json" <<'PY'
import json, sys
try:
    parent = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    sys.exit(1)
sys.exit(0 if parent.get("children") == ["child2", "child3"] else 1)
PY
check "3: second child appends to children" "$?"

# --- case 4: an invalid parent fails cleanly, before any dir is made -----

mkdir -p "$TESTDIR/bare" "$TESTDIR/half"
: > "$TESTDIR/half/wisp.jsonl"
for bad in "$TESTDIR/nope" "$TESTDIR/bare" "$TESTDIR/half"; do
    $WISP new --name badchild -m test-model --parent "$bad" \
        > "$TESTDIR/out4.txt" 2> "$TESTDIR/err4.txt"
    rc=$?
    lines="$(wc -l < "$TESTDIR/err4.txt")"
    if [ "$rc" -ne 0 ] && [ "$lines" -eq 1 ] \
       && grep -q "^wisp: " "$TESTDIR/err4.txt" \
       && [ ! -e "$WISP_SESSIONS_ROOT/badchild" ]; then
        check "4: invalid parent rejected cleanly: $bad" 0
    else
        check "4: invalid parent rejected cleanly: $bad" 1
    fi
done

# --- case 5: a parent update failure warns; the child still lands --------

P5="$($WISP new --name parent5 -m test-model)"
cp "$P5/wisp.run.json" "$TESTDIR/p5.before"
chmod 444 "$P5/wisp.run.json"
$WISP new --name child5 -m test-model --parent "$P5" \
    > "$TESTDIR/out5.txt" 2> "$TESTDIR/err5.txt"
rc=$?
chmod 644 "$P5/wisp.run.json"
if [ "$rc" -eq 0 ] \
   && [ "$(cat "$TESTDIR/out5.txt")" = "$WISP_SESSIONS_ROOT/child5" ] \
   && grep -q "warning: cannot update children" "$TESTDIR/err5.txt" \
   && cmp -s "$TESTDIR/p5.before" "$P5/wisp.run.json" \
   && grep -q '"parent"' "$WISP_SESSIONS_ROOT/child5/wisp.run.json"; then
    check "5: parent update failure warns; child still lands" 0
else
    check "5: parent update failure warns; child still lands" 1
fi

# --- case 6: a plain new writes no parent and changes no other session dir ---

$WISP new --name plain6 -m test-model > "$TESTDIR/out6.txt"
python3 - "$WISP_SESSIONS_ROOT/plain6/wisp.run.json" "$P2/wisp.run.json" <<'PY'
import json, sys
try:
    plain = json.load(open(sys.argv[1]))
    parent = json.load(open(sys.argv[2]))
except (OSError, ValueError):
    sys.exit(1)
ok = ("parent" not in plain
      and parent.get("model") == "test-model"
      and parent.get("thinking") == "high"
      and parent.get("children") == ["child2", "child3"])
sys.exit(0 if ok else 1)
PY
check "6: plain new writes no parent; other session dirs unchanged" "$?"

# --- not-a-list: a children value link_child cannot understand -----------

P8="$($WISP new --name parent8 -m test-model)"
printf '{"children": "oops", "model": "test-model"}\n' > "$P8/wisp.run.json"
cp "$P8/wisp.run.json" "$TESTDIR/p8.before"
$WISP new --name child8 -m test-model --parent "$P8" \
    > "$TESTDIR/out8.txt" 2> "$TESTDIR/err8.txt"
rc=$?
if [ "$rc" -eq 0 ] \
   && grep -q "children is not a list" "$TESTDIR/err8.txt" \
   && cmp -s "$TESTDIR/p8.before" "$P8/wisp.run.json" \
   && grep -q '"parent"' "$WISP_SESSIONS_ROOT/child8/wisp.run.json"; then
    check "nl: children not a list warns; parent file stays identical" 0
else
    check "nl: children not a list warns; parent file stays identical" 1
fi

# --- case 7: the recipe end to end, stream law included ------------------

FIXTURE="$(cd "$(dirname "$0")" && pwd)/fixtures/fake_llm_sse.py"
python3 "$FIXTURE" > "$TESTDIR/port7.txt" &
SERVER_PID=$!
port=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if [ -s "$TESTDIR/port7.txt" ]; then
        port="$(tr -d '[:space:]' < "$TESTDIR/port7.txt")"
        break
    fi
    sleep 0.3
done
if [ -z "$port" ]; then
    check "7: recipe runs verbatim; stream law holds" 1
else
    export WISP_LLM_URL="http://127.0.0.1:$port/v1/chat/completions"
    export WISP_LLM_API_KEY=fake-key
    P7="$($WISP new --name parent7 -m test-model)"
    (
        CHILD="$($WISP new --name sub7 -m test-model --parent "$P7")"
        $WISP run -d "$CHILD" > /dev/null <<'EOF'
do the task
EOF
        $WISP response -d "$CHILD"
    ) > "$TESTDIR/recipe7.out" 2> "$TESTDIR/recipe7.err"
    python3 - "$TESTDIR/recipe7.out" "$WISP_SESSIONS_ROOT/sub7/wisp.jsonl" \
        "$P7/wisp.run.json" <<'PY'
import json, sys
try:
    out = open(sys.argv[1]).read()
    records = [json.loads(line) for line in open(sys.argv[2]) if line.strip()]
    parent = json.load(open(sys.argv[3]))
except (OSError, ValueError):
    sys.exit(1)
ok = ("the child answer" in out
      and "data:" not in out
      and any(r.get("type") == "user" for r in records)
      and any(r.get("type") == "assistant" for r in records)
      and parent.get("children") == ["sub7"])
sys.exit(0 if ok else 1)
PY
    check "7: recipe runs verbatim; stream law holds" "$?"
fi
kill "$SERVER_PID" 2>/dev/null
SERVER_PID=""

# --- case 8: the wisp block teaches the recipe ---------------------------

$WISP build-system-prompt --wisp < /dev/null > "$TESTDIR/block8.txt" 2>/dev/null
if grep -q "^SUBAGENTS$" "$TESTDIR/block8.txt" \
   && grep -qF 'wisp run -d "$CHILD" --context-guard 70% > "$CHILD/wisp.stream"' "$TESTDIR/block8.txt" \
   && grep -qF 'tail -f "$CHILD/wisp.stream" | wisp render-live' "$TESTDIR/block8.txt" \
   && grep -qF 'wisp response -d "$CHILD"' "$TESTDIR/block8.txt" \
   && grep -qF -- "--parent" "$TESTDIR/block8.txt" \
   && grep -qF "prompt.txt" "$TESTDIR/block8.txt" \
   && grep -qF -- "--tree" "$TESTDIR/block8.txt" \
   && grep -qF -- "--name" "$TESTDIR/block8.txt" \
   && grep -qF "never export WISP_SESSION_DIR" "$TESTDIR/block8.txt" \
   && grep -qF "open-ended" "$TESTDIR/block8.txt" \
   && grep -qF -- "wisp skill read SKILL" "$TESTDIR/block8.txt" \
   && grep -qF -- "--env-in-system-prompt" "$TESTDIR/block8.txt" \
   && grep -qF -- "--context-guard 70%" "$TESTDIR/block8.txt" \
   && grep -qF -- "--skills --agents-md" "$TESTDIR/block8.txt"; then
    check "8: wisp block teaches the recipe" 0
else
    check "8: wisp block teaches the recipe" 1
fi

echo "----------------------------------------"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
