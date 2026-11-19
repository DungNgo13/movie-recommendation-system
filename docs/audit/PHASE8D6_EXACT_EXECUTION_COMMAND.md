# Phase 8D.6 — Exact Execution Command

| Field | Value |
|---|---|
| **Run ID** | `phase8d_run_002` |
| **Phase** | 8D.6 — Execution Reference |
| **Date** | 2026-11-19 |

---

## Tóm tắt

Hướng dẫn chính xác để thực thi pilot run_002, bao gồm: biến môi trường, tạo thư
mục, lệnh CLI chính xác, giải thích từng tham số, lệnh xác minh sau thực thi, và
quy trình rollback. Tất cả lệnh sử dụng PowerShell trên Windows.

> [!IMPORTANT]
> **Không thực thi** cho đến khi chủ dự án cung cấp ủy quyền rõ ràng cho run_002.

---

## 1. Required Environment Variables

Set these in the **same PowerShell session** that will run the pilot:

```powershell
# Authorization gate
$env:PHASE8D_LIVE_AUTHORIZED = "true"

# Enable live TMDB requests in TMDBClient
$env:TMDB_ENABLE_LIVE_REQUESTS = "true"

# API token is loaded from backend/.env by python-dotenv (do NOT set in shell)
# Verify it exists:
Set-Location d:\TLTN\movie-recommendation-system\backend
.venv\Scripts\python.exe -c "from dotenv import dotenv_values; v=dotenv_values('.env'); print(f'Token present: {bool(v.get(\"TMDB_API_READ_ACCESS_TOKEN\",\"\").strip())}')"
```

| Variable | Value | Source |
|---|---|---|
| `PHASE8D_LIVE_AUTHORIZED` | `true` | Shell env (set above) |
| `TMDB_ENABLE_LIVE_REQUESTS` | `true` | Shell env (set above) |
| `TMDB_API_READ_ACCESS_TOKEN` | (from file) | `backend/.env` via `python-dotenv` |

> [!CAUTION]
> Never expose the actual `TMDB_API_READ_ACCESS_TOKEN` value in commands, logs,
> or report output. The `SecretRedactionFilter` in `phase8d_live_pilot.py` redacts
> it from log output automatically.

---

## 2. Pre-Execution Directory Setup

```powershell
# Create run_002 output and checkpoint directories:
New-Item -ItemType Directory -Force -Path "d:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot_run_002\checkpoint"

# Verify no stale lock file:
$lockPath = "d:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot_run_002\checkpoint\pilot.lock"
if (Test-Path $lockPath) {
    Write-Warning "Stale lock file found — remove before execution:"
    Write-Warning "  Remove-Item '$lockPath'"
} else {
    Write-Output "OK: No stale lock file"
}

# Verify run_001 checkpoint is intact:
$cp = Get-Content "d:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot\checkpoint\checkpoint.json" | ConvertFrom-Json
Write-Output "run_001 checkpoint: $($cp.cumulative_requests)/$($cp.request_budget)"
# Expected output: run_001 checkpoint: 74/74
```

---

## 3. Exact Execution Command

```powershell
Set-Location d:\TLTN\movie-recommendation-system\backend

.venv\Scripts\python.exe -m app.recommendation_evaluation.cli `
    --phase8d `
    --phase8d-live `
    --output-dir reports/phase8d_pilot_run_002
```

### Flag Reference

| Flag | Purpose | Value |
|---|---|---|
| `--phase8d` | Activates Phase 8D controlled live pilot mode | (boolean flag) |
| `--phase8d-live` | Enables live TMDB HTTP requests | (boolean flag, requires `PHASE8D_LIVE_AUTHORIZED=true`) |
| `--output-dir` | Directs all output to run_002 directory | `reports/phase8d_pilot_run_002` |

### Implicit Defaults (correct for run_002)

| Flag | Default | Effect |
|---|---|---|
| `--phase8d-pilot-size` | 40 | Selects 40 movies |
| `--phase8d-request-budget` | 74 | Maximum HTTP attempts |

---

## 4. How the CLI Processes This Command

### Step-by-step execution flow:

1. **`cli.py` line 255:** `if args.phase8d:` — enters Phase 8D branch
2. **`cli.py` lines 257–260:** Loads `.env` via `python-dotenv`
3. **`cli.py` line 262:** Since `--output-dir` is not the default value,
   uses the provided `reports/phase8d_pilot_run_002`
4. **`cli.py` lines 280–284:** Calls `Phase8DPilotConfig.from_args()`:
   - `pilot_size=40`
   - `seed=8042`
   - `request_budget=74`
   - `live=True` (from `--phase8d-live`)
5. **`phase8d_live_pilot.py` line 118–122:** Authorization check:
   - `env_authorized = os.getenv("PHASE8D_LIVE_AUTHORIZED") == "true"` → `True`
   - `is_live = bool(True and True)` → `True`
   - `clamped_budget = min(74, 74)` → `74`
6. **`cli.py` lines 286–287:** Sets `output_dir` and `checkpoint_dir`
7. **`cli.py` line 290:** Selects 40 pilot movies with `seed=8042`
8. **`cli.py` line 294:** Generates manifest (same content, fresh file)
9. **`cli.py` line 303:** Runs 8 preflight checks
10. **`cli.py` line 310:** Verifies authorization gate
11. **`cli.py` line 320:** Calls `run_live_pilot()` — **this is where HTTP requests happen**
12. **`cli.py` line 321:** Generates quality report

---

## 5. Expected Console Output

On successful execution, the CLI prints:

```
======================================================================
 PHASE 8D: Controlled Live TMDB Pilot
======================================================================
Pilot size: 40 | Mode: LIVE
Authorization: AUTHORIZED
Preflight checks (1-7): PASSED
Total attempted: 37
Successful: ?? | Conflicts: ??
Skipped: 3 | API errors: ?? | Not attempted: ??
Total HTTP attempts: ??/74 (max RPS: ?.??)
Verification mode: LIVE_VERIFIED
Latency: p50=???.?ms, p95=???.?ms
Reports saved to: D:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot_run_002
======================================================================
```

---

## 6. Post-Execution Verification

```powershell
# 1. Check run_002 quality report summary:
$qr = Get-Content "backend\reports\phase8d_pilot_run_002\phase8d_data_quality_report.json" | ConvertFrom-Json
$s = $qr.summary
Write-Output "Mode: $($s.verification_mode)"
Write-Output "Attempted: $($s.total_attempted) | Successful: $($s.successful)"
Write-Output "HTTP attempts: $($s.total_requests)/$($s.request_budget)"
Write-Output "API errors: $($s.api_errors) | Skipped: $($s.skipped)"

# 2. Verify run_001 checkpoint is UNCHANGED:
$cp1 = Get-Content "backend\reports\phase8d_pilot\checkpoint\checkpoint.json" | ConvertFrom-Json
Write-Output "run_001: $($cp1.cumulative_requests)/$($cp1.request_budget)"
# MUST be: 74/74

# 3. Check run_002 checkpoint:
$cp2 = Get-Content "backend\reports\phase8d_pilot_run_002\checkpoint\checkpoint.json" | ConvertFrom-Json
Write-Output "run_002: $($cp2.cumulative_requests)/$($cp2.request_budget)"
Write-Output "run_002 succeeded: $($cp2.stats_snapshot.requests_succeeded)"

# 4. Verify manifest checksum match:
$m1 = Get-Content "backend\reports\phase8d_pilot\phase8d_pilot_manifest.json" | ConvertFrom-Json
$m2 = Get-Content "backend\reports\phase8d_pilot_run_002\phase8d_pilot_manifest.json" | ConvertFrom-Json
Write-Output "Manifest checksums match: $($m1.manifest_checksum -eq $m2.manifest_checksum)"

# 5. List generated files:
Get-ChildItem "backend\reports\phase8d_pilot_run_002" -Recurse |
    Format-Table Name, Length, LastWriteTime -AutoSize
```

---

## 7. Rollback Procedure

If run_002 must be discarded entirely:

```powershell
# Remove all run_002 output (run_001 is never touched):
Remove-Item -Recurse -Force "d:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot_run_002"

# Verify run_001 is intact:
$cp = Get-Content "d:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot\checkpoint\checkpoint.json" | ConvertFrom-Json
Write-Output "run_001: $($cp.cumulative_requests)/$($cp.request_budget)"
# MUST be: 74/74
```

---

## 8. TEC Report Generation

> [!WARNING]
> The TEC collector (`test_center/collectors/phase8d_collector.py`) currently has
> hardcoded paths pointing to `reports/phase8d_pilot/`. It will collect run_001
> results, **not** run_002 results, without path modification.

### To collect run_002 results via TEC:

**Option A (manual):** Read run_002 JSON reports directly from the output directory.

**Option B (code change):** Modify `Phase8DCollector.__init__()` to accept a
configurable report path:

```python
# In phase8d_collector.py:
def __init__(self, settings, report_dir="reports/phase8d_pilot"):
    self.manifest_path = settings.backend_dir / report_dir / "phase8d_pilot_manifest.json"
    self.quality_report_path = settings.backend_dir / report_dir / "phase8d_data_quality_report.json"
```

Then run:
```powershell
# Standard TEC collection (will read run_001 by default):
Set-Location d:\TLTN\movie-recommendation-system\backend
.venv\Scripts\python.exe -m test_center.cli
```

---

## 9. Git Commit (Post-Execution)

After successful run_002 execution and verification:

```powershell
Set-Location d:\TLTN\movie-recommendation-system
git add docs/audit/PHASE8D6_*.md
git add backend/reports/phase8d_pilot_run_002/
git commit -m "docs(phase8d.6): recovery pilot run_002 results via router 4G WAN"
```

> [!NOTE]
> Do NOT push or deploy. Do NOT modify run_001 files. The commit captures
> run_002 results for local audit trail only.
