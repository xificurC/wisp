#!/usr/bin/env bash
# Tests for the wisp project registry: all eleven cases.
# No LLM traffic: these cases run wisp new and read-only commands only.
# Usage: bash tests/test_wisp_registry.sh

set -u

WISP="$(cd "$(dirname "$0")/.." && pwd)/wisp/wisp"

TESTDIR="$(mktemp -d)"
trap 'chmod -R u+w "$TESTDIR" 2>/dev/null; rm -rf "$TESTDIR"' EXIT
export WISP_SESSIONS_ROOT="$TESTDIR/sessions"
export WISP_STATE_ROOT="$TESTDIR/state"
unset XDG_STATE_HOME 2>/dev/null

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

# The expected link name: the real path of the sessions root with
# every / as __, cut to the last 255 bytes.
link_name() {
    python3 - "$1" <<'PY'
import os, sys
r = os.path.realpath(sys.argv[1])
d = r.replace("/", "__").encode("utf-8")
print(d[-255:].decode("utf-8", "ignore"))
PY
}

real_path() {
    python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

count_links() {
    find "$1" -mindepth 1 -maxdepth 1 -type l 2>/dev/null | wc -l
}

link_stamp() {
    python3 -c 'import os, sys; print(os.lstat(sys.argv[1]).st_mtime_ns)' "$1"
}

# --- case 1: one link with the link name and target ----------------------

P1="$($WISP new --name one -m test-model)"
R1="$(real_path "$WISP_SESSIONS_ROOT")"
L1="$WISP_STATE_ROOT/$(link_name "$WISP_SESSIONS_ROOT")"
if [ -L "$L1" ] \
   && [ "$(readlink "$L1")" = "$R1" ] \
   && [ "$(count_links "$WISP_STATE_ROOT")" -eq 1 ] \
   && [ "$P1" = "$WISP_SESSIONS_ROOT/one" ]; then
    check "1: one link with the link name and target" 0
else
    check "1: one link with the link name and target" 1
fi

# --- case 2: a second new in the same project leaves one link -------------

$WISP new --name two -m test-model > /dev/null
if [ -L "$L1" ] \
   && [ "$(readlink "$L1")" = "$R1" ] \
   && [ "$(count_links "$WISP_STATE_ROOT")" -eq 1 ]; then
    check "2: second new leaves one link in the same project" 0
else
    check "2: second new leaves one link in the same project" 1
fi

# --- case 3: two projects, two links --------------------------------------

SR3A="$TESTDIR/proja/sessions"
SR3B="$TESTDIR/projb/sessions"
STATE3="$TESTDIR/state3"
mkdir -p "$STATE3"
env WISP_SESSIONS_ROOT="$SR3A" WISP_STATE_ROOT="$STATE3" \
    $WISP new --name three-a -m test-model > /dev/null
env WISP_SESSIONS_ROOT="$SR3B" WISP_STATE_ROOT="$STATE3" \
    $WISP new --name three-b -m test-model > /dev/null
if [ -L "$STATE3/$(link_name "$SR3A")" ] \
   && [ "$(readlink "$STATE3/$(link_name "$SR3A")")" = "$(real_path "$SR3A")" ] \
   && [ -L "$STATE3/$(link_name "$SR3B")" ] \
   && [ "$(readlink "$STATE3/$(link_name "$SR3B")")" = "$(real_path "$SR3B")" ] \
   && [ "$(count_links "$STATE3")" -eq 2 ]; then
    check "3: two projects get two links, one per sessions root" 0
else
    check "3: two projects get two links, one per sessions root" 1
fi

# --- case 4: a slash-heavy path encodes every / as __ ---------------------

SR4="$TESTDIR/a/b/c/d/e/f/sessions"
STATE4="$TESTDIR/state4"
mkdir -p "$STATE4"
env WISP_SESSIONS_ROOT="$SR4" WISP_STATE_ROOT="$STATE4" \
    $WISP new --name four -m test-model > /dev/null
L4="$STATE4/$(link_name "$SR4")"
NAME4="$(basename "$L4")"
if [ -L "$L4" ] \
   && [ "$(readlink "$L4")" = "$(real_path "$SR4")" ] \
   && grep -q "__" <<< "$NAME4" \
   && [ "$(count_links "$STATE4")" -eq 1 ]; then
    check "4: slash-heavy path encodes every / as __" 0
else
    check "4: slash-heavy path encodes every / as __" 1
fi

# --- case 5: a name over 255 bytes keeps the last 255 bytes ---------------

SEG="$(printf 'x%.0s' $(seq 1 60))"
SR5="$TESTDIR/deep/$SEG/$SEG/$SEG/$SEG/$SEG/sessions"
STATE5="$TESTDIR/state5"
mkdir -p "$STATE5"
LONG5="$(python3 - "$SR5" <<'PY'
import os, sys
r = os.path.realpath(sys.argv[1])
d = r.replace("/", "__").encode("utf-8")
ok = len(d) > 255
print("yes" if ok else "no")
PY
)"
env WISP_SESSIONS_ROOT="$SR5" WISP_STATE_ROOT="$STATE5" \
    $WISP new --name five -m test-model > /dev/null
L5="$STATE5/$(link_name "$SR5")"
if [ "$LONG5" = "yes" ] \
   && [ "$(basename "$L5" | wc -c)" -eq 256 ] \
   && [ -L "$L5" ] \
   && [ "$(readlink "$L5")" = "$(real_path "$SR5")" ]; then
    check "5: a name over 255 bytes keeps the last 255 bytes" 0
else
    check "5: a name over 255 bytes keeps the last 255 bytes" 1
fi

# --- case 6: an existing link with the same target stays untouched --------

SR6="$TESTDIR/sessions6"
STATE6="$TESTDIR/state6"
mkdir -p "$STATE6" "$SR6"
L6="$STATE6/$(link_name "$SR6")"
ln -sfn "$(real_path "$SR6")" "$L6"
touch -h -d "2001-02-03 04:05:06" "$L6" 2>/dev/null
B6="$(link_stamp "$L6")"
env WISP_SESSIONS_ROOT="$SR6" WISP_STATE_ROOT="$STATE6" \
    $WISP new --name six -m test-model > /dev/null
A6="$(link_stamp "$L6")"
if [ -L "$L6" ] \
   && [ "$(readlink "$L6")" = "$(real_path "$SR6")" ] \
   && [ "$A6" = "$B6" ]; then
    check "6: same-target link stays untouched" 0
else
    check "6: same-target link stays untouched" 1
fi

# --- case 7: an existing link with a different target is replaced ---------

SR7="$TESTDIR/sessions7"
STATE7="$TESTDIR/state7"
mkdir -p "$STATE7"
L7="$STATE7/$(link_name "$SR7")"
ln -sfn "$TESTDIR/elsewhere" "$L7"
env WISP_SESSIONS_ROOT="$SR7" WISP_STATE_ROOT="$STATE7" \
    $WISP new --name seven -m test-model > /dev/null
if [ -L "$L7" ] \
   && [ "$(readlink "$L7")" = "$(real_path "$SR7")" ]; then
    check "7: different-target link is replaced" 0
else
    check "7: different-target link is replaced" 1
fi

# --- case 8: a read-only root warns; the session still lands --------------

SR8="$TESTDIR/sessions8"
STATE8="$TESTDIR/state8"
mkdir -p "$STATE8"
chmod 555 "$STATE8"
env WISP_SESSIONS_ROOT="$SR8" WISP_STATE_ROOT="$STATE8" \
    $WISP new --name eight -m test-model \
    > "$TESTDIR/out8.txt" 2> "$TESTDIR/err8.txt"
rc8=$?
if [ "$rc8" -eq 0 ] \
   && [ "$(cat "$TESTDIR/out8.txt")" = "$SR8/eight" ] \
   && [ "$(wc -l < "$TESTDIR/err8.txt")" -eq 1 ] \
   && grep -q "^wisp: warning: registry: " "$TESTDIR/err8.txt"; then
    check "8: read-only root warns, exits 0, path still printed" 0
else
    check "8: read-only root warns, exits 0, path still printed" 1
fi

# --- case 9: XDG_STATE_HOME sets the root when WISP_STATE_ROOT is unset ---

SR9="$TESTDIR/sessions9"
env -u WISP_STATE_ROOT WISP_SESSIONS_ROOT="$SR9" \
    XDG_STATE_HOME="$TESTDIR/xdg" \
    $WISP new --name nine -m test-model > /dev/null
XDGR="$TESTDIR/xdg/wisp-sessions"
if [ -L "$XDGR/$(link_name "$SR9")" ] \
   && [ "$(readlink "$XDGR/$(link_name "$SR9")")" = "$(real_path "$SR9")" ] \
   && [ "$(count_links "$XDGR")" -eq 1 ] \
   && [ ! -e "$WISP_STATE_ROOT/$(link_name "$SR9")" ]; then
    check "9: XDG_STATE_HOME sets the root without WISP_STATE_ROOT" 0
else
    check "9: XDG_STATE_HOME sets the root without WISP_STATE_ROOT" 1
fi

# --- case 10: WISP_STATE_ROOT wins over XDG_STATE_HOME --------------------

SR10="$TESTDIR/sessions10"
env WISP_SESSIONS_ROOT="$SR10" WISP_STATE_ROOT="$TESTDIR/ten" \
    XDG_STATE_HOME="$TESTDIR/xdg10" \
    $WISP new --name ten -m test-model > /dev/null
if [ -L "$TESTDIR/ten/$(link_name "$SR10")" ] \
   && [ "$(readlink "$TESTDIR/ten/$(link_name "$SR10")")" = "$(real_path "$SR10")" ] \
   && [ "$(count_links "$TESTDIR/ten")" -eq 1 ] \
   && [ ! -e "$TESTDIR/xdg10/wisp-sessions" ]; then
    check "10: WISP_STATE_ROOT wins over XDG_STATE_HOME" 0
else
    check "10: WISP_STATE_ROOT wins over XDG_STATE_HOME" 1
fi

# --- case 11: read-only commands create no link ---------------------------
# The read-only commands are run, ls, grep, render-past, usage,
# response, skill ls, and agents-md ls.

SR11="$TESTDIR/sessions11"
P11="$(env WISP_SESSIONS_ROOT="$SR11" WISP_STATE_ROOT="$TESTDIR/state11a" \
    $WISP new --name eleven -m test-model)"
STATE11="$TESTDIR/state11"
env WISP_SESSIONS_ROOT="$SR11" WISP_STATE_ROOT="$STATE11" \
    $WISP run -d "$P11" < /dev/null > /dev/null 2>&1
env WISP_SESSIONS_ROOT="$SR11" WISP_STATE_ROOT="$STATE11" \
    $WISP render-past -d "$P11" < /dev/null > /dev/null 2>&1
env WISP_SESSIONS_ROOT="$SR11" WISP_STATE_ROOT="$STATE11" \
    $WISP usage -d "$P11" > /dev/null 2>&1
env WISP_SESSIONS_ROOT="$SR11" WISP_STATE_ROOT="$STATE11" \
    $WISP response -d "$P11" > /dev/null 2>&1
( cd "$TESTDIR" && env WISP_STATE_ROOT="$STATE11" $WISP skill ls > /dev/null 2>&1 )
( cd "$TESTDIR" && env WISP_STATE_ROOT="$STATE11" $WISP agents-md ls > /dev/null 2>&1 )
if [ "$(count_links "$STATE11")" -eq 0 ] \
   && [ ! -e "$STATE11/$(link_name "$SR11")" ]; then
    check "11: run, render-past, usage, response, ls create no link" 0
else
    check "11: run, render-past, usage, response, ls create no link" 1
fi

echo "----------------------------------------"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
