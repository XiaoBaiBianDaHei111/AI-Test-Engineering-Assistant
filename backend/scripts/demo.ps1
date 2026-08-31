# Demo script (PowerShell) — full workflow via REST (real DeepSeek + Playwright, P013).
# Usage:  .\scripts\demo.ps1 [ -BaseUrl http://localhost:8000/api ]
# Outputs "DEMO PASSED" on success.

param(
    [string]$BaseUrl = "http://localhost:8000/api"
)

$ErrorActionPreference = "Stop"

function Step([string]$name) { Write-Host "[demo] $name" -ForegroundColor Cyan }
function Fail([string]$msg) { Write-Host "FAIL: $msg" -ForegroundColor Red; exit 1 }
function Assert($cond, [string]$msg) { if (-not $cond) { Fail $msg } }

# Preflight: real mode requires a DeepSeek key (env var or repo-root .env).
$key = $env:LLM_API_KEY
if (-not $key) {
    $envPath = Join-Path (Split-Path $PSScriptRoot -Parent) "..\.env"
    if (Test-Path $envPath) {
        $match = Select-String -Path $envPath -Pattern '^\s*LLM_API_KEY\s*=\s*(\S+)' | Select-Object -First 1
        if ($match) { $key = $match.Matches[0].Groups[1].Value }
    }
}
if (-not $key) { Fail "real mode requires a DeepSeek key: set LLM_API_KEY in the repo-root .env (or the environment) and restart the backend" }

function PostJson([string]$path, $body) {
    Invoke-RestMethod -Uri "$BaseUrl$path" -Method Post `
        -Body ($body | ConvertTo-Json -Depth 10) -ContentType "application/json"
}
function PatchJson([string]$path, $body) {
    Invoke-RestMethod -Uri "$BaseUrl$path" -Method Patch `
        -Body ($body | ConvertTo-Json -Depth 10) -ContentType "application/json"
}

# 1. health
Step "health check"
$health = Invoke-RestMethod -Uri "$BaseUrl/health"
Assert ($health.status -eq "ok") "health endpoint not ok"

# 2. project (timestamp name -> idempotent across runs)
Step "create project"
$proj = PostJson "/projects" @{ name = "demo-$((Get-Date).ToString('yyyyMMdd-HHmmss'))"; description = "demo" }
$projectId = $proj.id
Assert ($projectId -gt 0) "project id missing"

# 3. analyze requirement (real DeepSeek)
Step "analyze requirement"
$ana = PostJson "/ai/analyze-requirement" @{ project_id = $projectId; prd_text = "用户登录：输入用户名密码，成功跳转任务页" }
Assert ($ana.requirements.Count -ge 1) "no requirements generated"
$reqId = $ana.requirements[0].id

# 4. Gate 1: confirm requirement
Step "confirm requirement (Gate 1)"
$req = PatchJson "/requirements/$reqId" @{ status = "confirmed" }
Assert ($req.status -eq "confirmed") "requirement not confirmed"

# 5. extract test points
Step "extract test points"
$tp = PostJson "/ai/extract-test-points" @{ requirement_id = $reqId }
Assert ($tp.test_points.Count -ge 1) "no test points generated"
$pointId = $tp.test_points[0].id

# 6. Gate 2: confirm test point
Step "confirm test point (Gate 2)"
$point = PatchJson "/test-points/$pointId" @{ status = "confirmed" }
Assert ($point.status -eq "confirmed") "test point not confirmed"

# 7. generate test cases (batch run -> poll)
Step "generate test cases"
$gen = PostJson "/ai/generate-test-cases" @{ project_id = $projectId; test_point_ids = @($pointId) }
$genRunId = $gen.run_id
$genStatus = "running"
for ($i = 0; $i -lt 60 -and $genStatus -notin @("completed", "partial", "failed"); $i++) {
    Start-Sleep -Milliseconds 500
    $gr = Invoke-RestMethod -Uri "$BaseUrl/ai/generation-runs/$genRunId"
    $genStatus = $gr.status
}
Assert ($genStatus -in @("completed", "partial")) "generation failed: $genStatus"

# 8. list test cases -> take the first
Step "list generated cases"
$cases = Invoke-RestMethod -Uri "$BaseUrl/projects/$projectId/test-cases"
Assert ($cases.Count -ge 1) "no test cases generated"
$caseId = $cases[0].id

# 9. review: submit + approve
Step "review case (submit + approve)"
$null = Invoke-RestMethod -Uri "$BaseUrl/test-cases/$caseId/submit-review" -Method Post
$approved = PostJson "/test-cases/$caseId/review" @{ verdict = "approved" }
Assert ($approved.status -eq "approved") "case not approved"

# 10. run (UI execution, real Playwright)
Step "execute run"
$run = PostJson "/runs" @{
    project_id = $projectId
    test_case_ids = @($caseId)
    config = @{ base_url = "http://localhost:8000"; qa_mode = "none"; browser = "chromium"; headless = $true }
}
$runId = $run.run_id
$runStatus = "running"
for ($i = 0; $i -lt 60 -and $runStatus -notin @("completed", "failed", "cancelled"); $i++) {
    Start-Sleep -Milliseconds 500
    $r = Invoke-RestMethod -Uri "$BaseUrl/runs/$runId"
    $runStatus = $r.status
}
Assert ($runStatus -eq "completed") "run not completed: $runStatus"

# 11. report (auto-generated)
Step "check report"
$report = $null
for ($i = 0; $i -lt 20 -and $null -eq $report; $i++) {
    Start-Sleep -Milliseconds 300
    try { $report = Invoke-RestMethod -Uri "$BaseUrl/reports/$runId" } catch { }
}
Assert ($null -ne $report) "report not generated"
Assert ($report.summary.passed -ge 1) "report summary unexpected"

# 12. quality summary (GO rule recompute)
Step "generate quality summary"
$summary = Invoke-RestMethod -Uri "$BaseUrl/quality-summary/$($report.id)" -Method Post
Assert ($summary.recommendation -eq "GO") "quality summary not GO"

# 13. export (JSON + Markdown)
Step "export report"
$null = Invoke-RestMethod -Uri "$BaseUrl/reports/$runId/export?format=json"
$null = Invoke-RestMethod -Uri "$BaseUrl/reports/$runId/export?format=markdown"

Write-Host ""
Write-Host "DEMO PASSED  (project=$projectId, run=$runId, report=$($report.id), recommendation=$($summary.recommendation))" -ForegroundColor Green
