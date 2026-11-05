#!/usr/bin/env bash
# Test runner for tikit-ticket. Runs all test cases from the spec.
set -u
SCRIPT="$(cd "$(dirname "$0")" && pwd)/tikit"
PASS=0
FAIL=0
FAILED_TESTS=""

run() {
    # run "name" "command" -- executes command, sets RC and OUT
    name="$1"; shift
    OUT="$("$@" 2>/tmp/tikit.err)"; RC=$?
    ERR=$(cat /tmp/tikit.err 2>/dev/null)
}

check() {
    # check "name" "condition"
    local name="$1" cond="$2"
    if eval "$cond"; then
        PASS=$((PASS+1))
        # echo "PASS: $name"
    else
        FAIL=$((FAIL+1))
        FAILED_TESTS="$FAILED_TESTS\n  - $name"
        echo "FAIL: $name"
        echo "    cond: $cond"
    fi
}

echo "=== bash32 / static ==="
grep -nE 'declare[[:space:]]+-A|mapfile|readarray' "$SCRIPT" >/tmp/tikit_g1 || true
grep -nE '\$\{[A-Za-z_][A-Za-z0-9_]*[,^]' "$SCRIPT" >/tmp/tikit_g2 || true
check "bash32_no_forbidden" "[ ! -s /tmp/tikit_g1 ] && [ ! -s /tmp/tikit_g2 ]"
bash -n "$SCRIPT"; check "syntax_check" "[ $? -eq 0 ]"
grep -niE 'clojure|babashka' "$SCRIPT" >/tmp/tikit_g3 || true
check "no_clojure_runtime" "[ ! -s /tmp/tikit_g3 ]"
grep -nE 'import[[:space:]]+(yaml|requests|numpy|pandas|ruamel|toml)|from[[:space:]]+(yaml|requests|numpy|pandas|ruamel|toml)[[:space:]]+import' "$SCRIPT" >/tmp/tikit_g4 || true
check "stdlib_only_python" "[ ! -s /tmp/tikit_g4 ]"
python3 -c 'import json,sqlite3,re,sys,os,datetime; print("ok")' >/tmp/tikit_g5
check "python_stdlib_importable" "grep -q ok /tmp/tikit_g5"
grep -niE 'resolve-ticket-id|build-tree|render-tree|cycle|descendant|ancestor' "$SCRIPT" >/tmp/tikit_g6 || true
check "no_tree_code_static" "[ ! -s /tmp/tikit_g6 ]"

echo "=== command dispatch ==="
"$SCRIPT" tree >/dev/null 2>&1; check "tree_rejected" "[ $? -ne 0 ]"
"$SCRIPT" tree tikit-abc123 >/dev/null 2>&1; check "tree_with_arg_rejected" "[ $? -ne 0 ]"
"$SCRIPT" frobnicate >/dev/null 2>&1; check "unknown_subcommand_rejected" "[ $? -ne 0 ]"
"$SCRIPT" --help >/dev/null 2>&1; check "top_level_help_exit0" "[ $? -eq 0 ]"
"$SCRIPT" -h >/dev/null 2>&1; check "top_level_h_exit0" "[ $? -eq 0 ]"
"$SCRIPT" query --help >/dev/null 2>&1; check "query_help_exit0" "[ $? -eq 0 ]"

echo "=== python3 absent ==="
TB=$(mktemp -d); for t in tr head date mkdir cat ls basename dirname printf rm sed grep; do ln -sf "$(command -v "$t" 2>/dev/null)" "$TB/$t" 2>/dev/null || true; done
PATH="$TB" TIKIT_DIR="$(mktemp -d)" "$SCRIPT" create --name t 2>"$TB/err"; RC=$?
ERR=$(cat "$TB/err" 2>/dev/null)
check "python3_absent_error_rc" "[ $RC -ne 0 ]"
check "python3_absent_error_msg" "echo '$ERR' | grep -qi python3"

echo "=== env override ==="
D=$(mktemp -d)
P=$(TIKIT_DIR="$D/x" "$SCRIPT" create --name hi)
check "tikit_tickets_dir_override" "case \"$P\" in \"$D/x\"/*) true;; *) false;; esac"
[ -f "$P" ] && check "tikit_tickets_dir_override_exists" "true" || check "tikit_tickets_dir_override_exists" "false"
D=$(mktemp -d); mkdir -p "$D/proj"; cd "$D/proj" || exit 1
P=$(TIKIT_DIR="" "$SCRIPT" create --name hi)
check "tikit_tickets_dir_empty_falls_back" "test -d .tickets"
D=$(mktemp -d); mkdir -p "$D/proj"; cd "$D/proj" || exit 1
unset TIKIT_DIR
P=$("$SCRIPT" create --name hi)
check "tikit_tickets_dir_unset_default" "test -f ./.tickets/*/ticket.md"

echo "=== id format ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
P=$("$SCRIPT" create); ID=$(basename "$(dirname "$P")")
check "id_format_cwd_tikit" "printf '%s' \"$ID\" | grep -qE '^tiki-[a-z0-9]{6}\$'"
D=$(mktemp -d); mkdir -p "$D/Tikit"; cd "$D/Tikit" || exit 1
P=$("$SCRIPT" create); ID=$(basename "$(dirname "$P")")
check "id_slug_case_preserving" "printf '%s' \"$ID\" | grep -qE '^Tiki-[a-z0-9]{6}\$'"
D=$(mktemp -d); mkdir -p "$D/ab"; cd "$D/ab" || exit 1
P=$("$SCRIPT" create); ID=$(basename "$(dirname "$P")")
check "id_slug_short_basename" "printf '%s' \"$ID\" | grep -qE '^ab-[a-z0-9]{6}\$'"
D=$(mktemp -d); mkdir -p "$D/myproject"; cd "$D/myproject" || exit 1
P=$("$SCRIPT" create); ID=$(basename "$(dirname "$P")")
check "id_slug_long_basename" "printf '%s' \"$ID\" | grep -qE '^mypr-[a-z0-9]{6}\$'"
D=$(mktemp -d); cd / || exit 1
P=$(TIKIT_DIR="$D" "$SCRIPT" create --name t); RC=$?
ID=$(basename "$(dirname "$P")")
check "id_slug_empty_basename_root_rc" "[ $RC -eq 0 ]"
check "id_slug_empty_basename_root_id" "printf '%s' \"$ID\" | grep -qE '^t-[a-z0-9]{6}\$'"

echo "=== create layout / output ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
P=$("$SCRIPT" create)
check "create_writes_subfolder_ticket_md" "case \"$P\" in */ticket.md) true;; *) false;; esac"
check "create_no_flat_file" "[ ! -f ./.tickets/*.md ]"
OUT=$("$SCRIPT" create --name t)
LINES=$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')
check "create_prints_absolute_path_sole_line_lines" "[ $LINES -eq 1 ]"
check "create_prints_absolute_path_sole_line_abs" "case \"$OUT\" in /*) true;; *) false;; esac"

echo "=== create defaults ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create >/dev/null
J=$("$SCRIPT" query --json)
echo "$J" | python3 -c "
import json,sys,re
o=json.loads(sys.stdin.readline())
assert o['status']=='open', o['status']
assert o['name']=='', repr(o['name'])
assert o['_body'].strip() == '', repr(o['_body'])
assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\$', o['created']), o['created']
print('defaults-ok')
" >/tmp/t_def
check "create_defaults" "grep -q defaults-ok /tmp/t_def"

echo "=== create errors / help ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --status >/dev/null 2>&1; check "create_key_no_value_error" "[ $? -ne 0 ]"
"$SCRIPT" create extra >/dev/null 2>&1; check "create_unexpected_positional_error" "[ $? -ne 0 ]"
"$SCRIPT" create --help >/dev/null 2>&1; check "create_help_exit0" "[ $? -eq 0 ]"
"$SCRIPT" create -h >/dev/null 2>&1; check "create_h_short_exit0" "[ $? -eq 0 ]"

echo "=== id gate / overwrite gate ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --id taken >/dev/null
printf -- "---\nid: 'taken'\nname: 'orig'\nstatus: 'open'\ncreated: '2020-01-01T00:00:00Z'\nparent: null\nblocked-on: []\n---\nbody line\n" > "$D/tikit/.tickets/taken/ticket.md"
"$SCRIPT" create --id taken >/dev/null 2>/tmp/tikit.err; RC=$?
check "create_existing_id_refused_rc" "[ $RC -ne 0 ]"
check "create_existing_id_refused_msg" "grep -q 'already exists' /tmp/tikit.err"
check "create_existing_id_keeps_file" "grep -q \"name: 'orig'\" \"$D/tikit/.tickets/taken/ticket.md\""
"$SCRIPT" create --id taken --force --name new >/dev/null 2>&1; RC=$?
check "create_force_overwrites_rc" "[ $RC -eq 0 ]"
check "create_force_overwrites_file" "grep -q \"name: 'new'\" \"$D/tikit/.tickets/taken/ticket.md\""
"$SCRIPT" create --id ../escape >/dev/null 2>/tmp/tikit.err; RC=$?
check "create_id_traversal_refused_rc" "[ $RC -ne 0 ]"
check "create_id_traversal_refused_msg" "grep -q 'bad id' /tmp/tikit.err"
check "create_id_traversal_no_escape" "[ ! -e '$D/escape' ]"
"$SCRIPT" create --id /tmp/tikit-escape-abs >/dev/null 2>&1; RC=$?
check "create_id_absolute_refused_rc" "[ $RC -ne 0 ]"
check "create_id_absolute_refused_no_file" "[ ! -e /tmp/tikit-escape-abs ]"
"$SCRIPT" create --id "a b" >/dev/null 2>&1
check "create_id_space_refused_rc" "[ $? -ne 0 ]"
"$SCRIPT" create --id .. >/dev/null 2>&1
check "create_id_dotdot_refused_rc" "[ $? -ne 0 ]"

echo "=== null representation ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --name n1 >/dev/null
J=$("$SCRIPT" query --json)
echo "$J" | python3 -c "
import json,sys
o=json.loads(sys.stdin.readline())
assert o['parent'] is None, o['parent']
assert o['blocked-on']==[], o['blocked-on']
print('null-ok')
" >/tmp/t_null
check "json_parent_is_null" "grep -q null-ok /tmp/t_null"
N=$("$SCRIPT" query --files --parent null | wc -l | tr -d ' ')
check "filter_null_positive_empty" "[ $N -eq 0 ]"
N=$("$SCRIPT" query --files not --parent . | wc -l | tr -d ' ')
check "filter_null_negated_matches" "[ $N -eq 1 ]"
S=$("$SCRIPT" query --sql 'SELECT id FROM tickets WHERE parent IS NULL' | wc -l | tr -d ' ')
check "sql_parent_is_null" "[ $S -eq 1 ]"

echo "=== create permissive / id override ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
P=$("$SCRIPT" create --foo bar); RC=$?
[ -f "$P" ] && check "create_permissive_file" "true" || check "create_permissive_file" "false"
check "create_permissive_rc" "[ $RC -eq 0 ]"
J=$("$SCRIPT" query --json)
echo "$J" | python3 -c "import json,sys; o=json.loads(sys.stdin.readline()); print('foo=' + o.get('foo','MISSING'))" >/tmp/t_perm
check "create_permissive_arbitrary_key" "grep -q 'foo=bar' /tmp/t_perm"
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
P=$("$SCRIPT" create --id customid); ID=$(basename "$(dirname "$P")")
check "create_id_override_d20_folder" "test -f \"$D/tikit/.tickets/customid/ticket.md\""
check "create_id_override_d20_foldername" "[ \"$ID\" = customid ]"
J=$("$SCRIPT" query --json)
echo "$J" | python3 -c "import json,sys; o=json.loads(sys.stdin.readline()); print('id=' + o['id'])" >/tmp/t_id
check "create_id_override_d20_id" "grep -q 'id=customid' /tmp/t_id"
"$SCRIPT" create --id custom-1 >/dev/null
"$SCRIPT" query --files | grep -q '/custom-1/ticket.md' && check "create_id_override_visible" "true" || check "create_id_override_visible" "false"

echo "=== list syntax ==="
test_list() {
    local name="$1" args="$2" pycheck="$3"
    D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
    eval "\"$SCRIPT\" create $args" >/dev/null
    J=$("$SCRIPT" query --json)
    echo "$J" | python3 -c "$pycheck" >/tmp/tl_$name 2>&1
    check "$name" "grep -q ok /tmp/tl_$name"
}
test_list "list_syntax_two_elements" "--tags :a:b: --status closed" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['tags']==['a','b'], o['tags']; assert o['status']=='closed'; print('ok')"
test_list "list_syntax_one_element" "--tags :s:" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['tags']==['s'], o['tags']; print('ok')"
test_list "list_syntax_double_colon_scalar" "--x ::" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']=='::', repr(o['x']); print('ok')"
test_list "list_syntax_single_colon_scalar" "--x :" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']==':', repr(o['x']); print('ok')"
test_list "list_syntax_not_ending_colon_scalar" "--x :a:b" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']==':a:b', repr(o['x']); print('ok')"

echo "=== yaml roundtrip ==="
test_rt() {
    local name="$1" arg="$2" pycheck="$3"
    D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
    eval "\"$SCRIPT\" create --x $arg" >/dev/null
    J=$("$SCRIPT" query --json)
    echo "$J" | python3 -c "$pycheck" >/tmp/trt_$name 2>&1
    check "$name" "grep -q ok /tmp/trt_$name"
}
test_rt "yaml_roundtrip_colon_space" "'a: b'" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']=='a: b', repr(o['x']); print('ok')"
test_rt "yaml_roundtrip_leading_star" "'*foo'" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']=='*foo', repr(o['x']); print('ok')"
test_rt "yaml_roundtrip_brackets_scalar" "'[a, b]'" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']=='[a, b]', repr(o['x']); print('ok')"
test_rt "yaml_roundtrip_single_quote" "\"it's\"" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']==\"it's\", repr(o['x']); print('ok')"
test_rt "yaml_roundtrip_empty_value" "''" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']=='', repr(o['x']); print('ok')"
test_rt "yaml_no_bool_null_number_coercion" "yes --y true --z null --w 123" "import json,sys; o=json.loads(sys.stdin.readline()); assert o['x']=='yes' and o['y']=='true' and o['z']=='null' and o['w']=='123'; print('ok')"

echo "=== json / files output ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --name t1 --tags :a:b: >/dev/null
"$SCRIPT" create --name t2 >/dev/null
"$SCRIPT" query --json | python3 -c "
import json,sys
n=0
for line in sys.stdin:
    line=line.rstrip('\n')
    if not line: continue
    o=json.loads(line)
    assert '_body' in o and isinstance(o['_body'],str)
    assert 'path' in o and isinstance(o['path'],str) and o['path'].startswith('/')
    n+=1
assert n==2, n
print('ndjson-ok')
" >/tmp/t_ndjson
check "json_ndjson_valid_and_fields" "grep -q ndjson-ok /tmp/t_ndjson"
LINES=$("$SCRIPT" query --files)
echo "$LINES" | while read -r f; do case "$f" in /*) ;; *) echo RELATIVE; exit 1;; esac; test -f "$f" || echo "MISSING:$f"; done >/tmp/t_files
COUNT=$(printf '%s\n' "$LINES" | grep -c .)
check "query_files_absolute_existing" "[ ! -s /tmp/t_files ] && [ $COUNT -eq 2 ]"
D=$(mktemp -d)
OUT=$(TIKIT_DIR="$D/empty" "$SCRIPT" query --files); RC=$?
check "query_files_empty_dir" "[ $RC -eq 0 ] && [ -z \"$OUT\" ]"
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --name a >/dev/null
A=$("$SCRIPT" query --files); B=$("$SCRIPT" query)
check "query_default_mode_is_files" "[ \"$A\" = \"$B\" ]"
"$SCRIPT" query --files --json >/dev/null 2>&1; check "query_conflict_files_json" "[ $? -ne 0 ]"
"$SCRIPT" query --sql 'SELECT 1' --files >/dev/null 2>&1; check "query_conflict_sql_files" "[ $? -ne 0 ]"
"$SCRIPT" query --json --json >/dev/null 2>&1; check "query_duplicate_mode_json" "[ $? -ne 0 ]"

echo "=== sql ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --name a --status open >/dev/null
"$SCRIPT" create --name b --status closed >/dev/null
OUT=$("$SCRIPT" query --sql 'SELECT id FROM tickets ORDER BY id')
ROWS=$(printf '%s\n' "$OUT" | grep -c .)
check "query_sql_basic" "[ $ROWS -eq 2 ]"
"$SCRIPT" create --status open >/dev/null
"$SCRIPT" create --status closed >/dev/null
OUT=$("$SCRIPT" query --sql "SELECT id FROM tickets WHERE json_extract(data,'\$.status')='open'")
OROWS=$(printf '%s\n' "$OUT" | grep -c .)
check "query_sql_json_extract_status" "[ $OROWS -ge 1 ]"
"$SCRIPT" query --sql "SELECT json_extract(data,'\$.nope') FROM tickets" >/dev/null 2>&1; check "query_sql_absent_key_null" "[ $? -eq 0 ]"
"$SCRIPT" query --sql SELECT id , status FROM tickets >/dev/null 2>&1; check "query_sql_join_args" "[ $? -eq 0 ]"
"$SCRIPT" query --sql >/dev/null 2>&1; check "query_sql_no_query_error" "[ $? -ne 0 ]"
"$SCRIPT" query --sql 'SELECT 1' --status open >/dev/null 2>&1; check "query_sql_mix_key_error" "[ $? -ne 0 ]"

echo "=== filters ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --name a --status open >/dev/null
"$SCRIPT" create --name b --status closed >/dev/null
OPEN=$("$SCRIPT" query --files --status open | grep -c .)
check "filter_status_open" "[ $OPEN -eq 1 ]"
NOTOPEN=$("$SCRIPT" query --files --not --status open | grep -c .)
check "filter_not_status_open" "[ $NOTOPEN -eq 1 ]"
"$SCRIPT" create --name fix --status open --tags :urgent: >/dev/null
"$SCRIPT" create --name fix --status closed --tags :urgent: >/dev/null
"$SCRIPT" create --name other --status open --tags :low: >/dev/null
AND=$("$SCRIPT" query --files --name fix --status open | grep -c .)
check "filter_and_composition" "[ $AND -eq 1 ]"
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --name a --status open >/dev/null
MPOS=$("$SCRIPT" query --files --priority high | grep -c .)
check "filter_missing_key_positive_fails" "[ $MPOS -eq 0 ]"
MNEG=$("$SCRIPT" query --files --not --priority high | grep -c .)
check "filter_missing_key_negated_succeeds" "[ $MNEG -eq 1 ]"
"$SCRIPT" create --name 'fix bug' --status open >/dev/null
"$SCRIPT" create --name 'add feature' --status open >/dev/null
RSUB=$("$SCRIPT" query --files --name fix | grep -c .)
check "filter_regex_substring" "[ $RSUB -eq 1 ]"
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --status open >/dev/null
"$SCRIPT" create --status closed >/dev/null
ANC=$("$SCRIPT" query --files --status '^open$' | grep -c .)
check "filter_regex_anchored" "[ $ANC -eq 1 ]"
"$SCRIPT" create --tags :report:urgent: >/dev/null
"$SCRIPT" create --tags :low: >/dev/null
LM=$("$SCRIPT" query --files --tags urgent | grep -c .)
check "filter_list_membership" "[ $LM -eq 1 ]"

echo "=== filter errors ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --status open >/dev/null
"$SCRIPT" query --status open not >/dev/null 2>&1; check "query_not_at_end_error" "[ $? -ne 0 ]"
"$SCRIPT" query not not --status open >/dev/null 2>&1; check "query_consecutive_not_error" "[ $? -ne 0 ]"
"$SCRIPT" query not >/dev/null 2>&1; check "query_not_alone_error" "[ $? -ne 0 ]"
"$SCRIPT" query --status >/dev/null 2>&1; check "query_key_no_value_error" "[ $? -ne 0 ]"

echo "=== legacy / dedup ==="
D=$(mktemp -d); TT="$D/tt"; mkdir -p "$TT"
printf -- '---\nid: tikit-leg001\nname: legacy flat\nstatus: open\ncreated: 2026-01-01T00:00:00Z\n---\nlegacy body\n' > "$TT/tikit-leg001.md"
cd "$D" || exit 1
OUT=$(TIKIT_DIR="$TT" "$SCRIPT" query --files)
echo "$OUT" | grep -q '/tikit-leg001\.md' && check "legacy_flat_ticket_discovered" "true" || check "legacy_flat_ticket_discovered" "false"
D=$(mktemp -d); TT="$D/tt"; mkdir -p "$TT"
printf -- '---\nid: tikit-leg002\nname: legacy\nstatus: closed\ncreated: 2026-01-01T00:00:00Z\n---\nbody\n' > "$TT/tikit-leg002.md"
cd "$D" || exit 1
J=$(TIKIT_DIR="$TT" "$SCRIPT" query --json)
echo "$J" | python3 -c "import json,sys; o=json.loads(sys.stdin.readline()); assert o['id']=='tikit-leg002' and o['status']=='closed' and o['_body'].strip()=='body'; print('ok')" >/tmp/tikit_lj
check "legacy_flat_in_json" "grep -q ok /tmp/tikit_lj"
S=$(TIKIT_DIR="$TT" "$SCRIPT" query --sql 'SELECT id FROM tickets')
echo "$S" | grep -q tikit-leg002 && check "legacy_flat_in_sql" "true" || check "legacy_flat_in_sql" "false"
D=$(mktemp -d); TT="$D/tt"; mkdir -p "$TT/tikit-ded001"
printf -- '---\nid: tikit-ded001\nname: subfolder\nstatus: open\ncreated: 2026-01-01T00:00:00Z\n---\n\n' > "$TT/tikit-ded001/ticket.md"
printf -- '---\nid: tikit-ded001\nname: flat\nstatus: open\ncreated: 2026-01-01T00:00:00Z\n---\n\n' > "$TT/tikit-ded001.md"
cd "$D" || exit 1
DEDUP=$(TIKIT_DIR="$TT" "$SCRIPT" query --files | grep -c .)
check "dedup_same_id_both_layouts" "[ $DEDUP -eq 1 ]"
D=$(mktemp -d); TT="$D/tt"; mkdir -p "$TT"
printf -- '---\nid: tikit-leg003\nname: blk\nstatus: open\ncreated: 2026-01-01T00:00:00Z\ntags:\n  - report\n  - urgent\n---\nbody\n' > "$TT/tikit-leg003.md"
cd "$D" || exit 1
J=$(TIKIT_DIR="$TT" "$SCRIPT" query --json)
echo "$J" | python3 -c "import json,sys; o=json.loads(sys.stdin.readline()); assert o['tags']==['report','urgent'], o['tags']; print('ok')" >/tmp/t_bl
check "legacy_block_list_parsed" "grep -q ok /tmp/t_bl"
D=$(mktemp -d); TT="$D/tt"; mkdir -p "$TT"
printf -- '---\nid: tikit-leg004\nname: "quoted name"\nstatus: '"'"'open'"'"'\ncreated: 2026-01-01T00:00:00Z\n---\nbody\n' > "$TT/tikit-leg004.md"
cd "$D" || exit 1
J=$(TIKIT_DIR="$TT" "$SCRIPT" query --json)
echo "$J" | python3 -c "import json,sys; o=json.loads(sys.stdin.readline()); assert o['name']=='quoted name' and o['status']=='open'; print('ok')" >/tmp/t_q
check "legacy_quoted_scalar_parsed" "grep -q ok /tmp/t_q"

echo "=== open world ==="
D=$(mktemp -d); mkdir -p "$D/tikit"; cd "$D/tikit" || exit 1
"$SCRIPT" create --priority 5 --sprint 'S-42' >/dev/null
J=$("$SCRIPT" query --json)
echo "$J" | python3 -c "import json,sys; o=json.loads(sys.stdin.readline()); assert o.get('priority')=='5' and o.get('sprint')=='S-42'; print('ok')" >/tmp/t_ow
check "open_world_key_preserved_json" "grep -q ok /tmp/t_ow"
S=$("$SCRIPT" query --sql "SELECT json_extract(data,'\$.priority') FROM tickets")
echo "$S" | grep -q '^5$' && check "open_world_key_preserved_sql" "true" || check "open_world_key_preserved_sql" "false"

echo "=== readonly / errors ==="
D=$(mktemp -d); mkdir -p "$D/ro"; chmod 555 "$D/ro"; cd "$D" || exit 1
TIKIT_DIR="$D/ro/sub" "$SCRIPT" create --name t >/dev/null 2>&1; check "create_readonly_dir_error" "[ $? -ne 0 ]"
chmod 755 "$D/ro"

echo "=== body special chars roundtrip ==="
D=$(mktemp -d); TT="$D/tt"; mkdir -p "$TT/tikit-zz0001"
printf -- '---\nid: tikit-zz0001\nname: t\nstatus: open\ncreated: 2026-01-01T00:00:00Z\n---\nLine1 "q" \back `code` caf\xc3\xa9\nLine2 "more"\n' > "$TT/tikit-zz0001/ticket.md"
printf 'Line1 "q" \back `code` caf\xc3\xa9\nLine2 "more"\n' > "$D/exp.txt"
TIKIT_DIR="$TT" "$SCRIPT" query --json > "$D/out.jsonl"
python3 - "$D/exp.txt" "$D/out.jsonl" <<'PY' >/tmp/tikit_bs
import json,sys
exp=open(sys.argv[1]).read()
found=False
for line in open(sys.argv[2]):
    line=line.rstrip('\n')
    if not line: continue
    o=json.loads(line)
    if o.get('id')=='tikit-zz0001':
        found=True
        if o['_body']==exp:
            print('body-rt-ok')
        else:
            print('MISMATCH'); print(repr(o['_body'])); print(repr(exp))
if not found: print('NOT-FOUND')
PY
check "json_body_special_chars_roundtrip" "grep -q body-rt-ok /tmp/tikit_bs"

echo "=== create output ==="
D=$(mktemp -d); mkdir -p "$D/tikit"
cd "$D/tikit" || exit 1
OUT=$("$SCRIPT" create --name "skeleton-test")
FILE="$D/tikit/.tickets/$(basename $(dirname "$OUT"))/ticket.md"

check "create_frontmatter_id" "grep -q '^id:' \"$FILE\""
check "create_frontmatter_name" "grep -q '^name:' \"$FILE\""
check "create_frontmatter_status" "grep -q '^status:' \"$FILE\""
check "create_frontmatter_created" "grep -q '^created:' \"$FILE\""
check "create_frontmatter_parent" "grep -q '^parent:' \"$FILE\""
check "create_frontmatter_blocked_on" "grep -q '^blocked-on:' \"$FILE\""

check "create_no_phase_headings" "! grep -q '^# ' \"$FILE\""

cd / || exit 1
rm -rf "$D"

echo ""
echo "================================"
echo "PASS: $PASS  FAIL: $FAIL"
echo "================================"
if [ $FAIL -gt 0 ]; then echo -e "Failed tests:$FAILED_TESTS"; fi
