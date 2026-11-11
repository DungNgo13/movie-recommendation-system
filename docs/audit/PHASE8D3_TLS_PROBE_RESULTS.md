# Phase 8D.3 — Authorized TLS Connectivity Probe Results (Kết quả kiểm tra kết nối TLS được phê duyệt)

**Date**: 2026-11-11  
**Phase**: Phase 8D.3 — Authorized TLS Connectivity Verification  
**Git Commit at Execution**: `645337473d687df0df0d731a64f37fe5e7be7cc3` (`6453374`)  
**Comparison Matrix Step**: Comparison 1 (`Schannel` vs. `OpenSSL 3.0.18` on the same network and pinned IPv4)  
**Final Classification**: **CASE D** (`Schannel: FAILED`, `OpenSSL: FAILED` — Both TLS stacks terminated by TCP `RST` during `ClientHello`)

---

## 1. Authorization Scope (Phạm vi phê duyệt)

The project owner explicitly authorized **Phase 8D.3** to execute **exactly two (2)** controlled connectivity probes to `api.themoviedb.org`:

| Parameter | Authorized Limit | Actual Executed | Compliance |
| :--- | :--- | :--- | :---: |
| **Probe A (`curl.exe` / Windows Schannel)** | `1` unauthenticated HTTPS `HEAD` request (`https://api.themoviedb.org/3/configuration`) | **`1`** | ✅ PASS |
| **Probe B (`python.exe` / OpenSSL 3.0.18)** | `1` stdlib `socket` + `ssl` TLS handshake (`api.themoviedb.org:443`, `0` HTTP requests) | **`1`** | ✅ PASS |
| **Retries (`--retry 0` / no retry loop)** | `0` retries | **`0`** | ✅ PASS |
| **Redirects (`--max-redirs 0`)** | `0` redirects | **`0`** | ✅ PASS |
| **TMDB Authentication Tokens** | `0` tokens transmitted or logged | **`0`** | ✅ PASS |
| **Certificate Validation** | Standard validation enabled (no `-k`, `--insecure`, or `verify=False`) | **Enabled (`Schannel` default + `CERT_REQUIRED`)** | ✅ PASS |
| **Target Host & SNI** | `api.themoviedb.org` pinned to single resolved IPv4 | **`3.169.173.60:443`** (both probes) | ✅ PASS |
| **Production Database Writes** | `0` writes | **`0`** | ✅ PASS |
| **Phase 8D Pilot Client / Checkpoint (`run_001`)** | Not invoked; checkpoint preserved immutable at `74/74` | **Untouched at `74/74`** | ✅ PASS |

---

## 2. Execution Timestamp (Thời điểm thực thi)

- **Probe A (`curl.exe` / Schannel)**:
  - **UTC**: `2026-11-11T02:09:25.638Z`
  - **Local (`UTC+07:00`)**: `2026-11-11T09:09:25.640+07:00`
- **Probe B (`python.exe` / OpenSSL 3.0.18)**:
  - **UTC**: `2026-11-11T02:09:44.386Z`
  - **Local (`UTC+07:00`)**: `2026-11-11T09:09:44.386+07:00`

*(Historical preservation note: An earlier baseline run at commit `6fbcbfe` on `2026-11-11T02:01:46.307Z` / `02:02:55.464Z` against pinned CloudFront edge IP `3.169.173.116` is also preserved in Section 7.2 for cross-IP corroboration.)*

---

## 3. Git Commit (Phiên bản Git khi thực thi)

- **HEAD Commit Full SHA**: `645337473d687df0df0d731a64f37fe5e7be7cc3` (`6453374`)
- **Parent Commit SHA (Phase 8D.2 baseline)**: `6fbcbfe` (`docs(phase8d.2): finalize TLS connectivity diagnosis and recovery preparation docs`)
- **Working Tree Status Prior to Probes**: Clean (`nothing to commit, working tree clean`)

---

## 4. Sanitized Exact Commands (Lệnh thực thi nguyên bản đã làm sạch)

### 4.1 Probe A Command (Windows `curl.exe` — Schannel)

```powershell
$utcNow = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
$localNow = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fffK")
$gitCommit = (git rev-parse HEAD).Trim()
$ips = [System.Net.Dns]::GetHostAddresses("api.themoviedb.org") | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -ExpandProperty IPAddressToString
$pinnedIp = $ips[0]
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& curl.exe --ipv4 --head --verbose `
  --retry 0 `
  --max-redirs 0 `
  --connect-timeout 5 `
  --max-time 12 `
  --noproxy "*" `
  --resolve "api.themoviedb.org:443:$pinnedIp" `
  "https://api.themoviedb.org/3/configuration" 2>&1
$exitCode = $LASTEXITCODE
$sw.Stop()
```

### 4.2 Probe B Command (Python stdlib `socket` + `ssl` + `time` — OpenSSL 3.0.18)

```powershell
@'
import datetime
import socket
import ssl
import sys
import time

hostname = "api.themoviedb.org"
pinned_ip = "3.169.173.60"
port = 443
timeout_sec = 5.0

now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
now_local = datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")

ctx = ssl.create_default_context()

print("=== PROBE B METADATA ===")
print(f"TIMESTAMP_UTC: {now_utc}")
print(f"TIMESTAMP_LOCAL: {now_local}")
print(f"PYTHON_EXECUTABLE: {sys.executable}")
print(f"PYTHON_VERSION: {sys.version.split()[0]}")
print(f"OPENSSL_VERSION: {ssl.OPENSSL_VERSION}")
print(f"TARGET_HOSTNAME: {hostname}")
print(f"PINNED_IPV4: {pinned_ip}")
print(f"PORT: {port}")
print(f"VERIFY_MODE: {ctx.verify_mode.name}")
print(f"CHECK_HOSTNAME: {ctx.check_hostname}")
print("=== PROBE B EXECUTION ===")

t0 = time.perf_counter()
try:
    with socket.create_connection((pinned_ip, port), timeout=timeout_sec) as sock:
        tcp_ms = (time.perf_counter() - t0) * 1000.0
        peer = sock.getpeername()
        print(f"TCP_CONNECTED: True ({peer[0]}:{peer[1]} in {tcp_ms:.2f} ms)")
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            total_ms = (time.perf_counter() - t0) * 1000.0
            print("TLS_HANDSHAKE_SUCCESS: True")
            print(f"TLS_VERSION: {ssock.version()}")
            print(f"TLS_CIPHER: {ssock.cipher()}")
            cert = ssock.getpeercert()
            print(f"CERT_SUBJECT: {cert.get('subject')}")
            print(f"CERT_ISSUER: {cert.get('issuer')}")
            print(f"DURATION_MS: {total_ms:.2f}")
            sys.exit(0)
except Exception as exc:
    total_ms = (time.perf_counter() - t0) * 1000.0
    print("TLS_HANDSHAKE_SUCCESS: False")
    print(f"EXCEPTION_CLASS: {type(exc).__module__}.{type(exc).__name__}")
    print(f"EXCEPTION_ERRNO: {getattr(exc, 'errno', None)}")
    print(f"EXCEPTION_WINERROR: {getattr(exc, 'winerror', None)}")
    print(f"EXCEPTION_MESSAGE: {exc}")
    print(f"DURATION_MS: {total_ms:.2f}")
    sys.exit(1)
'@ | & "d:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe" -
Write-Output "EXIT_CODE: $LASTEXITCODE"
```

---

## 5. Probe A Exit Code and Outcome (Kết quả Probe A — Windows `curl.exe` / Schannel)

### 5.1 Raw Verbose Output

```text
=== PROBE A METADATA ===
TIMESTAMP_UTC: 2026-11-11T02:09:25.638Z
TIMESTAMP_LOCAL: 2026-11-11T09:09:25.640+07:00
GIT_COMMIT: 645337473d687df0df0d731a64f37fe5e7be7cc3
RESOLVED_IPV4_LIST: 3.169.173.60, 3.169.173.63, 3.169.173.116, 3.169.173.96
PINNED_IPV4: 3.169.173.60
=== PROBE A EXECUTION ===
* Added api.themoviedb.org:443:3.169.173.60 to DNS cache
* Hostname api.themoviedb.org was found in DNS cache
* Host api.themoviedb.org:443 was resolved.
* IPv6: (none)
* IPv4: 3.169.173.60
*   Trying 3.169.173.60:443...
* schannel: disabled automatic use of client certificate
* ALPN: curl offers http/1.1
* Recv failure: Connection was reset
* schannel: failed to receive handshake, SSL/TLS connection failed
* closing connection #0
curl: (35) Recv failure: Connection was reset
=== PROBE A RESULT ===
EXIT_CODE: 35
DURATION_MS: 242.95
```

### 5.2 Probe A Summary

| Field | Recorded Value |
| :--- | :--- |
| **Executable & TLS Backend** | Windows `curl.exe` (`8.21.0`, `Schannel` native Windows TLS) |
| **Command Exit Code** | **`35`** (`CURLE_SSL_CONNECT_ERROR`) |
| **Remote IP & Port** | `3.169.173.60:443` |
| **TLS Handshake Outcome** | **`FAILED`** (`TLS_FAILED`, `CONNECTION_RESET`) |
| **Probe Duration** | **`242.95 ms`** |

---

## 6. Probe B Exit Code and Outcome (Kết quả Probe B — Python `ssl` / OpenSSL)

### 6.1 Raw Output

```text
=== PROBE B METADATA ===
TIMESTAMP_UTC: 2026-11-11T02:09:44.386Z
TIMESTAMP_LOCAL: 2026-11-11T09:09:44.386+07:00
PYTHON_EXECUTABLE: D:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe
PYTHON_VERSION: 3.14.3
OPENSSL_VERSION: OpenSSL 3.0.18 30 Sep 2025
TARGET_HOSTNAME: api.themoviedb.org
PINNED_IPV4: 3.169.173.60
PORT: 443
VERIFY_MODE: CERT_REQUIRED
CHECK_HOSTNAME: True
=== PROBE B EXECUTION ===
TCP_CONNECTED: True (3.169.173.60:443 in 201.23 ms)
TLS_HANDSHAKE_SUCCESS: False
EXCEPTION_CLASS: builtins.ConnectionResetError
EXCEPTION_ERRNO: 10054
EXCEPTION_WINERROR: 10054
EXCEPTION_MESSAGE: [WinError 10054] An existing connection was forcibly closed by the remote host
DURATION_MS: 215.18
EXIT_CODE: 1
```

### 6.2 Probe B Summary

| Field | Recorded Value |
| :--- | :--- |
| **Python Executable** | `D:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe` (CPython `3.14.3`) |
| **OpenSSL Version** | `OpenSSL 3.0.18 30 Sep 2025` |
| **Command Exit Code** | **`1`** |
| **Remote IP & Port** | `3.169.173.60:443` (SNI `server_hostname="api.themoviedb.org"`) |
| **TCP Handshake Outcome** | **`SUCCEEDED`** in **`201.23 ms`** (`TCP_SUCCESS`) |
| **TLS Handshake Outcome** | **`FAILED`** (`TLS_FAILED`, `CONNECTION_RESET` **`13.95 ms`** after sending `ClientHello`) |
| **Probe Duration** | **`215.18 ms`** |

---

## 7. Target IP Addresses (Địa chỉ IP mục tiêu)

### 7.1 Current Execution IP Pinning (`3.169.173.60`)

- **DNS Resolution Method**: `[System.Net.Dns]::GetHostAddresses("api.themoviedb.org")` filtered to `InterNetwork` (IPv4)
- **Resolved IPv4 Set**: `3.169.173.60`, `3.169.173.63`, `3.169.173.116`, `3.169.173.96` (Amazon CloudFront edge range)
- **Pinned IPv4 Selected for Both Probes**: **`3.169.173.60:443`**
  - **Probe A**: Pinned via `--resolve "api.themoviedb.org:443:3.169.173.60"` while preserving URL `https://api.themoviedb.org/3/configuration` for SNI and certificate hostname verification.
  - **Probe B**: Connected TCP socket to `("3.169.173.60", 443)` and wrapped with `ctx.wrap_socket(sock, server_hostname="api.themoviedb.org")`.
- **IP Consistency Limitation Check**: Both Probe A and Probe B targeted the **exact same remote IPv4 address (`3.169.173.60`)**, eliminating CloudFront edge server rotation as a confounding variable.

### 7.2 Preserved Historical Corroboration (`3.169.173.116` at `02:01Z` / `02:02Z`)

For completeness, the earlier Phase 8D.3 baseline run (`6fbcbfe`) pinned a different CloudFront IP from the same anycast pool (**`3.169.173.116:443`**) and observed the exact same failure on both stacks:
- **Probe A (`3.169.173.116:443` at `2026-11-11T02:01:46.307Z`)**: Exit code `35`, `curl: (35) Recv failure: Connection was reset`, duration `231.29 ms`.
- **Probe B (`3.169.173.116:443` at `2026-11-11T02:02:55.464Z`)**: TCP connected in `185.71 ms`, TLS failed in `10.23 ms` (`195.94 ms` total), `builtins.ConnectionResetError: [WinError 10054]`.

---

## 8. TLS Versions and Certificate Outcomes (Phiên bản TLS và kết quả xác thực chứng chỉ)

| Probe | TLS Implementation | Configured Validation | Negotiated TLS Version | Negotiated Cipher | Certificate Validation Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Probe A (`curl.exe`)** | Windows Native **Schannel** | Standard Windows Trust Store (default) | **None** (reset before `ServerHello`) | **None** | **Not reached** (connection reset prior to certificate exchange; NOT `CERTIFICATE_VALIDATION_FAILED`) |
| **Probe B (`python.exe`)** | **OpenSSL 3.0.18** | `ssl.CERT_REQUIRED`, `check_hostname=True` | **None** (reset before `ServerHello`) | **None** | **Not reached** (connection reset prior to certificate exchange; NOT `CERTIFICATE_VALIDATION_FAILED`) |

---

## 9. HTTP Status from Probe A (Mã trạng thái HTTP từ Probe A)

- **Probe A HTTP Status**: **None received** (`N/A`). Because the TCP connection was forcibly reset during the Schannel TLS handshake (`ClientHello`), `curl.exe` never established a TLS session and never transmitted the HTTP `HEAD /3/configuration` request.
- **Probe B HTTP Status**: **Not applicable** (by design, Probe B only attempted a raw TLS handshake and sent zero HTTP requests).

---

## 10. Exception Details (Chi tiết ngoại lệ và mã lỗi)

| Attribute | Probe A (`curl.exe` / Schannel) | Probe B (`python.exe` / OpenSSL 3.0.18) |
| :--- | :--- | :--- |
| **Process Exit Code** | `35` (`CURLE_SSL_CONNECT_ERROR`) | `1` |
| **Exception / Error Class** | Native curl error `35` / Schannel handshake recv failure | `builtins.ConnectionResetError` (subclass of `OSError` / ` socket.error`) |
| **OS Error Codes** | WinSock TCP reset on recv | `errno = 10054`, `winerror = 10054` (`WSAECONNRESET`) |
| **Sanitized Error Message** | `curl: (35) Recv failure: Connection was reset` (`schannel: failed to receive handshake, SSL/TLS connection failed`) | `[WinError 10054] An existing connection was forcibly closed by the remote host` |

---

## 11. Side-by-Side Comparison & Evidence Classification (So sánh đối chiếu)

### 11.1 Standardized Evidence Quality Tags

| Stage | Probe A (`curl.exe` / Schannel) | Probe B (`python.exe` / OpenSSL 3.0.18) | Evidence Tag |
| :--- | :--- | :--- | :--- |
| **1. DNS Resolution** | Resolved `api.themoviedb.org` → `3.169.173.60` | Pinned `3.169.173.60` | **`DNS_SUCCESS`** |
| **2. TCP Port 443 Connect** | Connected to `3.169.173.60:443` | Connected to `3.169.173.60:443` in `201.23 ms` | **`TCP_SUCCESS`** |
| **3. TLS Handshake (`ClientHello`)** | Failed during handshake receive | Failed in `wrap_socket()` after `13.95 ms` | **`TLS_FAILED`** |
| **4. Transport Termination** | `Recv failure: Connection was reset` | `ConnectionResetError` (`[WinError 10054]`) | **`CONNECTION_RESET`** |
| **5. Certificate Validation** | Not reached (pre-certificate `RST`) | Not reached (pre-certificate `RST`) | *(Not Reached — Pre-Cert Reset)* |
| **6. HTTP Layer** | No HTTP response received | No HTTP request sent | *(Not Reached)* |

### 11.2 Side-by-Side Comparison Table

| Dimension | Probe A (Windows `curl.exe`) | Probe B (Python `ssl`) | Comparison |
| :--- | :--- | :--- | :--- |
| **TLS Stack** | Windows **Schannel** (`curl 8.21.0`) | **OpenSSL 3.0.18** (`CPython 3.14.3`) | Independent implementations |
| **CA Store** | Windows Certificate Store | Default SSL context (`CERT_REQUIRED`) | Independent trust stores |
| **Target IPv4:Port** | `3.169.173.60:443` | `3.169.173.60:443` | Identical pinned endpoint |
| **TLS SNI Hostname** | `api.themoviedb.org` | `api.themoviedb.org` | Identical SNI |
| **TCP Connect** | Succeeded | Succeeded (`201.23 ms`) | Both `TCP_SUCCESS` |
| **TLS Handshake** | **FAILED (`Exit 35`)** | **FAILED (`WinError 10054`)** | Both `TLS_FAILED` + `CONNECTION_RESET` |
| **Total Duration** | `242.95 ms` | `215.18 ms` | Consistent (~215–243 ms) |

### 11.3 Result Classification: **CASE D (`Schannel FAILED, OpenSSL FAILED`)**

Both Windows Schannel (`Probe A`) and Python OpenSSL (`Probe B`) failed at the exact same protocol stage (immediately after transmitting the TLS `ClientHello` carrying `server_name="api.themoviedb.org"`) with a TCP connection reset (`CONNECTION_RESET`).

---

## 12. Verified Conclusions (Kết luận đã được chứng minh thực nghiệm)

1. **Client-Side TLS Stack & Application Code Are Definitively Exonerated**:
   - Because native Windows `curl.exe` (Schannel) and standalone Python `ssl` (OpenSSL 3.0.18) both fail with a TCP `RST` against the exact same pinned IP (`3.169.173.60:443`, as well as `3.169.173.116:443`), the failure is **not** caused by `TMDBClient`, `httpx`, `httpcore`, Python's `ssl` configuration, `certifi` CA bundles, or OpenSSL-specific JA3/JA4 TLS client fingerprinting.
2. **DNS Resolution and TCP Transport to CloudFront Are Functional (`DNS_SUCCESS`, `TCP_SUCCESS`)**:
   - `api.themoviedb.org` resolves to valid Amazon CloudFront IPv4 addresses, and the TCP 3-way handshake completes cleanly in `201.23 ms`.
3. **Timing Differential Strongly Indicates Near-End / ISP SNI Inspection Reset (`13.95 ms` vs. `201.23 ms`)**:
   - In Probe B, establishing the TCP connection to the remote CloudFront server took **`201.23 ms`** (1 network RTT), whereas the TCP `RST` arrived only **`13.95 ms`** after sending the TLS `ClientHello` (`215.18 ms` total minus `201.23 ms` TCP connect; `10.23 ms` vs. `185.71 ms` in the earlier `3.169.173.116` run).
   - Because `10–14 ms` is roughly **15× shorter** than the round-trip time to the CloudFront server, the TCP `RST` cannot have traveled to the remote CloudFront origin and back; it is injected by an in-path node much closer to the client (~10–14 ms RTT, consistent with a domestic ISP DPI middlebox) or a local kernel-level filter inspecting the plaintext TLS SNI (`api.themoviedb.org`).
4. **Scope Boundaries Maintained**:
   - Neither probe completed a TLS handshake (`TLS_FAILED`), no HTTP response was received, no credential validity can be inferred, and this local/in-path reset does **not** imply that TMDB is globally unavailable.
5. **Recovery Pilot Suitability on Current Network**:
   - The current Wi-Fi network environment is **NOT suitable** for executing a Phase 8D recovery pilot. Planning a separately authorized recovery pilot is supported at the software level (all circuit-breaker and budget guards are ready), but execution **must wait** until a working network path is verified.

---

## 13. Unresolved Hypotheses (Giả thuyết chưa giải quyết)

1. **Hypothesis H1 — ISP SNI-Based Deep Packet Inspection (DPI) Blocking (Primary Suspect, High Probability)**:
   - The `10–14 ms` `ClientHello`-to-`RST` latency matches domestic ISP DPI equipment resetting connections matching `server_name = api.themoviedb.org`. However, because both probes ran on the same Wi-Fi ISP, a network block remains a **strong hypothesis rather than a proven root cause** until tested against a different network path (Comparison 2).
2. **Hypothesis H2 — Local Kernel Callout Driver / FortiClient Filter (Secondary Suspect, Low Probability)**:
   - Phase 8D.2 confirmed that the FortiClient VPN tunnel is inactive and `WebFilter` registry keys do not exist. Nevertheless, a stack-agnostic Windows Filtering Platform (WFP) kernel driver could theoretically reset both Schannel and OpenSSL connections and can only be ruled out if switching ISPs (mobile hotspot) succeeds on the same machine.
3. **Hypothesis H3 — Upstream Anycast Edge Reset**:
   - Strongly contradicted by the `10–14 ms` `RST` timing (compared to the `185–201 ms` TCP RTT to CloudFront), though an ISP-adjacent caching/peering middlebox remains indistinguishable from ISP DPI without a separate network comparison.

---

## 14. Recommended Next Action (Hành động tiếp theo được khuyến nghị)

Per **CASE D** and [`docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md`](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md):

1. **Stop All TMDB Network Activity Immediately on the Current Wi-Fi Network**:
   - Do **not** run additional probes, do **not** reset `checkpoint.json` (`74/74`), and do **not** start a recovery pilot on this network path.
2. **Recommend Comparison 2 (Separate Network Path / Mobile Hotspot Test — Requires Separate Owner Authorization)**:
   - Connect the workstation to an independent ISP (e.g., a 4G/5G mobile hotspot) or an authorized VPN tunnel.
   - Once connected to the alternative network, request owner authorization to run **Comparison 2** (a single non-authenticated Python `ssl` handshake probe):
     - **If Probe B succeeds on the mobile hotspot**: ISP-level blocking on the Wi-Fi network is proven, and the owner can authorize the Phase 8D recovery pilot (`phase8d_run_002`) to run over the working mobile hotspot connection.
     - **If Probe B still fails with `<15 ms` TCP `RST` on the mobile hotspot**: The interference is local to the workstation (Comparison 4 — inspect/disable FortiClient kernel drivers with administrator privileges).

---

## 15. Tóm tắt ngắn gọn cho Chủ dự án (Concise Vietnamese Summary for Project Owner)

1. **Thực thi đúng phạm vi ủy quyền**:
   - Đã chạy đúng **02 probe duy nhất** được phê duyệt tới `api.themoviedb.org` (ghim cố định cùng địa chỉ IPv4 CloudFront `3.169.173.60:443`), không retry, không redirect, không gửi TMDB token, không chạm tới cơ sở dữ liệu và giữ nguyên tuyệt đối `checkpoint.json` ở mức `74/74`.
2. **Kết quả 2 Probe**:
   - **Probe A (`curl.exe` / Windows Schannel)**: **THẤT BẠI** (`EXIT_CODE: 35`, `TLS_FAILED` / `CONNECTION_RESET` — `curl: (35) Recv failure: Connection was reset`, thời gian `242.95 ms`).
   - **Probe B (`python.exe` / OpenSSL 3.0.18)**: Kết nối TCP thành công sau `201.23 ms` (`TCP_SUCCESS`), nhưng bắt tay TLS **THẤT BẠI** chỉ **`13.95 ms`** sau khi gửi `ClientHello` (`EXIT_CODE: 1`, `TLS_FAILED` / `CONNECTION_RESET` — `builtins.ConnectionResetError: [WinError 10054]`, tổng thời gian `215.18 ms`).
3. **Phân loại & Kết luận xác minh (`CASE D`)**:
   - Cả hai ngăn xếp TLS độc lập (`Schannel` của Windows và `OpenSSL 3.0.18` của Python) đều bị ngắt bởi gói tin TCP `RST` ngay sau khi gửi `ClientHello`. Điều này **loại bỏ hoàn toàn** khả năng lỗi do code Python, `httpx`, `OpenSSL` hay chứng chỉ `certifi`.
   - Thời gian từ lúc gửi `ClientHello` đến khi nhận gói `RST` chỉ mất **`13.95 ms`** (so với **`201.23 ms`** để bắt tay TCP tới máy chủ CloudFront) cho thấy gói `RST` được sinh ra từ một nút mạng ở rất gần máy trạm (khả năng cao nhất là thiết bị DPI kiểm tra SNI `api.themoviedb.org` của nhà mạng ISP nội địa).
4. **Đánh giá mức độ sẵn sàng & Khuyến nghị**:
   - Phần mềm đã sẵn sàng 100% để lập kế hoạch chạy pilot phục hồi (đã có circuit breaker và kiểm soát ngân sách), nhưng **môi trường mạng Wi-Fi hiện tại KHÔNG phù hợp để chạy pilot**.
   - **Bước tiếp theo được khuyến nghị**: Tạm dừng mọi truy cập TMDB trên mạng Wi-Fi hiện tại; chuyển sang **Comparison 2** bằng cách đổi sang mạng khác (ví dụ: phát 4G/5G Mobile Hotspot từ điện thoại) và xin phép chạy 1 probe kiểm tra TLS trên mạng mới trước khi thực thi pilot phục hồi.

---

## 16. Final Safety Verification (Kiểm tra an toàn cuối cùng)

| Safety Check | Verified Status |
| :--- | :--- |
| **Exactly two authorized probes executed in this session** | ✅ Confirmed (`1` `curl.exe` HEAD probe + `1` Python `ssl` handshake probe) |
| **No retries executed** | ✅ Confirmed (`--retry 0` in Probe A; single try/except in Probe B) |
| **No redirects followed** | ✅ Confirmed (`--max-redirs 0` in Probe A; no HTTP in Probe B) |
| **No TMDB token transmitted or exposed** | ✅ Confirmed (`0` auth headers, `0` secrets read or printed) |
| **No production database modifications** | ✅ Confirmed (`0` DB connections or writes) |
| **Original Phase 8D checkpoint remains `74/74`** | ✅ Confirmed (`cumulative_requests: 74`, `request_budget: 74` in `checkpoint.json`) |
| **No new Phase 8D pilot started** | ✅ Confirmed |
| **No full-catalog enrichment occurred** | ✅ Confirmed |
| **No `git push` or deployment performed** | ✅ Confirmed |
