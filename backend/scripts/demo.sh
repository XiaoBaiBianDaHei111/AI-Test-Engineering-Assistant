#!/usr/bin/env bash
# Demo script (shell) — full workflow via REST (real DeepSeek + Playwright, P013).
# Usage:  ./scripts/demo.sh [BASE_URL]   (default http://localhost:8000/api)
# Outputs "DEMO PASSED" on success. Requires curl + python3.

set -euo pipefail
BASE_URL="${1:-http://localhost:8000/api}"

step() { printf '\033[36m[demo]\033[0m %s\n' "$1"; }
fail() { printf '\033[31mFAIL: %s\033[0m\n' "$1"; exit 1; }

jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)"; }

# Preflight: real mode requires a DeepSeek key (env var or repo-root .env).
if [ -z "${LLM_API_KEY:-}" ]; then
  env_file="$(dirname "$0")/../../.env"
  if ! { [ -f "$env_file" ] && grep -qE '^\s*LLM_API_KEY\s*=\s*\S+' "$env_file"; }; then
    fail "real mode requires a DeepSeek key: set LLM_API_KEY in the repo-root .env (or the environment) and restart the backend"
  fi
fi

# 1. health
step "health check"
health=$(curl -sf "$BASE_URL/health")
[ "$(echo "$health" | jget "['status']")" = "ok" ] || fail "health endpoint not ok"

# 2. project (timestamp name -> idempotent)
step "create project"
proj=$(curl -sf -X POST "$BASE_URL/projects" -H 'Content-Type: application/json' \
    -d "{\"name\":\"demo-$(date +%Y%m%d-%H%M%S)\",\"description\":\"demo\"}")
project_id=$(echo "$proj" | jget "['id']")

# 3. analyze requirement
step "analyze requirement"
ana=$(curl -sf -X POST "$BASE_URL/ai/analyze-requirement" -H 'Content-Type: application/json' \
    -d "{\"project_id\":$project_id,\"prd_text\":\"用户登录：输入用户名密码，成功跳转任务页\"}")
req_id=$(echo "$ana" | jget "['requirements'][0]['id']")

# 4. Gate 1
step "confirm requirement (Gate 1)"
req=$(curl -sf -X PATCH "$BASE_URL/requirements/$req_id" -H 'Content-Type: application/json' -d '{"status":"confirmed"}')
[ "$(echo "$req" | jget "['status']")" = "confirmed" ] || fail "requirement not confirmed"

# 5. extract test points
step "extract test points"
tp=$(curl -sf -X POST "$BASE_URL/ai/extract-test-points" -H 'Content-Type: application/json' \
    -d "{\"requirement_id\":$req_id}")
point_id=$(echo "$tp" | jget "['test_points'][0]['id']")

# 6. Gate 2
step "confirm test point (Gate 2)"
point=$(curl -sf -X PATCH "$BASE_URL/test-points/$point_id" -H 'Content-Type: application/json' -d '{"status":"confirmed"}')
[ "$(echo "$point" | jget "['status']")" = "confirmed" ] || fail "test point not confirmed"

# 7. generate test cases (poll)
step "generate test cases"
gen=$(curl -sf -X POST "$BASE_URL/ai/generate-test-cases" -H 'Content-Type: application/json' \
    -d "{\"project_id\":$project_id,\"test_point_ids\":[$point_id]}")
gen_run_id=$(echo "$gen" | jget "['run_id']")
gen_status="running"
for _ in $(seq 1 60); do
    gr=$(curl -sf "$BASE_URL/ai/generation-runs/$gen_run_id")
    gen_status=$(echo "$gr" | jget "['status']")
    [ "$gen_status" = "completed" ] || [ "$gen_status" = "partial" ] && break
    sleep 0.5
done
[ "$gen_status" = "completed" ] || [ "$gen_status" = "partial" ] || fail "generation failed: $gen_status"

# 8. first case
step "list generated cases"
cases=$(curl -sf "$BASE_URL/projects/$project_id/test-cases")
case_id=$(echo "$cases" | jget "[0]['id']")

# 9. review
step "review case (submit + approve)"
curl -sf -X POST "$BASE_URL/test-cases/$case_id/submit-review" > /dev/null
approved=$(curl -sf -X POST "$BASE_URL/test-cases/$case_id/review" -H 'Content-Type: application/json' -d '{"verdict":"approved"}')
[ "$(echo "$approved" | jget "['status']")" = "approved" ] || fail "case not approved"

# 10. run
step "execute run"
run=$(curl -sf -X POST "$BASE_URL/runs" -H 'Content-Type: application/json' \
    -d "{\"project_id\":$project_id,\"test_case_ids\":[$case_id],\"config\":{\"base_url\":\"http://localhost:8000\",\"qa_mode\":\"none\",\"browser\":\"chromium\",\"headless\":true}}")
run_id=$(echo "$run" | jget "['run_id']")
run_status="running"
for _ in $(seq 1 60); do
    r=$(curl -sf "$BASE_URL/runs/$run_id")
    run_status=$(echo "$r" | jget "['status']")
    [ "$run_status" = "completed" ] || [ "$run_status" = "failed" ] || [ "$run_status" = "cancelled" ] && break
    sleep 0.5
done
[ "$run_status" = "completed" ] || fail "run not completed: $run_status"

# 11. report
step "check report"
report=""
for _ in $(seq 1 20); do
    report=$(curl -sf "$BASE_URL/reports/$run_id" || true)
    [ -n "$report" ] && break
    sleep 0.3
done
[ -n "$report" ] || fail "report not generated"
report_id=$(echo "$report" | jget "['id']")

# 12. quality summary
step "generate quality summary"
summary=$(curl -sf -X POST "$BASE_URL/quality-summary/$report_id")
[ "$(echo "$summary" | jget "['recommendation']")" = "GO" ] || fail "quality summary not GO"

# 13. export
step "export report"
curl -sf "$BASE_URL/reports/$run_id/export?format=json" > /dev/null
curl -sf "$BASE_URL/reports/$run_id/export?format=markdown" > /dev/null

printf '\n\033[32mDEMO PASSED\033[0m  (project=%s, run=%s, report=%s)\n' "$project_id" "$run_id" "$report_id"
