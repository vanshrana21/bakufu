#!/usr/bin/env bash
# Go-live smoke check. Run this the moment Yash's artifact bundle is extracted.
#
#   ./scripts/go-live-check.sh [API_BASE_URL]
#
# Verifies every endpoint the frontend actually consumes, and reports the exact
# shape facts the adapters depend on. Exits non-zero if a required endpoint is
# down, so it can gate a deploy.
set -uo pipefail

API="${1:-http://127.0.0.1:8000}"
PASS=0; FAIL=0; WARN=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL+1)); }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; WARN=$((WARN+1)); }

code() { curl -s -o /tmp/glc.json -w '%{http_code}' -m 90 "$@"; }

echo "Go-live check against $API"
echo

# --- 1. health + provenance ------------------------------------------------
echo "[1] Health and artifact provenance"
if [ "$(code "$API/")" = 200 ]; then
  ok "GET / reachable"
  python3 - <<'PY'
import json
d = json.load(open('/tmp/glc.json'))
prov = d.get('data_provenance') or {}
deg  = d.get('degraded') or []
if prov.get('synthetic') is True:
    print("  \033[33mWARN\033[0m  artifacts are SYNTHETIC dev stand-ins, not the trained bundle")
    print(f"        origin={prov.get('origin')}")
else:
    print(f"  \033[32mPASS\033[0m  artifacts report origin={prov.get('origin', 'unknown')}")
print(("  \033[31mFAIL\033[0m  degraded components: " + ", ".join(deg)) if deg
      else "  \033[32mPASS\033[0m  degraded[] is empty - all artifacts loaded")
PY
else
  bad "GET / unreachable - is uvicorn running on $API ?"
fi
echo

# --- 2. endpoints the frontend consumes ------------------------------------
echo "[2] Endpoints consumed by the frontend"
for spec in \
  "GET|/dashboard/summary|vital-signs.tsx" \
  "GET|/production/history|production-chart.tsx" \
  "GET|/forecast?horizon=1|forecast-risk-panel.tsx" \
  "GET|/shortfall/risk|risk-gauge.tsx" \
  "GET|/recommendations|review-register.tsx" \
  "GET|/masks|site-inspector.tsx"
do
  IFS='|' read -r m path who <<< "$spec"
  c=$(code "$API$path")
  [ "$c" = 200 ] && ok "$m $path -> 200   ($who)" || bad "$m $path -> $c   ($who)"
done

c=$(code -X POST "$API/predict/point" -H 'Content-Type: application/json' -d '{"lat":21.73,"lon":79.52}')
[ "$c" = 200 ] && ok "POST /predict/point -> 200   (site-inspector.tsx)" \
                || bad "POST /predict/point -> $c   (site-inspector.tsx)"

c=$(code "$API/prospectivity/heatmap?min_lon=79.0&min_lat=21.3&max_lon=80.6&max_lat=22.1&grid_size=32&mask=none")
if [ "$c" = 200 ]; then
  ok "GET /prospectivity/heatmap -> 200   (map-canvas.tsx)"
  python3 - <<'PY'
import json
d = json.load(open('/tmp/glc.json'))
rows = d.get('scores') or []
flat = [v for r in rows for v in r]
nulls = sum(1 for v in flat if v is None)
nz = [v for v in flat if v is not None]
print(f"  \033[32mPASS\033[0m  lattice {len(rows)}x{len(rows[0]) if rows else 0}, "
      f"{len(nz)} scored, {nulls} no-data (null), model={d.get('model_version')}")
if nz and max(nz) > 0.99:
    print(f"  \033[33mWARN\033[0m  max score {max(nz)} exceeds the documented 0.99 cap "
          f"(float32 clip) - the frontend schema will reject it")
PY
else
  bad "GET /prospectivity/heatmap -> $c   (map-canvas.tsx)"
fi
echo

# --- 3. shape facts the adapters rely on -----------------------------------
echo "[3] Contract shape checks"
if [ "$(code "$API/forecast?horizon=3")" = 200 ]; then
  python3 - <<'PY'
import json
d = json.load(open('/tmp/glc.json'))
if isinstance(d.get('series'), list) and len(d['series']) == d.get('horizon_months'):
    print(f"  \033[32mPASS\033[0m  /forecast?horizon=3 returns series[] with {len(d['series'])} points")
    k = set(d['series'][0])
    want = {'month', 'predicted_tonnes', 'lower_ci', 'upper_ci'}
    print(("  \033[32mPASS\033[0m  series keys match the adapter" if want <= k
           else f"  \033[31mFAIL\033[0m  series keys are {sorted(k)}, adapter expects {sorted(want)}"))
else:
    print("  \033[33mWARN\033[0m  /forecast?horizon=3 has no series[] - chart falls back to 1 month")
    print("        Ask Yash to add a series array to GET /forecast.")
PY
fi
if [ "$(code "$API/production/history?start=2026-01&end=2026-05")" = 200 ]; then
  ok "/production/history accepts a date range"
else
  warn "/production/history 500s on ?start=&end= (report_month string vs pd.Period)"
fi
echo

# --- 4. CORS ---------------------------------------------------------------
echo "[4] CORS for the frontend dev ports"
for port in 3000 3001; do
  if curl -s -D- -o /dev/null -m 15 "$API/dashboard/summary" -H "Origin: http://localhost:$port" \
     | grep -qi "access-control-allow-origin"; then
    ok "origin http://localhost:$port allowed"
  else
    bad "origin http://localhost:$port NOT in the backend allowlist"
  fi
done
echo

printf 'Summary: \033[32m%d pass\033[0m, \033[33m%d warn\033[0m, \033[31m%d fail\033[0m\n' "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo
  echo "Ready. Enable live mode:"
  echo "  sed -i '' 's|^# NEXT_PUBLIC_API_BASE_URL|NEXT_PUBLIC_API_BASE_URL|' .env.local && npm run dev:sih"
fi
exit $(( FAIL > 0 ? 1 : 0 ))
