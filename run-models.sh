#!/usr/bin/env bash
# run-models.sh - run one prompt across many models for ONE wallet.
# Layout: <wallet-address>/<model-label>/...  (one folder per wallet+model)
#
#   ./run-models.sh --wallet 0xABC...                 verify all free models, then run
#   ./run-models.sh --wallet 0xABC... --dry-run       print every command, no API calls
#   ./run-models.sh --wallet 0xABC... --stage verify  only the free-check probes
#   ./run-models.sh --wallet 0xABC... --jobs 6 --only kilo
#   ./run-models.sh --wallet 0xABC... --no-verify     skip the up-front probe phase
#   ./run-models.sh --wallet 0xABC... --probe-jobs 8  concurrency for the probe phase
#
# EVERY model is verified $0-free at run time, before ANY prompt is sent
# (prices and free tiers change without notice, so nothing is trusted from a
# previous sweep):
#   stage 0 rating    : model has a -1 rating in the app => never contacted
#   stage A metadata  : poll each tool's CURRENT free list
#                       cline -> .free[] from api.cline.bot
#                       kilo  -> isFree AND every cost field 0
#                       opencode -> input/output/cache read+write all 0
#   stage B probe     : one tiny "Reply OK" call per free model, run for the
#                       whole sweep up front by verify_all(); plan agent, so a
#                       paywall or auth error shows up as a verdict
#   stage C run       : the real prompt, output captured in <label>/
#
# A model only reaches stage C if it is listed free RIGHT NOW and its probe
# returned OK. Anything else is skipped, so a sweep cannot spend money.
set -uo pipefail

# Print the usage header: every leading comment line after the shebang. Reading
# the docs from the same place the docs live keeps --help from going stale when
# the comment block grows.
help_header() {
  awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$1"
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_FILE="$ROOT/models.tsv"
PROMPT_FILE="$ROOT/prompt.txt"
JOBS=4
TIMEOUT_SECS=1800
PROBE_TIMEOUT=180
PROBE_JOBS=4
CHECK_FREE=1
VERIFY=1
DRY_RUN=0
STAGE=run
ONLY=""
FORCE=0
RESUME=0
WALLET=""
PROMPT_FILE_SET=0

PROBE_PROMPT="Reply with exactly: OK"

while [ $# -gt 0 ]; do
  case "$1" in
    --jobs) JOBS="$2"; shift 2;;
    --timeout) TIMEOUT_SECS="$2"; shift 2;;
    --probe-jobs) PROBE_JOBS="$2"; shift 2;;
    --models) MODELS_FILE="$2"; shift 2;;
    --prompt-file) PROMPT_FILE="$2"; PROMPT_FILE_SET=1; shift 2;;
    --wallet) WALLET="$2"; shift 2;;
    --only) ONLY="$2"; shift 2;;
    --stage) STAGE="$2"; shift 2;;
    --no-check-free) CHECK_FREE=0; VERIFY=0; shift;;
    --no-verify) VERIFY=0; shift;;
    --force) FORCE=1; shift;;
    --resume) RESUME=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) help_header "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done

[ -f "$MODELS_FILE" ] || { echo "missing $MODELS_FILE" >&2; exit 1; }
[ -n "$WALLET" ] || { echo "missing --wallet <address> (runs land in <wallet>/<label>/)" >&2; exit 1; }
RUN_ROOT="$ROOT/$WALLET"
mkdir -p "$RUN_ROOT"
# per-wallet prompt by default (<wallet>/prompt.txt); --prompt-file overrides
if [ "$PROMPT_FILE_SET" = 0 ] && [ -f "$RUN_ROOT/prompt.txt" ]; then
  PROMPT_FILE="$RUN_ROOT/prompt.txt"
fi
[ -f "$PROMPT_FILE" ] || { echo "missing $PROMPT_FILE" >&2; exit 1; }
PROMPT="$(cat "$PROMPT_FILE")"
TMP="$(mktemp -d "$ROOT/.tmp.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------- free lists
load_free_lists() {
  [ "$CHECK_FREE" = 1 ] || return 0
  log "loading free-model lists (metadata gate)"

  local tok=""
  if command -v jq >/dev/null 2>&1; then
    tok="$(jq -r '.providers.cline.settings.auth.accessToken // empty' \
             "$HOME/.cline/data/settings/providers.json" 2>/dev/null || true)"
  fi
  if [ -n "$tok" ]; then
    curl -sS -m 45 'https://api.cline.bot/api/v1/ai/cline/recommended-models' \
      -H "Authorization: Bearer $tok" 2>/dev/null \
      | jq -r '.free[]?.id' 2>/dev/null | sort -u > "$TMP/free_cline.txt" || : > "$TMP/free_cline.txt"
  else
    : > "$TMP/free_cline.txt"
  fi

  timeout 120 kilo models --verbose 2>/dev/null | python3 "$ROOT/lib/parse_free.py" kilo \
    > "$TMP/free_kilo.txt" 2>/dev/null || : > "$TMP/free_kilo.txt"

  timeout 120 opencode models --verbose 2>/dev/null | python3 "$ROOT/lib/parse_free.py" opencode \
    > "$TMP/free_opencode.txt" 2>/dev/null || : > "$TMP/free_opencode.txt"

  log "  free ids -> cline:$(wc -l < "$TMP/free_cline.txt") kilo:$(wc -l < "$TMP/free_kilo.txt") opencode:$(wc -l < "$TMP/free_opencode.txt")"
}

metadata_free() {  # tool model -> 0 if it passes the metadata gate
  [ "$CHECK_FREE" = 1 ] || return 0
  case "$1" in
    cline)    grep -qxF "$2" "$TMP/free_cline.txt" 2>/dev/null;;
    kilo)     grep -qxF "$2" "$TMP/free_kilo.txt" 2>/dev/null;;
    opencode) grep -qxF "$2" "$TMP/free_opencode.txt" 2>/dev/null;;
    *) return 0;;
  esac
}


log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

# --------------------------------------------- rating gate (app DB, see §3b)
# Models with at least one negative rating in the rating app are never sent
# prompts (probe or run). The blocklist is loaded ONCE in main() into the
# exported $BLOCKED var (one psql call; `work_one` runs in parallel subshells,
# so no in-function cache would be shared). Fail-open: if the DB is
# unreachable the sweep proceeds; lift a block by removing the -1 in the app.
model_blocked() {  # model -> 0 if it has a -1 rating in the app db
  [ -n "$1" ] && [ -n "${BLOCKED:-}" ] && printf '%s\n' "$BLOCKED" | grep -qxF "$1"
}

# ------------------------------------------------- pre-sweep free verification
# Verdict cache: tool \t model \t verdict. Rebuilt from scratch every sweep --
# free tiers change without notice, so a verdict from yesterday proves nothing
# about whether we can spend money on the model today.
DISCOVERY_FILE="$ROOT/discovery.tsv"   # tool | model | verdict | date | note (history)

# probe_verdict tool model -> OK | NOT_FREE | RATE_LIMITED | AUTH_ERROR | ERROR | EMPTY | MISSING
probe_verdict() {
  awk -F'\t' -v t="$1" -v m="$2" '$1==t && $2==m {print $3; exit}' \
    "$TMP/verdicts.tsv" 2>/dev/null
}

record_discovery() {  # tool model verdict note  (append-only history, latest wins)
  printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$(date +%F)" "$4" >> "$DISCOVERY_FILE"
}

# Probe one model and cache its verdict. Runs in a background subshell, so it
# only ever appends a single line to the shared cache file.
probe_one() {  # tool model variant extra
  local tool="$1" model="$2" variant="$3" extra="$4"
  local pd; pd="$(mktemp -d "$TMP/probe.XXXXXX")"
  build_cmd "$tool" "$model" "$variant" "$extra" "$pd" "$PROBE_PROMPT" probe
  timeout "$PROBE_TIMEOUT" "${CMD[@]}" > "$pd/probe.txt" 2>&1 < /dev/null
  local code=$?
  local verdict; verdict="$(classify "$pd/probe.txt" "$code")"
  printf '%s\t%s\t%s\n' "$tool" "$model" "$verdict" >> "$TMP/verdicts.tsv"
  rm -rf "$pd"
}

# What gets probed: ONLY ids a tool currently lists as $0-free, minus any the
# rating gate blocks. This is the money-safety boundary -- the probe is itself
# a billable call, so a model the provider does not advertise as free is never
# even contacted, let alone sent the real prompt. Curated rows contribute their
# variant/extra-args, and are dropped if they are not in a live free list.
verify_targets() {
  : > "$TMP/targets.tsv"
  local tool model variant extra
  for tool in cline kilo opencode; do
    [ -s "$TMP/free_$tool.txt" ] || continue
    while IFS= read -r model; do
      [ -n "$model" ] || continue
      model_blocked "$model" && continue
      printf '%s\t%s\t\t\n' "$tool" "$model" >> "$TMP/targets.tsv"
    done < "$TMP/free_$tool.txt"
  done
  # hand curated rows their variant/extra so the probe matches the real run
  while IFS='|' read -r tool model label variant extra; do
    [ -z "${label:-}" ] || continue
    [ -z "${model:-}" ] || continue
    grep -qP "^\Q$tool\E\t\Q$model\E\t" "$TMP/targets.tsv" 2>/dev/null || continue
    awk -F'\t' -v OFS='\t' -v t="$tool" -v m="$model" -v v="${variant:-}" -v x="${extra:-}" \
      '($1==t && $2==m) { if ($3=="" && $4=="") { $3=v; $4=x } print; next } { print }' \
      "$TMP/targets.tsv" > "$TMP/targets.new" && mv "$TMP/targets.new" "$TMP/targets.tsv"
  done < <(rows)
}

# Probe EVERY free model before the sweep spends anything on the real prompt.
# A model whose probe fails here never reaches stage C at all.
verify_all() {
  : > "$TMP/verdicts.tsv"
  verify_targets

  local total; total=$(grep -c . "$TMP/targets.tsv" 2>/dev/null || echo 0)
  [ "$total" -gt 0 ] || { log "verify: nothing to probe"; return 0; }
  log "verify: probing $total free model(s) before the sweep (1 tiny call each)"

  local running=0
  while IFS=$'\t' read -r tool model variant extra; do
    [ -n "${tool:-}" ] || continue
    [ -n "${model:-}" ] || continue
    probe_one "$tool" "$model" "${variant:-}" "${extra:-}" < /dev/null &
    running=$((running + 1))
    if [ "$running" -ge "$PROBE_JOBS" ]; then
      wait -n 2>/dev/null || true
      running=$((running - 1))
    fi
  done < "$TMP/targets.tsv"
  wait

  local ok; ok=$(awk -F'\t' '$3=="OK"' "$TMP/verdicts.tsv" 2>/dev/null | wc -l)
  log "verify: $ok/$total confirmed \$0-free; the rest are blocked from the prompt"
}

# Promote verified models that are not in models.tsv yet, so a newly free
# model joins the sweep instead of needing a manual edit.
promote_new() {
  local added=0 tool model verdict label
  while IFS=$'\t' read -r tool model verdict; do
    [ "$verdict" = OK ] || continue
    grep -qP "^\Q$tool\E\|\Q$model\E\|" "$MODELS_FILE" 2>/dev/null && continue
    label="new-$(printf '%s' "$model" | tr -c 'A-Za-z0-9._-' '-' | sed 's/-\{2,\}/-/g;s/^-//;s/-$//')"
    label="$(printf '%s' "$label" | cut -c1-60)"
    label="new-$tool-${label#new-}"
    printf '%s|%s|%s||\n' "$tool" "$model" "$label" >> "$MODELS_FILE"
    record_discovery "$tool" "$model" free "probe OK, added to models.tsv"
    log "  + new free model '$label' ($model)"
    added=$((added + 1))
  done < "$TMP/verdicts.tsv"
  [ "$added" -gt 0 ] && log "promote: $added new free model(s) added to models.tsv"
  return 0
}

# ------------------------------------------------------------ command builder
build_cmd() {  # tool model variant extra work prompt mode(run|probe) -> fills CMD[]
  CMD=()
  local tool="$1" model="$2" variant="$3" extra="$4" work="$5" prompt="$6" mode="$7"
  local -a x=()
  [ -n "$extra" ] && read -r -a x <<< "$extra"
  case "$tool" in
    cline)
      CMD=(cline -P cline -m "$model" --auto-approve true -y -c "$work")
      [ -n "$variant" ] && CMD+=(--thinking "$variant")
      [ "$mode" = probe ] && CMD+=(-p)
      CMD+=("${x[@]}" "$prompt");;
    kilo)
      CMD=(kilo run -m "$model" --auto --dir "$work")
      [ -n "$variant" ] && CMD+=(--variant "$variant")
      [ "$mode" = probe ] && CMD+=(--agent plan)
      CMD+=("${x[@]}" "$prompt");;
    opencode)
      CMD=(opencode run -m "$model" --auto --dir "$work")
      [ -n "$variant" ] && CMD+=(--variant "$variant")
      [ "$mode" = probe ] && CMD+=(--agent plan)
      CMD+=("${x[@]}" "$prompt");;
  esac
}

classify() {  # file exitcode -> verdict
  local f="$1" code="$2"
  if grep -qiE 'insufficient (credit|fund|balance)|not enough credit|out of credit|no credits|payment required|requires? (a )?(paid|subscription|upgrade|credit)|upgrade (to|your) (plan|account)|not available on (the )?free|no free (access|quota)|402 payment required|status code 402|error 402|billing' "$f"; then
    echo NOT_FREE; return; fi
  if grep -qiE 'rate limit|429|too many requests|quota exceeded|temporarily unavailable' "$f"; then
    echo RATE_LIMITED; return; fi
  if grep -qiE 'unauthor|forbidden|invalid api key|not authenticated|no credentials|401 |403 ' "$f"; then
    echo AUTH_ERROR; return; fi
  if [ "$code" != "0" ]; then echo "ERROR"; return; fi
  [ -s "$f" ] || { echo EMPTY; return; }
  echo OK
}

shquote() { printf '%q ' "$@" | sed 's/ $//'; }


# ------------------------------------------------------------------ one model
write_meta() {  # dir label tool model variant free_gate probe status exit dur bytes extra
  python3 - "$@" <<'PY'
import json, os, sys
d, wallet, label, tool, model, variant, gate, probe, status, code, dur, nbytes = sys.argv[1:13]
extra = sys.argv[13] if len(sys.argv) > 13 else ""
json.dump({"wallet": wallet, "label": label, "tool": tool, "model": model, "variant": variant,
           "free_gate": gate, "probe": probe, "status": status,
           "exit": int(code), "duration_s": round(float(dur), 1),
           "bytes": int(nbytes), "extra": extra, "prompt_file": "prompt.txt"},
          open(os.path.join(d, "meta.json"), "w"), indent=1)
PY
}

work_one() {  # tool model label variant extra
  local tool="$1" model="$2" label="$3" variant="$4" extra="$5"
  local dir="$RUN_ROOT/$label"

  # stage 0 - rating gate: never send prompts to a model with a negative
  # rating in the rating app (covers probe AND run; see model_blocked).
  # Checked before ANY side effect (no work dir, no probe). If a previous
  # sweep already produced a result for this label, leave that dir untouched
  # (no synthetic meta.json: it would clobber the real record and wipe
  # report_path on the next import).
  if model_blocked "$model"; then
    if [ -f "$dir/meta.json" ]; then
      log "SKIP $label (negative rating; keeping previous run record)"
    else
      mkdir -p "$dir"
      local gate="ok" probe="skipped" status="SKIPPED_NEGATIVE_RATING"
      printf 'skipped: model %s has at least one negative rating in the rating app\n' "$model" > "$dir/output.txt"
      write_meta "$dir" "$WALLET" "$label" "$tool" "$model" "$variant" "$gate" "$probe" "$status" 1 0 0 "$extra"
      log "SKIP $label (negative rating)"
    fi
    return
  fi

  # stage A - money gate. A model that is not in a tool's CURRENT free list is
  # never run: both the probe and the real prompt would be billable calls on
  # it. Checked before any workdir is created, so a blocked model leaves no
  # trace and keeps any previous run record intact. Deliberately NOT gated on
  # --force: rerunning a model is a normal request, spending money on it is not.
  if [ "$CHECK_FREE" = 1 ] && ! metadata_free "$tool" "$model"; then
    if [ -f "$dir/meta.json" ]; then
      log "SKIP $label (not free per metadata; keeping previous run record)"
    else
      mkdir -p "$dir"
      printf 'skipped: not in the current free list for %s (metadata gate)\n' "$tool" > "$dir/output.txt"
      write_meta "$dir" "$WALLET" "$label" "$tool" "$model" "$variant" "not_free_metadata" "skipped" \
        "SKIPPED_NOT_FREE" 1 0 0 "$extra"
      log "SKIP $label (not in the current free list - not spending to find out)"
    fi
    return
  fi

  local work="$dir/work"
  mkdir -p "$work"
  local gate="ok" probe="skipped" status="" code=0 t0 t1 dur bytes=0

  # stage B - verdict from the up-front probe phase (verify_all ran before the
  # sweep, so no real prompt was ever sent to an unverified model). Re-probing
  # here would double the API cost for no extra certainty. VERIFY=0 means the
  # operator opted out: the metadata gate above is then the only gate.
  if [ "$CHECK_FREE" = 1 ] && [ "$VERIFY" = 1 ]; then
    probe="$(probe_verdict "$tool" "$model")"
    [ -n "$probe" ] || probe="MISSING"
    if [ "$probe" != OK ]; then
      status="SKIPPED_NOT_FREE"; gate="ok"
      printf 'skipped: the pre-sweep free-check probe returned %s\n' "$probe" > "$dir/output.txt"
      write_meta "$dir" "$WALLET" "$label" "$tool" "$model" "$variant" "$gate" "$probe" "$status" 1 0 0 "$extra"
      log "SKIP $label (probe: $probe)"
      rm -rf "$work"
      return
    fi
  fi

  # --stage verify stops here. Never clobber a real prior run record: a
  # verification pass must not erase the status/duration/bytes of a report
  # that already exists, only refresh its probe verdict.
  if [ "$STAGE" = verify ]; then
    if [ -f "$dir/meta.json" ]; then
      python3 - "$dir/meta.json" "$probe" <<'PY'
import json, os, sys
p, probe = sys.argv[1], sys.argv[2]
try:
    m = json.load(open(p))
except Exception:
    sys.exit(0)
m["probe"] = probe
tmp = p + ".tmp"
json.dump(m, open(tmp, "w"), indent=1)
os.replace(tmp, p)
PY
      log "OK   $label (verified free; kept existing run record)"
    else
      write_meta "$dir" "$WALLET" "$label" "$tool" "$model" "$variant" "$gate" "$probe" "VERIFIED_FREE" 0 0 0 "$extra"
      log "OK   $label (verified free)"
    fi
    rm -rf "$work"
    return
  fi

  # stage C - the real prompt
  build_cmd "$tool" "$model" "$variant" "$extra" "$work" "$PROMPT" run
  shquote "${CMD[@]}" > "$dir/command.sh"
  t0=$SECONDS
  timeout "$TIMEOUT_SECS" "${CMD[@]}" > "$dir/output.txt" 2>&1 < /dev/null
  code=$?
  t1=$SECONDS
  dur=$((t1 - t0))
  bytes=$(wc -c < "$dir/output.txt")
  if [ "$code" = 124 ]; then status="TIMEOUT"
  elif grep -qiE 'insufficient (credit|fund|balance)|not enough credit|out of credit|payment required|402 payment required|status code 402|error 402' "$dir/output.txt"; then status="NOT_FREE"
  elif [ "$code" != "0" ]; then status="FAILED"
  else status="DONE"; fi
  # NOTE: no separate exit file -- the exit code lives ONLY in meta.json
  # (write_meta). One fact, one place (dedup rule, see agents.md §2).
  write_meta "$dir" "$WALLET" "$label" "$tool" "$model" "$variant" "$gate" "$probe" "$status" "$code" "$dur" "$bytes" "$extra"
  log "$status $label (${dur}s, ${bytes}B)"
}


# ---------------------------------------------------------------------- main
rows() {
  grep -vE '^[[:space:]]*(#|$)' "$MODELS_FILE"
}

manifest() {
  python3 - "$RUN_ROOT" <<'PY'
import json, os, sys
root = sys.argv[1]
rows = []
for name in sorted(os.listdir(root)):
    meta = os.path.join(root, name, "meta.json")
    if os.path.isfile(meta):
        try:
            rows.append(json.load(open(meta)))
        except Exception:
            pass
order = {"DONE": 0, "VERIFIED_FREE": 1, "SKIPPED_NOT_FREE": 2, "NOT_FREE": 2,
         "TIMEOUT": 3, "FAILED": 4, "": 5}
rows.sort(key=lambda r: (order.get(r.get("status", ""), 5), r.get("label", "")))
with open(os.path.join(root, "manifest.tsv"), "w") as fh:
    fh.write("status\ttool\tmodel\tvariant\tprobe\tgate\texit\tduration_s\tbytes\tlabel\n")
    for r in rows:
        fh.write("\t".join(str(r.get(k, "")) for k in
                 ("status", "tool", "model", "variant", "probe", "free_gate",
                  "exit", "duration_s", "bytes", "label")) + "\n")
w = max([len(r.get("label", "")) for r in rows] + [5])
print()
print("%-16s %-*s %-9s %-13s %8s %8s" % ("STATUS", w, "LABEL", "PROBE", "VARIANT", "SECS", "BYTES"))
for r in rows:
    print("%-16s %-*s %-9s %-13s %8s %8s" % (r.get("status", ""), w, r.get("label", ""),
          r.get("probe", ""), r.get("variant", "") or "-",
          r.get("duration_s", ""), r.get("bytes", "")))
done = [r for r in rows if r.get("status") == "DONE"]
print("\n%d/%d produced a real answer; manifest -> manifest.tsv" % (len(done), len(rows)))
PY
}

DRY=0
main() {
  log "models: $MODELS_FILE | prompt: $(head -c 60 "$PROMPT_FILE")..."
  load_free_lists
  # rating gate: one psql call before the job loop; exported so the
  # `work_one &` subshells (which can't share an in-function cache) see it.
  # < /dev/null: stdin here is the models list — docker exec must not inherit it.
  BLOCKED="$(docker compose -f "$ROOT/docker-compose.yml" exec -T db psql -U hl -d hl -Atc \
    "SELECT DISTINCT r.model FROM runs r JOIN ratings rt ON rt.run_id = r.id WHERE rt.value = -1" < /dev/null 2>/dev/null)" || BLOCKED=""
  export BLOCKED
  if [ -n "$BLOCKED" ]; then
    log "rating gate: $(printf '%s\n' "$BLOCKED" | wc -l) negatively-rated model(s) will be skipped"
  else
    log "rating gate: unavailable (app db down or no ratings) - not blocking anything"
  fi

  if [ "$DRY_RUN" = 1 ]; then
    log "dry-run: no probes, no API calls"
    verify_targets
    local n=0 queued=0 blocked=0
    while IFS='|' read -r tool model label variant extra; do
      [ -z "${label:-}" ] && continue
      if model_blocked "$model"; then
        printf '%-28s SKIPPED (negative rating)\n' "$label"
        n=$((n + 1))
        continue
      fi
      if metadata_free "$tool" "$model"; then
        gate=ok
        if grep -qP "^\Q$tool\E\t\Q$model\E\t" "$TMP/targets.tsv" 2>/dev/null; then
          queued=$((queued + 1))
        else
          gate=NOT_PROBED
        fi
      else
        gate=BLOCKED_NOT_FREE
        blocked=$((blocked + 1))
      fi
      build_cmd "$tool" "$model" "$variant" "${extra:-}" "$RUN_ROOT/$label/work" "$PROMPT" run
      printf '%-28s gate=%-16s %s\n' "$label" "$gate" "$(shquote "${CMD[@]}")"
      n=$((n + 1))
    done < <(rows)
    log "dry-run: $n models total -> $queued will be probed then run, $blocked blocked (not in a current free list), nothing executed"
    return
  fi

  # Up-front probe of every free model, before any real prompt is sent.
  # Verdict cache only -- a previous sweep's verdict is never reused, because
  # free tiers change and a stale OK is exactly how money gets spent.
  if [ "$VERIFY" = 1 ] && [ "$CHECK_FREE" = 1 ]; then
    verify_all
    promote_new
  else
    log "verify: skipped (--no-verify / --no-check-free) - models run unverified"
  fi

  local running=0
  while IFS='|' read -r tool model label variant extra; do
    [ -z "${label:-}" ] && continue
    if [ -n "$ONLY" ] && [[ "$label" != *"$ONLY"* ]]; then continue; fi
    if [ "$RESUME" = 1 ] && [ -f "$RUN_ROOT/$label/meta.json" ] && [ "$FORCE" = 0 ]; then
      log "SKIP $label (resume: previous result exists)"
      continue
    fi
    # stdin MUST be /dev/null: agents otherwise inherit this loop's input stream
    # (the models list) and swallow the remaining rows.
    work_one "$tool" "$model" "$label" "${variant:-}" "${extra:-}" < /dev/null &
    running=$((running + 1))
    if [ "$running" -ge "$JOBS" ]; then
      wait -n 2>/dev/null || true
      running=$((running - 1))
    fi
  done < <(rows)
  wait
  manifest
}

main

