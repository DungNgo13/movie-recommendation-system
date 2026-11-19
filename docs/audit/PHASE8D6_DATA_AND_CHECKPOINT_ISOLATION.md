# Phase 8D.6 — Data and Checkpoint Isolation

| Field | Value |
|---|---|
| **Run ID** | `phase8d_run_002` |
| **Phase** | 8D.6 — Data Isolation Analysis |
| **Date** | 2026-11-19 |

---

## Tóm tắt

Tài liệu này phân tích cách ly dữ liệu giữa run_001 và run_002. Run_001 sử dụng
thư mục `reports/phase8d_pilot/`, run_002 sử dụng thư mục riêng biệt
`reports/phase8d_pilot_run_002/`. Checkpoint run_001 (74/74) là bất biến và không
bị ảnh hưởng. Có hai vấn đề cần lưu ý: TEC collector có đường dẫn hardcoded và
hàm `_save_research_snapshot()` cũng tham chiếu đường dẫn cố định.

---

## 1. Directory Structure

```
backend/reports/
├── phase8d_pilot/                          ← Run 001 (IMMUTABLE)
│   ├── checkpoint/
│   │   └── checkpoint.json                 (74/74 exhausted, 0 successes)
│   ├── phase8d_pilot_manifest.json
│   ├── phase8d_preflight_report.json
│   ├── phase8d_data_quality_report.json
│   ├── phase8d_request_statistics.json
│   ├── phase8d_field_completeness.json
│   ├── phase8d_identity_matching_report.json
│   ├── phase8d_failure_report.json
│   ├── phase8d_full_catalog_estimate.json
│   └── phase8d_live_retrieval.log
│
└── phase8d_pilot_run_002/                  ← Run 002 (NEW — fresh start)
    ├── checkpoint/
    │   └── (empty — no prior checkpoint)
    ├── phase8d_pilot_manifest.json         (regenerated, same content)
    ├── phase8d_preflight_report.json
    ├── phase8d_data_quality_report.json
    ├── phase8d_request_statistics.json
    ├── phase8d_field_completeness.json
    ├── phase8d_identity_matching_report.json
    ├── phase8d_failure_report.json
    ├── phase8d_full_catalog_estimate.json
    └── phase8d_live_retrieval.log
```

---

## 2. Run_001 Immutability

> [!CAUTION]
> The run_001 data at `backend/reports/phase8d_pilot/` is **IMMUTABLE**.
> No process may read-write, modify, or delete any file in this directory.

### Checkpoint State (verified 2026-11-19):

```json
{
  "cumulative_requests": 74,
  "request_budget": 74,
  "completed_count": 22,
  "stats_snapshot": {
    "requests_total": 74,
    "requests_succeeded": 0,
    "api_failures": 19,
    "retry_count": 55,
    "budget_exhausted_count": 1
  }
}
```

### Why run_002 never touches run_001:

The CLI's `--output-dir reports/phase8d_pilot_run_002` flag sets:
- `phase8d_config.output_dir = Path("reports/phase8d_pilot_run_002")`
- `phase8d_config.checkpoint_dir = Path("reports/phase8d_pilot_run_002/checkpoint")`

All file operations in `run_live_pilot()` and `generate_pilot_quality_report()`
use `output_dir` as the base path. The run_001 directory is never referenced.

---

## 3. New Checkpoint Behavior

| Property | Value |
|---|---|
| Checkpoint path | `backend/reports/phase8d_pilot_run_002/checkpoint/` |
| Initial state | Empty directory (no `checkpoint.json`) |
| `prior_requests` | 0 (fresh start, no prior checkpoint loaded) |
| Lock file | `checkpoint_dir/pilot.lock` (exclusive `O_CREAT | O_EXCL`) |
| Checkpoint frequency | After each movie completes |

When `run_live_pilot()` calls `_load_checkpoint_state()`:
- It looks for `checkpoint_dir/checkpoint.json`
- In an empty directory → returns `prior_requests = 0`
- `TMDBClient` initialized with `initial_requests_total = 0`
- Full 74-request budget available from the start

---

## 4. Known Path Reference Issues

### Issue A: `_save_research_snapshot()` Hardcoded Paths

**Location:** `phase8d_live_pilot.py`, lines 1504–1509

The `_save_research_snapshot()` function may contain hardcoded references to
`backend/reports/phase8d_pilot/` in snapshot manifest artifact entries.

**Risk level:** LOW — The function uses `output_dir` for actual file writes.
The hardcoded paths are only in metadata/documentation references within the
snapshot artifact, not in file I/O operations.

**Mitigation:** Verify after run_002 that snapshot artifacts reference the
correct `phase8d_pilot_run_002` path.

### Issue B: TEC Collector Hardcoded Paths

**Location:** `test_center/collectors/phase8d_collector.py`

```python
# Lines 30-45 (approximate): Hardcoded paths
class Phase8DCollector:
    def __init__(self, settings):
        self.manifest_path = settings.backend_dir / "reports/phase8d_pilot/phase8d_pilot_manifest.json"
        self.quality_report_path = settings.backend_dir / "reports/phase8d_pilot/phase8d_data_quality_report.json"
```

**Risk level:** MEDIUM — The TEC collector will **not** auto-discover run_002
output at `reports/phase8d_pilot_run_002/`.

**Mitigation options:**

| Option | Effort | Impact |
|---|---|---|
| A. Modify collector to accept configurable path | Low | Clean solution |
| B. Add second collector instance for run_002 | Medium | Preserves run_001 collector |
| C. Manual report collection from run_002 directory | None | No code changes, manual verification |
| D. Post-run symlink or copy to expected path | Low | Quick workaround, risk of confusion |

**Recommendation:** Option C (manual verification) for run_002 — this is a pilot.
If a run_003 or full-catalog run is planned, implement Option A.

---

## 5. Manifest Identity

| Property | run_001 | run_002 |
|---|---|---|
| Seed | 8042 | 8042 |
| Pilot size | 40 | 40 |
| Movies with TMDB ID | 37 | 37 |
| Movies without TMDB ID | 3 | 3 |
| Checksum | `d23fc802...` | `d23fc802...` (must match) |

The manifest is **regenerated** by `select_phase8d_pilot()` using the same seed.
The deterministic selection guarantees identical movie lists. The checksum in
`phase8d_pilot_manifest.json` must match to confirm this.

> [!NOTE]
> The manifest file is regenerated (not copied) because the CLI always calls
> `select_phase8d_pilot()` and `generate_pilot_manifest()`. The content is
> identical due to deterministic seed-based selection.

---

## 6. Database Safety

| Aspect | Status |
|---|---|
| Production database writes | **NONE** — pilot does not write to any database |
| SQLite/PostgreSQL connections | Not opened during pilot execution |
| In-memory data only | All enrichment results stored in JSON files |
| Rollback needed | No — no database state to roll back |

---

## 7. Isolation Verification Commands

```powershell
# 1. Verify run_001 is untouched after run_002:
$cp1 = Get-Content "backend\reports\phase8d_pilot\checkpoint\checkpoint.json" | ConvertFrom-Json
Write-Output "run_001: $($cp1.cumulative_requests)/$($cp1.request_budget) requests"
# Expected: 74/74

# 2. Verify run_002 has its own checkpoint:
$cp2 = Get-Content "backend\reports\phase8d_pilot_run_002\checkpoint\checkpoint.json" | ConvertFrom-Json
Write-Output "run_002: $($cp2.cumulative_requests)/$($cp2.request_budget) requests"

# 3. Compare manifests:
$m1 = Get-Content "backend\reports\phase8d_pilot\phase8d_pilot_manifest.json" | ConvertFrom-Json
$m2 = Get-Content "backend\reports\phase8d_pilot_run_002\phase8d_pilot_manifest.json" | ConvertFrom-Json
Write-Output "Checksums match: $($m1.manifest_checksum -eq $m2.manifest_checksum)"
# Expected: True

# 4. Verify no cross-contamination:
Get-ChildItem "backend\reports\phase8d_pilot\" -Recurse | 
  Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-1) } |
  ForEach-Object { Write-Warning "run_001 file modified: $_" }
# Expected: no output (no recent modifications)
```
