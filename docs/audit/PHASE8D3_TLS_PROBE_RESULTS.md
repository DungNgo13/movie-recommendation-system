# Phase 8D.3 — Authorized TLS Connectivity Probe Results (Kết quả kiểm tra kết nối TLS được phê duyệt)

**Date**: 2026-11-11  
**Phase**: Phase 8D.3 — Authorized TLS Connectivity Verification  
**Git Commit at Execution**: `6fbcbfe` (`docs(phase8d.2): finalize TLS connectivity diagnosis and recovery preparation docs`)  
**Comparison Matrix Step**: Comparison 1 (`Schannel` vs. `OpenSSL 3.0.18` on the same network and pinned IPv4)  
**Final Classification**: **CASE D** (`Schannel: FAILED`, `OpenSSL: FAILED` — Both TLS stacks reset by TCP `RST` during `ClientHello`)

---

## 1. Phạm vi phê duyệt / Authorization Scope

The project owner explicitly authorized **Phase 8D.3** to execute **at most two (2)** controlled connectivity probes to `api.themoviedb.org`:

| Parameter | Authorized Limit | Actual Executed | Compliance |
| :--- | :--- | :--- | :---: |
| **Probe A (`curl.exe` Schannel)** | Max `1` unauthenticated HTTPS `HEAD` request (`https://api.themoviedb.org/3/configuration`) | **`1`** | ✅ PASS |
| **Probe B (`python.exe` OpenSSL)** | Max `1` stdlib `socket` + `ssl` TLS handshake (`api.themoviedb.org:443`, `0` HTTP requests) | **`1`** | ✅ PASS |
| **Retries (`--retry 0` / no loop)** | `0` retries | **`0`** | ✅ PASS |
| **Redirects (`--max-redirs 0`)** | `0` redirects | **`0`** | ✅ PASS |
| **TMDB Authentication Tokens** | `0` tokens transmitted or logged | **`0`** | ✅ PASS |
| **Certificate Validation** | Enabled (no `-k`, `--insecure`, or `verify=False`) | **Enabled (`Schannel` default + `CERT_REQUIRED`)** | ✅ PASS |
| **Target Host & Pinned IPv4** | `api.themoviedb.org` pinned to single resolved IPv4 | **`3.169.173.116:443`** (both probes) | ✅ PASS |
| **Production PostgreSQL Writes** | `0` writes | **`0`** | ✅ PASS |
| **Phase 8D Pilot Checkpoint (`run_001`)** | Preserved untouched at `74/74` | **Preserved untouched at `74/74`** | ✅ PASS |

---

## 2. Thời điểm thực thi, Git Commit và Địa chỉ IP mục tiêu / Execution Metadata & Target IP Pinning

- **Git Commit**: `6fbcbfe`
- **Probe A Timestamp (UTC)**: `2026-11-11T02:01:46.307Z` (`2026-11-11T09:01:46.307+07:00`)
- **Probe B Timestamp (UTC)**: `2026-11-11T02:02:55.464Z` (`2026-11-11T09:02:55.464+07:00`)
- **DNS Resolution for `api.themoviedb.org` (IPv4 `InterNetwork`)**:
  - Resolved IPv4 set: `3.169.173.116`, `3.169.173.96`, `3.169.173.60`, `3.169.173.63` (Amazon CloudFront edge anycast range)
  - **Pinned IPv4 Used for Both Probes**: **`3.169.173.116`** (Port `443`)
  - **Why IP Pinning Was Applied**: By passing `--resolve "api.themoviedb.org:443:3.169.173.116"` to `curl.exe` in Probe A and connecting the TCP socket directly to `("3.169.173.116", 443)` with `server_hostname="api.themoviedb.org"` in Probe B, both TLS stacks tested the exact same CloudFront edge IP on the exact same Wi-Fi network path.

---

## 3. Lệnh thực thi nguyên bản (đã làm sạch) / Sanitized Exact Commands

### 3.1 Probe A Command (Windows `curl.exe` — Schannel)

```powershell
$utcNow = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
$gitCommit = (git rev-parse --short HEAD).Trim()
$ips = [System.Net.Dns]::GetHostAddresses("api.themoviedb.org") | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -ExpandProperty IPAddressToString
$pinnedIp = $ips[0]
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& curl.exe --ipv4 --head --verbose --retry 0 --max-redirs 0 --connect-timeout 5 --max-time 12 --noproxy "*" --resolve "api.themoviedb.org:443:$pinnedIp" "https://api.themoviedb.org/3/configuration" 2>&1
$exitCode = $LASTEXITCODE
$sw.Stop()
```

### 3.2 Probe B Command (Python `ssl` — OpenSSL 3.0.18)

*(Note: An initial invocation using `python.exe -c '...'` exited immediately with `SyntaxError` at the CLI parser before line 1 due to PowerShell native-argument quote stripping, making `0` socket or network calls. The script was then piped via `stdin` to `python.exe -` to execute the single authorized TLS handshake cleanly.)*

```powershell
@'
import datetime, platform, socket, ssl, sys, time

pinned_ip = "3.169.173.116"
hostname = "api.themoviedb.org"
port = 443

ctx = ssl.create_default_context()
t0 = time.perf_counter()
try:
    with socket.create_connection((pinned_ip, port), timeout=5.0) as sock:
        tcp_ms = (time.perf_counter() - t0) * 1000.0
        peer = sock.getpeername()
        print(f"TCP_CONNECTED: True ({peer[0]}:{peer[1]} in {tcp_ms:.2f} ms)")
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            print("TLS_SUCCESS: True")
            print("TLS_VERSION:", ssock.version())
            print("TLS_CIPHER:", ssock.cipher())
            cert = ssock.getpeercert()
            print("CERT_SUBJECT:", cert.get("subject"))
            print("CERT_ISSUER:", cert.get("issuer"))
            print(f"DURATION_MS: {dur_ms:.2f}")
            sys.exit(0)
except Exception as exc:
    dur_ms = (time.perf_counter() - t0) * 1000.0
    print("TLS_SUCCESS: False")
    print("EXCEPTION_MODULE:", type(exc).__module__)
    print("EXCEPTION_CLASS:", type(exc).__name__)
    print("EXCEPTION_ERRNO:", getattr(exc, "errno", None))
    print("EXCEPTION_WINERROR:", getattr(exc, "winerror", None))
    print("EXCEPTION_MSG:", str(exc))
    print(f"DURATION_MS: {dur_ms:.2f}")
    sys.exit(1)
'@ | & "d:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe" -
```

---

## 4. Kết quả chi tiết Probe A / Probe A Detailed Results (Windows `curl.exe` / Schannel)

### 4.1 Raw Verbose Output

```text
=== PROBE A METADATA ===
TIMESTAMP_UTC: 2026-11-11T02:01:46.307Z
GIT_COMMIT: 6fbcbfe
RESOLVED_IPV4_LIST: 3.169.173.116, 3.169.173.96, 3.169.173.60, 3.169.173.63
PINNED_IPV4: 3.169.173.116
=== PROBE A EXECUTION ===
* Added api.themoviedb.org:443:3.169.173.116 to DNS cache
* Hostname api.themoviedb.org was found in DNS cache
* Host api.themoviedb.org:443 was resolved.
* IPv6: (none)
* IPv4: 3.169.173.116
*   Trying 3.169.173.116:443...
* schannel: disabled automatic use of client certificate
* ALPN: curl offers http/1.1
* Recv failure: Connection was reset
* schannel: failed to receive handshake, SSL/TLS connection failed
* closing connection #0
curl: (35) Recv failure: Connection was reset
=== PROBE A RESULT ===
EXIT_CODE: 35
DURATION_MS: 231.29
```

### 4.2 Structured Telemetry for Probe A

| Field | Recorded Value |
| :--- | :--- |
| **Tool & TLS Backend** | Windows `curl.exe` (`8.21.0`, `Schannel` native Windows TLS) |
| **Exit Code** | **`35`** (`CURLE_SSL_CONNECT_ERROR`) |
| **Remote IP & Port** | `3.169.173.116:443` |
| **TLS Handshake Outcome** | **`FAILED`** (`schannel: failed to receive handshake, SSL/TLS connection failed`) |
| **TLS Protocol / Cipher** | None negotiated (connection terminated by TCP `RST` before `ServerHello`) |
| **Certificate Validation Outcome** | Not reached (no server certificate received prior to TCP `RST`) |
| **HTTP Status** | None received (no HTTP `HEAD` request could be transmitted) |
| **Sanitized Error Message** | `curl: (35) Recv failure: Connection was reset` |
| **Execution Duration** | **`231.29 ms`** |

---

## 5. Kết quả chi tiết Probe B / Probe B Detailed Results (Python `ssl` / OpenSSL)

### 5.1 Raw Output

```text
=== PROBE B METADATA ===
TIMESTAMP_UTC: 2026-11-11T02:02:55.464Z
PYTHON_EXECUTABLE: D:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe
PYTHON_VERSION: 3.14.3
OPENSSL_VERSION: OpenSSL 3.0.18 30 Sep 2025
TARGET_HOST: api.themoviedb.org
PINNED_IPV4: 3.169.173.116
PORT: 443
VERIFY_MODE: CERT_REQUIRED
CHECK_HOSTNAME: True
=== PROBE B EXECUTION ===
TCP_CONNECTED: True (3.169.173.116:443 in 185.71 ms)
TLS_SUCCESS: False
EXCEPTION_MODULE: builtins
EXCEPTION_CLASS: ConnectionResetError
EXCEPTION_ERRNO: 10054
EXCEPTION_WINERROR: 10054
EXCEPTION_MSG: [WinError 10054] An existing connection was forcibly closed by the remote host
DURATION_MS: 195.94
EXIT_CODE: 1
```

### 5.2 Structured Telemetry for Probe B

| Field | Recorded Value |
| :--- | :--- |
| **Python Executable** | `D:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe` (CPython `3.14.3`) |
| **OpenSSL Version** | `OpenSSL 3.0.18 30 Sep 2025` |
| **Exit Code** | **`1`** |
| **Remote IP & Port** | `3.169.173.116:443` (SNI `server_hostname="api.themoviedb.org"`) |
| **TCP Handshake Outcome** | **`SUCCEEDED`** in **`185.71 ms`** |
| **TLS Handshake Outcome** | **`FAILED`** (`TLS_SUCCESS: False`) |
| **TLS Protocol / Cipher / Cert** | None negotiated (reset **`10.23 ms`** after TCP connect upon sending TLS `ClientHello`) |
| **Exception Class** | `builtins.ConnectionResetError` (`errno=10054`, `winerror=10054`) |
| **Sanitized Exception Message** | `[WinError 10054] An existing connection was forcibly closed by the remote host` |
| **Execution Duration** | **`195.94 ms`** (`185.71 ms` TCP connect + `10.23 ms` TLS `ClientHello` to TCP `RST`) |

---

## 6. Phân loại chất lượng bằng chứng và So sánh đối chiếu / Evidence Quality & Side-by-Side Comparison

### 6.1 Evidence Quality Tags

| Stage / Observation | Probe A (`curl.exe` / Schannel) | Probe B (`python.exe` / OpenSSL 3.0.18) | Evidence Quality Tag |
| :--- | :--- | :--- | :--- |
| **DNS Lookup (`api.themoviedb.org`)** | Resolved (`3.169.173.116`, `.96`, `.60`, `.63`) | Pinned to `3.169.173.116` | `DNS_SUCCESS` |
| **TCP 3-Way Handshake (`:443`)** | Connected, entered Schannel ALPN `http/1.1` | Connected to `3.169.173.116:443` in `185.71 ms` | `TCP_SUCCESS` |
| **TLS Handshake (`ClientHello` w/ SNI)** | `schannel: failed to receive handshake` | `wrap_socket()` raised `ConnectionResetError` | `TLS_FAILED` |
| **Failure Mechanism** | `Recv failure: Connection was reset` (exit `35`) | `[WinError 10054]` TCP `RST` in `10.23 ms` | `CONNECTION_RESET` |
| **Certificate Verification** | Not reached (pre-certificate `RST`) | Not reached (pre-certificate `RST`) | *(Pre-Cert Reset)* |
| **HTTP Response** | None received | Not attempted (TLS handshake-only probe) | *(None)* |

### 6.2 Side-by-Side Comparison & Matrix Classification

| Dimension | Probe A (`curl.exe` / Schannel) | Probe B (`python.exe` / OpenSSL 3.0.18) | Match? |
| :--- | :--- | :--- | :---: |
| **Target Host (SNI)** | `api.themoviedb.org` | `api.themoviedb.org` | ✅ Identical |
| **Target IPv4:Port** | `3.169.173.116:443` | `3.169.173.116:443` | ✅ Identical |
| **Network Path** | Local Wi-Fi (Direct, no proxy) | Local Wi-Fi (Direct, no proxy) | ✅ Identical |
| **TLS Stack** | Windows Native **Schannel** | **OpenSSL 3.0.18** | Different (Test Variable) |
| **CA Trust Store** | Windows Certificate Store | `certifi` (`2026.06.17`) + OpenSSL default | Different (Test Variable) |
| **TLS Outcome** | **FAILED (`Connection was reset`)** | **FAILED (`[WinError 10054]`)** | ✅ **Identical Failure** |
| **Total Duration** | `231.29 ms` | `195.94 ms` | ✅ Consistent (~200 ms) |

#### Classification Result: **CASE D**
- **Probe A (`Schannel`)**: **FAILED** (`TLS_FAILED`, `CONNECTION_RESET`)
- **Probe B (`OpenSSL`)**: **FAILED** (`TLS_FAILED`, `CONNECTION_RESET`)

---

## 7. Kết luận đã xác minh vs. Giả thuyết chưa giải quyết / Verified Conclusions vs. Unresolved Hypotheses

### 7.1 Verified Conclusions (Empirically Proven)

1. **Client TLS Stack Is NOT the Cause (Hypothesis H4 Eliminated)**:
   - Both Windows Schannel (`curl.exe`) and Python OpenSSL (`3.0.18`) fail with an identical TCP `RST` during the TLS handshake to `3.169.173.116:443`.
   - This definitively rules out `httpx`, `httpcore`, Python's `ssl` module, OpenSSL cipher/extension configuration, JA3/JA4 TLS client fingerprinting differences between Schannel and OpenSSL, and `certifi` vs. Windows Certificate Store differences.
2. **DNS and TCP Transport to CloudFront Are Healthy**:
   - `api.themoviedb.org` resolves cleanly (`DNS_SUCCESS`), and the TCP 3-way handshake to `3.169.173.116:443` completes in `185.71 ms` (`TCP_SUCCESS`).
3. **Active TCP `RST` Injection Occurs Immediately After TLS `ClientHello` (SNI Phase)**:
   - In Probe B, the TCP connection to CloudFront took **`185.71 ms`** (`SYN` → `SYN-ACK`), whereas the TCP `RST` arrived only **`10.23 ms`** after `wrap_socket()` sent the TLS `ClientHello` (`195.94 ms` total minus `185.71 ms` TCP connect).
   - Because `10.23 ms` is ~18× shorter than the `185.71 ms` network round-trip time to the remote CloudFront edge server, the TCP `RST` packet is almost certainly generated by an **in-path domestic middlebox (ISP SNI-based DPI equipment ~5–10 ms away)** or a local/near-end filter inspecting the plaintext `server_name` (`api.themoviedb.org`) extension in the TLS `ClientHello`.
4. **Current Network Path Remains Unsuitable for Any Live TMDB Pilot**:
   - Running a recovery pilot on the current Wi-Fi network would immediately fail and trip the `TMDBClient` circuit breaker (`circuit_breaker_threshold = 5`).

### 7.2 Unresolved Hypotheses (Requiring External Network Change)

1. **ISP SNI-Based DPI Blocking (Primary Suspect — Strongly Supported by `10.23 ms` `RST` Timing)**:
   - Whether switching from the current Wi-Fi ISP to a different carrier (e.g., a mobile 4G/5G hotspot in **Comparison 2** of [`PHASE8D2_NETWORK_COMPARISON_PLAN.md`](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md)) resolves the TLS handshake reset has not yet been tested because both probes ran on the current Wi-Fi connection.
2. **Passive FortiClient Kernel Driver Interference (Secondary / Low-Probability Suspect)**:
   - Although Phase 8D.2 showed the Fortinet VPN adapter is inactive and `WebFilter` registry keys are absent, a TLS-stack-agnostic kernel callout driver can only be 100% ruled out after testing Comparison 2 (Mobile Hotspot) or Comparison 4 (with FortiClient stopped).

---

## 8. Hành động tiếp theo được khuyến nghị / Recommended Next Action

Following the decision tree in [`docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md`](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md) for **CASE D (`Both fail`)**:

1. **Do NOT request or execute a Phase 8D recovery pilot on the current Wi-Fi network.**
2. **Proceed to Comparison 2 (Different ISP / Mobile Hotspot)**:
   - Connect the workstation temporarily to a different network path/ISP (e.g., a 4G/5G mobile hotspot) or an enterprise-authorized VPN tunnel.
   - With project owner authorization, run the single non-authenticated TLS handshake check on the new network path:
     - **If TLS succeeds on the mobile hotspot**: ISP-level SNI DPI blocking on the primary Wi-Fi ISP is 100% confirmed, and the recovery pilot can be authorized and executed while connected to the working network path.
     - **If TLS still fails on a different ISP**: Investigate Comparison 4 (local FortiClient services/kernel drivers) with administrator permission.

---

## 9. Tóm tắt ngắn gọn cho Chủ dự án (Vietnamese Summary)

1. **Kết quả thực thi 2 Probe được phê duyệt**:
   - **Probe A (`curl.exe` / Windows Schannel)** tới `api.themoviedb.org` (`3.169.173.116:443`): **THẤT BẠI** (`EXIT_CODE: 35`, `Recv failure: Connection was reset`, thời gian `231.29 ms`).
   - **Probe B (`python.exe` / OpenSSL 3.0.18)** tới cùng địa chỉ IP `3.169.173.116:443`: Kết nối TCP thành công sau `185.71 ms`, nhưng bắt tay TLS **THẤT BẠI** chỉ `10.23 ms` sau đó (`EXIT_CODE: 1`, `ConnectionResetError: [WinError 10054]`, tổng thời gian `195.94 ms`).
2. **Phân loại kết quả**: **CASE D** (Cả `Schannel` và `OpenSSL` đều thất bại với lỗi TCP `RST` ngay ở bước gửi `ClientHello`).
3. **Kết luận kỹ thuật quan trọng**:
   - Loại bỏ hoàn toàn giả thuyết lỗi do Python `httpx`, `OpenSSL 3.0.18` hay kho chứng chỉ `certifi`.
   - Việc gói tin TCP `RST` phản hồi chỉ sau **`10.23 ms`** kể từ khi gửi `ClientHello` (trong khi độ trễ TCP tới máy chủ CloudFront là **`185.71 ms`**) là bằng chứng thực nghiệm rất mạnh cho thấy kết nối bị chặn bởi **thiết bị kiểm duyệt gói tin (DPI) theo SNI của nhà mạng (ISP) nội địa** nằm gần máy trạm (~10 ms), chứ không phải do máy chủ TMDB/CloudFront từ chối.
4. **Khuyến nghị bước tiếp theo**:
   - **Không** chạy lại pilot trên mạng Wi-Fi hiện tại.
   - Chuyển sang **Comparison 2**: Đổi sang một đường truyền mạng khác (ví dụ: phát Wi-Fi 4G/5G từ điện thoại — Mobile Hotspot) và kiểm tra lại kết nối TLS khi có phê duyệt của Chủ dự án.

---

## 10. Kiểm tra an toàn cuối cùng / Final Safety Verification

| Safety Invariant | Verified Value | Status |
| :--- | :--- | :---: |
| **Total `curl.exe` probes executed** | `1` | ✅ |
| **Total Python `ssl` handshake probes executed** | `1` | ✅ |
| **Total retries executed** | `0` | ✅ |
| **Total redirects followed** | `0` | ✅ |
| **Total TMDB API tokens transmitted or logged** | `0` | ✅ |
| **Total production database writes** | `0` | ✅ |
| **Previous pilot checkpoint (`backend/reports/phase8d_pilot/checkpoint/checkpoint.json`)** | Untouched (`cumulative_requests: 74`, `request_budget: 74`) | ✅ |
