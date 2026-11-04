#!/usr/bin/env bash
# Tests for wisp ls and wisp grep.
# Cases 1-18, plus the accepted strict-parsing extras. Sessions are
# hand-written session dirs (wisp.jsonl plus wisp.run.json); the children
# lists in wisp.run.json are hand-written for the tree cases. The
# caller may export WISP_SESSION_DIR; the script unsets it up front or the
# no-d failure of case 11 would bind the caller's session instead of
# failing.
# Usage: bash tests/test_wisp_ls_grep.sh

set -u

WISP="$(cd "$(dirname "$0")/.." && pwd)/wisp/wisp"

TESTDIR="$(mktemp -d)"
trap 'chmod -R u+w "$TESTDIR" 2>/dev/null; rm -rf "$TESTDIR"' EXIT

unset WISP_SESSION_DIR

pass=0
fail=0

check() {
    if [ "$2" = "$3" ]; then
        echo "PASS: $1"
        pass=$((pass + 1))
    else
        echo "FAIL: $1"
        echo "  want: $3"
        echo "  got: $2"
        fail=$((fail + 1))
    fi
}

matches() {  # pattern text -> grep -E -c, 0 on no match
    if [ $# -eq 2 ] && [ -n "$2" ]; then
        printf '%s\n' "$2" | grep -Ec "$1"
    else
        echo 0
    fi
}

# A session dir with a model in wisp.run.json; the jsonl text is one
# record per line. An empty model argument skips wisp.run.json.
mk_session() {  # dir model jsonl_text
    mkdir -p "$1"
    printf '%s\n' "$3" > "$1/wisp.jsonl"
    if [ -n "$2" ]; then
        printf '{"model": "%s"}\n' "$2" > "$1/wisp.run.json"
    fi
}

# One user, one assistant (reasoning excluded from search), one tool.
U='{"type": "user", "content": "please audit the logs"}'
A='{"type": "assistant", "output": [{"type": "reasoning", "text": "secret zebra reasoning"}, {"type": "text", "text": "the logs look clean"}]}'
T='{"type": "tool", "call_id": "call_1", "content": "grep LOGS done"}'
RECORDS="$U
$A
$T"

ROOT="$TESTDIR/sessions"
STATE="$TESTDIR/state"
export WISP_SESSIONS_ROOT="$ROOT"
export WISP_STATE_ROOT="$STATE"

# --- case 1: project scope, newest first, line format -------------

mk_session "$ROOT/old" old-model '{"type": "user", "content": "old text"}'
mk_session "$ROOT/new" new-model '{"type": "user", "content": "new text"}'
touch -d '2000-01-01' "$ROOT/old/wisp.jsonl"

OUT="$("$WISP" ls 2>"$TESTDIR/e1")"; RC=$?
check "case 1: exits 0" "$RC" "0"
check "case 1: two lines" "$(printf '%s\n' "$OUT" | wc -l)" "2"
check "case 1: newest first" "$(printf '%s\n' "$OUT" | head -1 | cut -d' ' -f1)" "$ROOT/new"
check "case 1: oldest second" "$(printf '%s\n' "$OUT" | sed -n 2p | cut -d' ' -f1)" "$ROOT/old"
check "case 1: line format" \
    "$(matches "$ROOT/new model=new-model records=1 last=[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\$" "$OUT")" "1"

# --- case 2: project scope rejects -d ------------------------------

OUT="$("$WISP" ls -d "$ROOT/new" 2>"$TESTDIR/e2")"; RC=$?
check "case 2: -d without --tree fails" "$RC" "1"
check "case 2: one stderr line" "$(wc -l <"$TESTDIR/e2")" "1"
check "case 2: stderr names -d" "$(matches 'works only with --tree' "$(cat "$TESTDIR/e2")")" "1"

# --- case 3: WISP_SESSIONS_ROOT moves the project scope -------------------

mk_session "$TESTDIR/other/other" other-model '{"type": "user", "content": "other text"}'
OUT="$(WISP_SESSIONS_ROOT="$TESTDIR/other" "$WISP" ls 2>/dev/null)"
check "case 3: other root listed" "$(printf '%s\n' "$OUT" | cut -d' ' -f1)" "$TESTDIR/other/other"
check "case 3: default root absent" "$(matches "$ROOT" "$OUT")" "0"

# --- case 4: global scope over two registered roots ----------------

RA="$TESTDIR/proja"
RB="$TESTDIR/projb"
mk_session "$RA/a1" ma "$RECORDS"
mk_session "$RB/b1" mb '{"type": "user", "content": "b text"}'
touch -d '2000-06-01' "$RB/b1/wisp.jsonl"
mkdir -p "$STATE"
ln -s "$ROOT" "$STATE/link-root"
ln -s "$RA" "$STATE/link-a"
ln -s "$RB" "$STATE/link-b"

OUT="$("$WISP" ls --global 2>"$TESTDIR/e4")"; RC=$?
check "case 4: global ls exits 0" "$RC" "0"
check "case 4: all four sessions" "$(printf '%s\n' "$OUT" | wc -l)" "4"
check "case 4: newest first overall" \
    "$(printf '%s\n' "$OUT" | head -1 | cut -d' ' -f1)" "$RA/a1"

# --- case 5: dead link and wisp.jsonl-less dir print nothing --------------

ln -s "$TESTDIR/noproject" "$STATE/link-dead"
mkdir -p "$STATE/label"
check "case 5: dead link and plain dir skipped" "$("$WISP" ls --global 2>/dev/null | wc -l)" "4"
mkdir -p "$RA/empty-session"
printf '# log line\n' > "$RA/empty-session/wisp.log"
check "case 5: session dir without wisp.jsonl skipped" \
    "$(matches 'empty-session' "$("$WISP" ls --global 2>/dev/null)")" "0"

# --- case 6: missing registry root exits 0 with no output -----------------

OUT="$(WISP_STATE_ROOT="$TESTDIR/absent" "$WISP" ls --global 2>"$TESTDIR/e6")"; RC=$?
check "case 6: exits 0" "$RC" "0"
check "case 6: no output" "-$OUT-" "--"
check "case 6: no stderr" "$(wc -l <"$TESTDIR/e6")" "0"

# --- case 7: missing wisp.run.json renders model=? -----------------

mk_session "$ROOT/bare" "" '{"type": "user", "content": "bare text"}'
OUT="$("$WISP" ls 2>/dev/null)"
check "case 7: still listed" "$(matches "^$ROOT/bare " "$OUT")" "1"
check "case 7: model=?" "$(matches "^$ROOT/bare model=\\? records=1 last=" "$OUT")" "1"

# --- case 8: tree scope lists parent, children, grandchild ---------

TR="$TESTDIR/tree"
mk_session "$TR/p" mp '{"type": "user", "content": "p audit text"}'
printf '{"model": "mp", "children": ["c1", "c2"]}\n' > "$TR/p/wisp.run.json"
mk_session "$TR/c1" mc1 '{"type": "user", "content": "c1 audit text"}'
printf '{"model": "mc1", "children": ["gc"]}\n' > "$TR/c1/wisp.run.json"
mk_session "$TR/c2" mc2 '{"type": "user", "content": "c2 audit text"}'
mk_session "$TR/gc" mgc '{"type": "user", "content": "gc audit text"}'

OUT="$("$WISP" ls --tree -d "$TR/p" 2>"$TESTDIR/e8")"; RC=$?
check "case 8: exits 0" "$RC" "0"
check "case 8: four session dirs" "$(printf '%s\n' "$OUT" | wc -l)" "4"
for d in p c1 c2 gc; do
    check "case 8: $d listed" "$(matches "^$TR/$d model=" "$OUT")" "1"
done
OUT="$(WISP_SESSION_DIR="$TR/p" "$WISP" ls --tree 2>/dev/null)"
check "case 8: WISP_SESSION_DIR binds --tree" "$(printf '%s\n' "$OUT" | wc -l)" "4"

# --- case 9: a missing child id is skipped with no output ------------------

printf '{"model": "mp", "children": ["c1", "c2", "ghost"]}\n' > "$TR/p/wisp.run.json"
OUT="$("$WISP" ls --tree -d "$TR/p" 2>"$TESTDIR/e9")"; RC=$?
check "case 9: exits 0" "$RC" "0"
check "case 9: still four" "$(printf '%s\n' "$OUT" | wc -l)" "4"
check "case 9: no stderr" "$(wc -l <"$TESTDIR/e9")" "0"

# --- case 10: a cycle terminates through the visited set -------------------

CY="$TESTDIR/cycle"
mk_session "$CY/a" ma '{"type": "user", "content": "a text"}'
printf '{"model": "ma", "children": ["b"]}\n' > "$CY/a/wisp.run.json"
mk_session "$CY/b" mb '{"type": "user", "content": "b text"}'
printf '{"model": "mb", "children": ["a"]}\n' > "$CY/b/wisp.run.json"

OUT="$(timeout 20 "$WISP" ls --tree -d "$CY/a" 2>"$TESTDIR/e10")"; RC=$?
check "case 10: cycle terminates, exits 0" "$RC" "0"
check "case 10: both members" "$(printf '%s\n' "$OUT" | wc -l)" "2"
check "case 10: no stderr" "$(wc -l <"$TESTDIR/e10")" "0"

# --- case 11: --tree without -d and WISP_SESSION_DIR fails ---------------

OUT="$("$WISP" ls --tree 2>"$TESTDIR/e11")"; RC=$?
check "case 11: fails" "$RC" "1"
check "case 11: one stderr line" "$(wc -l <"$TESTDIR/e11")" "1"
check "case 11: resolve_rundir message shape" \
    "$(matches 'pass -d DIR, or set WISP_SESSION_DIR' "$(cat "$TESTDIR/e11")")" "1"

# --- case 12: --global --tree together fails -------------------------

OUT="$("$WISP" ls --global --tree -d "$TR/p" 2>"$TESTDIR/e12")"; RC=$?
check "case 12: fails" "$RC" "1"
check "case 12: one stderr line" "$(wc -l <"$TESTDIR/e12")" "1"

# --- case 13: grep finds a user match in all three scopes ------------

mk_session "$ROOT/gjob" gmodel "$RECORDS"

OUT="$("$WISP" grep audit 2>"$TESTDIR/e13")"; RC=$?
check "case 13: project grep exits 0" "$RC" "0"
check "case 13: session dir, record n, type" \
    "$(matches "^$ROOT/gjob 1 user: please audit the logs\$" "$OUT")" "1"
check "case 13: only the matching record" "$(printf '%s\n' "$OUT" | wc -l)" "1"

OUT="$(WISP_STATE_ROOT="$STATE" "$WISP" grep audit --global 2>/dev/null)"; RC=$?
check "case 13: global scope finds it" "$RC" "0"
check "case 13: global matches both roots" "$(printf '%s\n' "$OUT" | wc -l)" "2"

OUT="$("$WISP" grep audit --tree -d "$TR/p" 2>/dev/null)"; RC=$?
check "case 13: tree scope finds it" "$RC" "0"
check "case 13: tree matches the subtree" "$(printf '%s\n' "$OUT" | wc -l)" "4"

# --- case 14: -i matches across case ---------------------------------

check "case 14: case-sensitive misses" "$("$WISP" grep AUDIT >/dev/null 2>&1; echo $?)" "1"
OUT="$("$WISP" grep AUDIT -i 2>/dev/null)"
check "case 14: -i hits" "$(matches 'user: please audit the logs' "$OUT")" "1"

# --- case 15: reasoning blocks are not searched ----------------------

OUT="$("$WISP" grep zebra 2>"$TESTDIR/e15")"; RC=$?
check "case 15: reasoning excluded, exit 1" "$RC" "1"
check "case 15: no output" "-$OUT-" "--"
OUT="$("$WISP" grep 'logs look clean' 2>/dev/null)"; RC=$?
check "case 15: text block still searched, exit 0" "$RC" "0"
check "case 15: assistant line drops reasoning" \
    "$(matches "^$ROOT/gjob 2 assistant: the logs look clean\$" "$OUT")" "1"

# --- case 16: tool content is searched -------------------------------

OUT="$("$WISP" grep 'LOGS done' 2>/dev/null)"; RC=$?
check "case 16: tool record matched, exit 0" "$RC" "0"
check "case 16: record number 3" \
    "$(matches "^$ROOT/gjob 3 tool: grep LOGS done\$" "$OUT")" "1"

# --- case 17: no matches exits 1 with no output ----------------------

OUT="$("$WISP" grep definitely-absent 2>"$TESTDIR/e17")"; RC=$?
check "case 17: exit 1" "$RC" "1"
check "case 17: no output" "-$OUT-" "--"
check "case 17: no stderr" "$(wc -l <"$TESTDIR/e17")" "0"

# --- case 18: an invalid pattern fails with one stderr line ----------

OUT="$("$WISP" grep '[' 2>"$TESTDIR/e18")"; RC=$?
check "case 18: fails" "$RC" "1"
check "case 18: no output" "-$OUT-" "--"
check "case 18: one stderr line" "$(wc -l <"$TESTDIR/e18")" "1"
check "case 18: stderr names the pattern" \
    "$(matches 'invalid pattern' "$(cat "$TESTDIR/e18")")" "1"

# --- accepted extras: strict parsing, read-only corpus discipline -----------

OUT="$("$WISP" ls -i 2>"$TESTDIR/x1")"; RC=$?
check "ls -i rejected (P2)" "$RC" "1"
check "ls -i: one stderr line" "$(wc -l <"$TESTDIR/x1")" "1"
check "grep without PATTERN rejected" "$("$WISP" grep >/dev/null 2>&1; echo $?)" "1"
check "ls with a positional rejected" "$("$WISP" ls extra >/dev/null 2>&1; echo $?)" "1"
check "grep --tree without session dir rejected" "$("$WISP" grep --tree x >/dev/null 2>&1; echo $?)" "1"
check "-d needs a value" "$("$WISP" ls --tree -d >/dev/null 2>&1; echo $?)" "1"

# --- piped out: the reader closes the pipe ----------------------------------

# A CLI built to be piped must die cleanly when the reader goes away:
# one line reaches head, ls exits 141 (128 + SIGPIPE), and no traceback
# lands on stderr. The ~1500 seeded sessions outweigh the 64kB pipe
# buffer, so the BrokenPipeError path is exercised for real.

python3 - "$ROOT" <<'PYSEEDED'
import os, sys
root = sys.argv[1]
for i in range(1500):
    d = os.path.join(root, "bulk-%06d" % i)
    os.mkdir(d)
    with open(os.path.join(d, "wisp.jsonl"), "w") as f:
        f.write('{"type": "user", "content": "bulk text"}\n')
    with open(os.path.join(d, "wisp.run.json"), "w") as f:
        f.write('{"model": "model-%06d"}\n' % i)
PYSEEDED

"$WISP" ls 2>"$TESTDIR/bp.err" | head -1 >"$TESTDIR/bp.head"
LS_RC=${PIPESTATUS[0]}
check "pipe closed: one line reaches head" "$(wc -l <"$TESTDIR/bp.head")" "1"
check "pipe closed: ls exits 141" "$LS_RC" "141"
check "pipe closed: no traceback on stderr" \
    "$(grep -c Traceback "$TESTDIR/bp.err")" "0"
check "pipe closed: stderr empty" "$(wc -c <"$TESTDIR/bp.err")" "0"

echo
echo "PASS=$pass FAIL=$fail"
[ "$fail" = "0" ]
