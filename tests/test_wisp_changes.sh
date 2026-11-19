#!/usr/bin/env bash
# W13 request-time <environment>, W11 new -d, W7 fork, W2 run lock,
# W4 exit table, W5 status, W10 --no-stream, W12 --wallclock.
set -u
cd "$(dirname "$0")"
ROOT=$PWD
WISP="$ROOT/../wisp/wisp"
FAKE="$ROOT/fixtures/fake_llm_sse.py"
T=$(mktemp -d)
trap 'kill $SRV ${SRV2:-""} 2>/dev/null; wait $SRV $SRV2 2>/dev/null; rm -rf "$T"' EXIT
export WISP_SESSIONS_ROOT="$T/roots"
export WISP_STATE_ROOT="$T/state"
export FAKE_LLM_CAPTURE="$T/capture.jsonl"
python3 "$FAKE" 0 >"$T/port" &
SRV=$!
for _ in $(seq 1 50); do [ -s "$T/port" ] && break; sleep 0.1; done
PORT=$(cat "$T/port")
export WISP_LLM_URL="http://127.0.0.1:$PORT/v1/chat/completions"
export WISP_LLM_API_KEY=x
PASS=0; FAIL=0
check() { if [ "$2" = "$3" ]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $1 want=[$3] got=[$2]"; fi; }

# W11: new -d creates missing parents and records created/project_dir.
"$WISP" build-system-prompt --wisp --record --include-env </dev/null >"$T/p.json"
SRC=$("$WISP" new -d "$T/roots/types" --name verifier -m fake -s "$T/p.json")
check "W11 path" "$SRC" "$T/roots/types/verifier"
check "W11 parents" "$([ -d "$T/roots/types/verifier" ] && echo yes)" yes
check "W11 created" "$(python3 -c 'import json,sys;print(bool(json.load(open(sys.argv[1])).get("created")))' "$SRC/wisp.run.json")" True
check "W11 project" "$(python3 -c 'import json,sys;print(bool(json.load(open(sys.argv[1])).get("project_dir")))' "$SRC/wisp.run.json")" True
check "W13 no baked block" "$(head -1 "$SRC/wisp.jsonl" | python3 -c 'import json,sys;print(json.load(sys.stdin)["content"].startswith("<environment>"))')" False
check "W13 marker" "$(head -1 "$SRC/wisp.jsonl" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("include_env"))')" True

# W7: fork copies, fresh created, -m overrides, no record rewrite.
sleep 1
RUN=$("$WISP" fork -d "$SRC" -o "$T/roots/runs/r1" -m other)
check "W7 prints dest" "$RUN" "$T/roots/runs/r1"
check "W7 model" "$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["model"])' "$RUN/wisp.run.json")" other
check "W7 fresh created" "$(python3 -c 'import json,sys;a=json.load(open(sys.argv[1]));b=json.load(open(sys.argv[2]));print(a["created"]!=b["created"])' "$SRC/wisp.run.json" "$RUN/wisp.run.json")" True
check "W7 records copied" "$(cmp -s "$SRC/wisp.jsonl" "$RUN/wisp.jsonl"; echo $?)" 0

# W7: fork copies a per-session model table.
printf '{"fake":{"context":1000,"input":1,"output":1}}\n' >"$SRC/wisp.modelcfg"
RUN2=$("$WISP" fork -d "$SRC" -o "$T/roots/runs/r2")
check "W7 modelcfg" "$(cmp -s "$SRC/wisp.modelcfg" "$RUN2/wisp.modelcfg"; echo $?)" 0

# W1: an orphaned consumed inbox is recovered exactly once.
S4=$("$WISP" new -d "$T/roots" --name orphan -m fake -s "$T/p.json")
printf '%s\n' '{"content":"recovered steer"}' >"$S4/wisp.steer.inbox.deadbeef"
echo hi | "$WISP" run -d "$S4" --no-stream >/dev/null
check "W1 recovered" "$(grep -c wisp_steered "$S4/wisp.jsonl")" 1
check "W1 file gone" "$(ls "$S4" | grep -c 'wisp.steer.inbox')" 0
echo hi | "$WISP" run -d "$S4" --no-stream >/dev/null
check "W1 once" "$(grep -c wisp_steered "$S4/wisp.jsonl")" 1

# W13: the request renders the RUN dir, not the type dir.
: >"$T/capture.jsonl"
echo hello | "$WISP" run -d "$RUN" --no-stream
check "W13 run exit" "$?" 0
python3 - "$T/capture.jsonl" "$RUN" "$SRC" <<'PY'
import json, sys
body = json.loads(open(sys.argv[1]).read().split("\n")[0])
text = body["messages"][0]["content"]
run, src = sys.argv[2], sys.argv[3]
adult = run in text and src not in text and "MODEL: other" in text
raise SystemExit(0 if adult else 1)
PY
check "W13 render" "$?" 0
check "W13 render-past" "$("$WISP" render-past -d "$RUN" | grep -c "$RUN")" 1

# W10: --no-stream writes no data line to stdout.
OUT=$(echo hello | "$WISP" run -d "$RUN" --no-stream)
check "W10 empty stdout" "$OUT" ""

# W5 and W2: a live run holds the lock and status says so.
S2=$("$WISP" new -d "$T/roots" --name live -m fake -s "$T/p.json")
( sleep 3; echo hi ) | "$WISP" run -d "$S2" >/dev/null 2>&1 &
B=$!
sleep 0.7
check "W5 live" "$("$WISP" status -d "$S2" --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["live"])')" True
printf 'second\n' | "$WISP" run -d "$S2" >/dev/null 2>"$T/busy.err"; RC=$?
check "W2 busy exit" "$RC" 76
check "W2 busy kind" "$(grep -c 'kind=busy' "$T/busy.err")" 1
wait $B
check "W5 not live" "$("$WISP" status -d "$S2" --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["live"])')" False
check "W4 continue closed" "$("$WISP" continue -d "$S2" >/dev/null 2>&1; echo $?)" 78

# W12: the wall clock exits 124 and keeps the finished rounds.
python3 "$FAKE" 0 hang >"$T/port2" &
SRV2=$!
for _ in $(seq 1 50); do [ -s "$T/port2" ] && break; sleep 0.1; done
PORT2=$(cat "$T/port2")
export WISP_LLM_URL="http://127.0.0.1:$PORT2/v1/chat/completions"
S3=$("$WISP" new -d "$T/roots" --name wall -m fake -s "$T/p.json")
START=$(date +%s)
echo hi | "$WISP" run -d "$S3" --wallclock 3 >/dev/null 2>"$T/wall.err"; RC=$?
END=$(date +%s)
check "W12 exit" "$RC" 124
check "W12 prompt" "$([ $((END-START)) -le 6 ] && echo yes)" yes
check "W12 committed" "$(grep -c 'commit records=' "$S3/wisp.log" | awk '$1>=1{print "yes"}')" yes
kill $SRV2 2>/dev/null
wait $SRV2 2>/dev/null

echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
