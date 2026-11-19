# Phase 8D.5 — Authenticated TMDB API Smoke Test (Kiểm tra xác thực API TMDB)

**Date**: 2026-11-19  
**Phase**: Phase 8D.5 — Authenticated Single-Request TMDB API Smoke Test  
**Execution ID**: `phase8d5_smoke_001`  
**Git Commit**: `7f027f8`  
**Final Classification**: **`AUTHENTICATED_API_VERIFIED`** — HTTP 200, valid JSON, all expected configuration keys present

---

## 1. Authorization Scope (Phạm vi phê duyệt)

The project owner explicitly authorized **exactly one (1)** authenticated HTTP GET request:

| Parameter | Authorized Limit | Actual | Compliance |
| :--- | :--- | :--- | :---: |
| **HTTP Requests** | `1` GET to `https://api.themoviedb.org/3/configuration` | **`1`** | ✅ PASS |
| **HTTP Method** | `GET` only | **`GET`** | ✅ PASS |
| **Endpoint** | `/3/configuration` only | **`/3/configuration`** | ✅ PASS |
| **Authentication** | Bearer token (TMDB API Read Access Token) | **Bearer token** | ✅ PASS |
| **Retries** | `0` | **`0`** | ✅ PASS |
| **Redirects** | `0` (`follow_redirects=False`) | **`0`** | ✅ PASS |
| **TLS Certificate Validation** | Enabled (no `verify=False`) | **Enabled (`verify=True`)** | ✅ PASS |
| **Token Exposure** | Zero — not printed, not logged, not in URL | **Zero** | ✅ PASS |
| **Production Database Writes** | `0` | **`0`** | ✅ PASS |
| **Phase 8D Pilot Restart** | Not permitted | **Not invoked** | ✅ PASS |
| **Previous Checkpoint (`run_001`)** | Preserved at `74/74` | **Untouched at `74/74`** | ✅ PASS |
| **Additional Endpoints** | None permitted | **None accessed** | ✅ PASS |
| **Push / Deploy** | Not permitted | **Not performed** | ✅ PASS |

---

## 2. Execution Timestamp (Thời điểm thực thi)

| Field | Value |
| :--- | :--- |
| **UTC** | `2026-11-19T03:22:32.465Z` |
| **Local (UTC+07:00)** | `2026-11-19T10:22:32.465+07:00` |

---

## 3. Git Commit (Phiên bản Git)

| Field | Value |
| :--- | :--- |
| **HEAD (short)** | `7f027f8` |
| **Working Tree** | Clean — no uncommitted changes at time of execution |

---

## 4. Network Verification (Xác minh mạng)

### 4.1 Router-Level 4G WAN Routing (Owner-Confirmed)

The project owner confirmed the following network topology:

- The laptop connects via Intel Wi-Fi to a local router (SSID not disclosed in report).
- The router's upstream WAN is configured to route outbound Internet traffic through a **4G cellular connection**.
- The laptop's LAN-side addressing (IP, gateway, interface) remains unchanged when the router switches between broadband and 4G WAN — this is expected behavior for router-level WAN routing and dual-WAN/policy-based routing configurations.

### 4.2 Prior Successful Connectivity Evidence

Before this smoke test, the owner provided evidence of successful TMDB connectivity on the same network configuration:

| Test | Result | Significance |
| :--- | :--- | :--- |
| Windows `curl.exe` / Schannel HTTPS to `api.themoviedb.org` | **HTTP 401** (unauthenticated) | Full HTTPS session established; TLS handshake succeeded |
| Python `ssl` / OpenSSL TLS handshake to `api.themoviedb.org:443` | **TLS 1.3 SUCCESS** | Python OpenSSL stack can complete TLS to TMDB |

Both tests used the same laptop IP (`172.35.53.78`) and gateway, confirming that identical local addressing does not indicate the previously blocked broadband path.

### 4.3 Routing Verification Classification

| Aspect | Method |
| :--- | :--- |
| Router 4G WAN active | **Owner-confirmed** (not independently verified from laptop) |
| TMDB TLS connectivity | **Independently verified** (prior curl HTTP 401 + Python TLS 1.3) |
| Smoke test HTTP 200 | **Independently verified** (this execution) |

> [!NOTE]
> The laptop cannot independently distinguish router-level WAN paths (broadband vs. 4G) because the LAN-side configuration is identical in both cases. The routing confirmation relies on the project owner's statement about the router's current WAN configuration, corroborated by the successful TLS and HTTP outcomes which were impossible on the previously documented broadband path (Phase 8D.3 CASE D).

---

## 5. Sanitized Execution Method (Phương pháp thực thi đã làm sạch)

### 5.1 Execution Stack

| Component | Version |
| :--- | :--- |
| **Python** | CPython `3.14.3` |
| **OpenSSL** | `OpenSSL 3.0.18 30 Sep 2025` |
| **httpx** | `0.28.1` |
| **Credential Source** | `backend/.env` via `python-dotenv` |

### 5.2 Request Configuration

```python
httpx.Client(
    timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
    follow_redirects=False,
    verify=True,  # Standard TLS certificate validation
)
# Headers: Authorization: Bearer [REDACTED], Accept: application/json
# URL: https://api.themoviedb.org/3/configuration
# Method: GET
# No retry transport configured
# Token loaded from .env, never printed or logged
```

---

## 6. HTTP Attempt Count (Số lần thử HTTP)

| Metric | Value |
| :--- | :--- |
| **Authorized Maximum** | `1` |
| **Actual Attempts Sent** | **`1`** |
| **Retries** | **`0`** |
| **Redirects Followed** | **`0`** |

---

## 7. HTTP Status Code (Mã trạng thái HTTP)

| Field | Value |
| :--- | :--- |
| **HTTP Status** | **`200 OK`** |
| **Content-Type** | `application/json;charset=utf-8` |

---

## 8. Response JSON Validation (Xác thực JSON phản hồi)

### 8.1 JSON Parse Result

| Check | Result |
| :--- | :--- |
| **Response parses as JSON** | ✅ `True` |
| **Top-level type is `dict`** | ✅ `True` |

### 8.2 Expected Configuration Keys

| Expected Key | Present? | Type |
| :--- | :---: | :--- |
| `images` | ✅ Yes | `dict` |
| `change_keys` | ✅ Yes | `list` |

### 8.3 `images` Sub-Structure

The `images` object contains the expected TMDB image configuration:

| Sub-Key | Present? |
| :--- | :---: |
| `base_url` | ✅ |
| `secure_base_url` | ✅ |
| `backdrop_sizes` | ✅ |
| `logo_sizes` | ✅ |
| `poster_sizes` | ✅ |
| `profile_sizes` | ✅ |
| `still_sizes` | ✅ |

`secure_base_url` is non-empty — this confirms the TMDB image CDN base URL is available for future metadata enrichment.

### 8.4 Validation Verdict

**All expected configuration fields are present with correct types.** The response matches the documented TMDB `/3/configuration` schema.

---

## 9. Latency (Độ trễ)

| Metric | Value |
| :--- | :--- |
| **Total Request Latency** | **`911.72 ms`** |

This includes DNS resolution, TCP connect, TLS 1.3 handshake, HTTP request/response, and JSON response transfer — all in a single round-trip via the router's 4G WAN connection.

---

## 10. Evidence Classification (Phân loại bằng chứng)

### **Classification: `AUTHENTICATED_API_VERIFIED`**

All conditions for `AUTHENTICATED_API_VERIFIED` are satisfied:

| Condition | Status |
| :--- | :--- |
| Exactly one GET was sent | ✅ `ATTEMPT_COUNT: 1` |
| HTTP 200 received | ✅ `HTTP_STATUS: 200` |
| Response parses as valid JSON | ✅ `JSON_VALID: True` |
| Expected TMDB configuration fields present | ✅ `CONFIG_KEYS_PRESENT: True` (`images` + `change_keys`) |
| No security or safety constraint violated | ✅ See Section 11 |

---

## 11. Security Checks (Kiểm tra bảo mật)

| Security Check | Status |
| :--- | :--- |
| **Token printed to stdout/stderr** | ✅ No — token value never appears in any output |
| **Authorization header logged** | ✅ No — no request headers were logged or persisted |
| **Token embedded in URL** | ✅ No — Bearer authentication used via `Authorization` header |
| **Token length/prefix/suffix disclosed** | ✅ No |
| **Certificate validation** | ✅ Enabled (`verify=True`, standard CA bundle) |
| **Redirects followed** | ✅ No (`follow_redirects=False`) |
| **Retries attempted** | ✅ No (`0` retries) |
| **Untrusted proxy used** | ✅ No |

---

## 12. Production Database Write Count (Số lần ghi cơ sở dữ liệu)

| Check | Value |
| :--- | :--- |
| **PostgreSQL/SQLite writes** | **`0`** |
| **ORM sessions opened** | **`0`** |
| **Database imports in script** | **`0`** |

The smoke test script imported only `datetime`, `json`, `sys`, `time`, `dotenv`, `httpx`, and `ssl`. No database drivers, ORM modules, or application models were loaded.

---

## 13. Previous Checkpoint Integrity (Tính toàn vẹn checkpoint trước đó)

Verified immediately after the smoke test:

| Checkpoint Field | Expected | Actual | Match? |
| :--- | :--- | :--- | :---: |
| `cumulative_requests` | `74` | **`74`** | ✅ |
| `request_budget` | `74` | **`74`** | ✅ |
| `stats_snapshot.requests_total` | `74` | **`74`** | ✅ |
| `stats_snapshot.requests_succeeded` | `0` | **`0`** | ✅ |
| `completed_count` | `22` | **`22`** | ✅ |

The Phase 8D `run_001` checkpoint at `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` was **not read, modified, or reset** by the smoke test. It remains exhausted at `74/74`.

---

## 14. Recommended Next Step (Bước tiếp theo được khuyến nghị)

The `AUTHENTICATED_API_VERIFIED` result confirms:

1. **Network path**: The router's 4G WAN successfully routes HTTPS traffic to `api.themoviedb.org` with TLS 1.3.
2. **Authentication**: The TMDB API Read Access Token in `backend/.env` is valid and accepted by TMDB.
3. **API schema**: The `/3/configuration` endpoint returns the expected JSON structure with image CDN configuration.
4. **Software stack**: Python 3.14.3, OpenSSL 3.0.18, httpx 0.28.1 all function correctly for authenticated TMDB API access.

**Recommended action**: Plan a **NEW, separately authorized Phase 8D recovery pilot** with:

- A new execution ID (e.g., `phase8d_run_002`)
- An independent request budget (separate from the exhausted `74/74`)
- A new report directory (e.g., `backend/reports/phase8d_pilot_run_002/`)
- Execution on the confirmed working 4G network path
- Circuit breaker enabled (`threshold=5`) as a safety net
- The same 40-movie manifest or a new owner-approved manifest

> [!IMPORTANT]
> Do **not** start the recovery pilot without separate, explicit project-owner authorization.
> Do **not** reset the existing `run_001` checkpoint.
> The recovery pilot requires its own authorization scope, budget allocation, and execution plan.

---

## 15. Tóm tắt cho Chủ dự án (Vietnamese Summary)

### Kết quả kiểm tra Phase 8D.5

1. **Phạm vi thực thi**: Đã gửi đúng **01 request GET duy nhất** được phê duyệt tới `https://api.themoviedb.org/3/configuration`, sử dụng xác thực Bearer token từ `backend/.env`.

2. **Kết quả**: **`AUTHENTICATED_API_VERIFIED`**
   - **HTTP 200 OK** — API phản hồi thành công
   - **JSON hợp lệ** — Chứa đầy đủ các trường cấu hình mong đợi (`images`, `change_keys`)
   - **Cấu hình hình ảnh TMDB** — URL CDN (`secure_base_url`) và danh sách kích thước (`backdrop_sizes`, `poster_sizes`, v.v.) đều có sẵn
   - **Độ trễ**: `911.72 ms` qua kết nối 4G WAN của router

3. **Bảo mật**: Token không bị lộ, không ghi log Authorization header, xác thực TLS được bật, không chuyển hướng (redirect), không thử lại (retry).

4. **Checkpoint**: `run_001` giữ nguyên ở mức `74/74` — không bị thay đổi.

5. **Cơ sở dữ liệu**: `0` lần ghi — không chạm tới PostgreSQL hoặc SQLite.

6. **Khuyến nghị**: Lập kế hoạch cho **pilot phục hồi mới** (`phase8d_run_002`) với:
   - Mã thực thi mới và ngân sách request riêng
   - Thực thi trên mạng 4G WAN đã xác nhận hoạt động
   - Circuit breaker bật sẵn để bảo vệ ngân sách
   - **Cần phê duyệt riêng của Chủ dự án trước khi bắt đầu**

---

## 16. References (Tài liệu tham chiếu)

| Document | Path |
| :--- | :--- |
| Phase 8D.3 TLS probe results | `docs/audit/PHASE8D3_TLS_PROBE_RESULTS.md` |
| Phase 8D.2 recovery readiness | `docs/audit/PHASE8D2_RECOVERY_READINESS.md` |
| Phase 8D.2 network comparison plan | `docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md` |
| Phase 8D live pilot results | `docs/audit/PHASE8D_LIVE_PILOT_RESULTS.md` |
| Phase 8D network diagnostics | `docs/audit/PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Previous checkpoint (`run_001`) | `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` |
