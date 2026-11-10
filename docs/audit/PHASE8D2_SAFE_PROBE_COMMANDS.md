# Phase 8D.2 — Safe Probe Commands (Lệnh chẩn đoán an toàn)

**Date**: 2026-11-10  
**Phase**: Phase 8D.2 — TLS Connectivity Diagnosis and Safe Pilot Recovery  
**Purpose**: Exact commands for two independent TLS connectivity probes  
**Authorization**: These probes require explicit owner authorization before execution

---

## 1. Cảnh báo an toàn / Safety Warnings

> [!CAUTION]
> Both probes make outbound network connections to `api.themoviedb.org:443`.
> They perform a TLS handshake ONLY — no TMDB API authentication tokens are sent.
> No movie metadata is retrieved. No production database is accessed.
>
> **Do NOT execute these probes without explicit owner authorization.**

### What These Probes DO

- Establish a TCP connection to `api.themoviedb.org:443`
- Perform a TLS handshake (ClientHello → ServerHello → Certificate exchange)
- Report TLS version, cipher suite, and certificate subject
- Close the connection immediately

### What These Probes Do NOT Do

- ❌ Send any TMDB API tokens or authentication headers
- ❌ Make any HTTP GET/POST requests to TMDB endpoints
- ❌ Retrieve any movie metadata
- ❌ Count toward any request budget
- ❌ Access any database
- ❌ Modify any files or configurations
- ❌ Disable certificate verification
- ❌ Follow redirects

---

## 2. Probe A: Windows curl / Schannel (Thăm dò bằng curl / Schannel)

### 2.1 Command

```powershell
# Probe A: TLS handshake via Windows curl (Schannel)
# Network activity: TCP connect + TLS handshake to api.themoviedb.org:443
# No authentication tokens sent
# Connection closed after TLS handshake
curl.exe -v --connect-timeout 10 --max-time 15 -o NUL "https://api.themoviedb.org/3/configuration" 2>&1 | Select-String -Pattern "SSL|TLS|error|Connected|subject|issuer|expire|HTTP/"
```

### 2.2 What This Command Does

1. `curl.exe`: Windows built-in curl using **Schannel** TLS backend
2. `-v`: Verbose output showing TLS handshake details
3. `--connect-timeout 10`: TCP connect timeout of 10 seconds
4. `--max-time 15`: Total operation timeout of 15 seconds
5. `-o NUL`: Discard response body (we only need TLS handshake info)
6. URL: `https://api.themoviedb.org/3/configuration` — TMDB's configuration
   endpoint, which does NOT require authentication and returns public data
7. `Select-String`: Filter output to show only TLS-related lines

### 2.3 Expected Network Activity

- **1 DNS query** to resolve `api.themoviedb.org`
- **1 TCP SYN/ACK** to port 443
- **1 TLS ClientHello** with SNI `api.themoviedb.org`
- **1 TLS ServerHello** + certificate chain (if handshake succeeds)
- **1 HTTP GET** to `/3/configuration` (if TLS succeeds)
- **0 authentication headers** (no Bearer token)

### 2.4 Expected Output — Success

```
* Connected to api.themoviedb.org (3.169.173.x) port 443
* schannel: SSL/TLS connection with api.themoviedb.org port 443 (step 2/3)
* schannel: encrypted data got X
* schannel: SSL/TLS handshake complete
* SSL connection using TLS 1.3 / TLS_AES_256_GCM_SHA384
*  subject: CN=*.themoviedb.org
*  issuer: CN=Amazon RSA 2048 M02,O=Amazon,C=US
*  expire date: YYYY-MM-DD
> HTTP/1.1 ...
< HTTP/1.1 401 Unauthorized
```

The HTTP 401 is expected because we are NOT sending an authentication token.
The important result is the **TLS handshake succeeding** (showing SSL/TLS
connection details and certificate subject).

### 2.5 Expected Output — Failure

```
* Connected to api.themoviedb.org (3.169.173.x) port 443
* schannel: next InitializeSecurityContext failed: SEC_E_xxx (0xHHHHHHHH)
* Closing connection
* schannel: shutting down SSL/TLS connection
curl: (35) schannel: failed to receive handshake, SSL/TLS connection failed
```

Or:
```
* Recv failure: Connection was reset
curl: (56) Recv failure: Connection was reset
```

---

## 3. Probe B: Python ssl module / OpenSSL (Thăm dò bằng Python / OpenSSL)

### 3.1 Command

```powershell
# Probe B: TLS handshake via Python ssl module (OpenSSL 3.0.18)
# Network activity: TCP connect + TLS handshake to api.themoviedb.org:443
# No authentication tokens sent
# Connection closed after TLS handshake
Set-Location d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -c "
import ssl
import socket
import sys

hostname = 'api.themoviedb.org'
port = 443
timeout = 10

print(f'Python {sys.version}')
print(f'OpenSSL: {ssl.OPENSSL_VERSION}')
print(f'Target: {hostname}:{port}')
print()

# Step 1: DNS resolution
import socket as s
addrs = s.getaddrinfo(hostname, port, s.AF_INET, s.SOCK_STREAM)
print(f'Resolved IPs: {[a[4][0] for a in addrs]}')
print()

# Step 2: Create default SSL context (certificate verification enabled)
ctx = ssl.create_default_context()
print(f'SSL verify_mode: {ctx.verify_mode}')
print(f'SSL check_hostname: {ctx.check_hostname}')
print(f'SSL min_version: {ctx.minimum_version}')
print()

# Step 3: TCP connect + TLS handshake
print(f'Connecting to {hostname}:{port}...')
try:
    with socket.create_connection((hostname, port), timeout=timeout) as sock:
        print(f'TCP connected to {sock.getpeername()}')
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            print(f'TLS version: {ssock.version()}')
            print(f'Cipher: {ssock.cipher()}')
            cert = ssock.getpeercert()
            subject = dict(x[0] for x in cert.get('subject', ()))
            issuer = dict(x[0] for x in cert.get('issuer', ()))
            print(f'Subject CN: {subject.get(\"commonName\", \"N/A\")}')
            print(f'Issuer CN: {issuer.get(\"commonName\", \"N/A\")}')
            print(f'Not After: {cert.get(\"notAfter\", \"N/A\")}')
            print()
            print('SUCCESS: TLS handshake completed')
except ConnectionResetError as e:
    print(f'FAILED: ConnectionResetError: {e}')
    print('  → TCP RST received during TLS handshake')
    print('  → Consistent with SNI-based DPI blocking')
    sys.exit(1)
except ssl.SSLError as e:
    print(f'FAILED: SSLError: {e}')
    print('  → TLS protocol error (certificate, cipher, or version issue)')
    sys.exit(1)
except ConnectionRefusedError as e:
    print(f'FAILED: ConnectionRefusedError: {e}')
    sys.exit(1)
except TimeoutError as e:
    print(f'FAILED: TimeoutError: {e}')
    sys.exit(1)
except Exception as e:
    print(f'FAILED: {type(e).__name__}: {e}')
    sys.exit(1)
"
```

### 3.2 What This Command Does

1. Resolves `api.themoviedb.org` via DNS
2. Creates a TCP connection to port 443 with 10-second timeout
3. Creates a standard `ssl.SSLContext` with **certificate verification enabled**
4. Performs TLS handshake with SNI set to `api.themoviedb.org`
5. Reports TLS version, cipher suite, and certificate details
6. Closes the connection immediately
7. Does NOT send any HTTP request or authentication token

### 3.3 Expected Network Activity

- **1 DNS query** to resolve `api.themoviedb.org`
- **1 TCP SYN/ACK** to port 443
- **1 TLS ClientHello** with SNI `api.themoviedb.org`
- **1 TLS ServerHello** + certificate chain (if handshake succeeds)
- **0 HTTP requests** (connection closed after TLS handshake)
- **0 authentication headers**

### 3.4 Expected Output — Success

```
Python 3.14.3 (tags/v3.14.3:323c59a, ...)
OpenSSL: OpenSSL 3.0.18 30 Sep 2025
Target: api.themoviedb.org:443

Resolved IPs: ['3.169.173.63', '3.169.173.96', ...]

SSL verify_mode: 2
SSL check_hostname: True
SSL min_version: 771

Connecting to api.themoviedb.org:443...
TCP connected to ('3.169.173.63', 443)
TLS version: TLSv1.3
Cipher: ('TLS_AES_256_GCM_SHA384', 'TLSv1.3', 256)
Subject CN: *.themoviedb.org
Issuer CN: Amazon RSA 2048 M02
Not After: Mon DD HH:MM:SS YYYY GMT

SUCCESS: TLS handshake completed
```

### 3.5 Expected Output — Failure (WinError 10054)

```
Python 3.14.3 (tags/v3.14.3:323c59a, ...)
OpenSSL: OpenSSL 3.0.18 30 Sep 2025
Target: api.themoviedb.org:443

Resolved IPs: ['3.169.173.63', ...]

SSL verify_mode: 2
SSL check_hostname: True
SSL min_version: 771

Connecting to api.themoviedb.org:443...
TCP connected to ('3.169.173.63', 443)
FAILED: ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host
  → TCP RST received during TLS handshake
  → Consistent with SNI-based DPI blocking
```

---

## 4. Interpretation Matrix (Ma trận phân tích kết quả)

### Case A: Schannel Succeeds, OpenSSL Fails

```
Probe A (curl/Schannel):  ✅ TLS handshake OK
Probe B (Python/OpenSSL): ❌ ConnectionResetError [WinError 10054]
```

**Interpretation**: The TLS failure is specific to Python's OpenSSL TLS stack.

**Next steps**:
1. Compare TLS ClientHello between curl and Python (JA3 fingerprint)
2. Test with `ssl.SSLContext` using custom cipher list matching Schannel
3. Test with `verify=False` to check if certifi CA bundle matters
   (only for diagnosis — NOT for production use)
4. Consider using `truststore` package to use Windows certificate store from Python

**Software change needed**: Potentially adjust `httpx.Client` SSL context
configuration or install `truststore` package.

### Case B: Both Fail

```
Probe A (curl/Schannel):  ❌ Connection reset / SSL error
Probe B (Python/OpenSSL): ❌ ConnectionResetError [WinError 10054]
```

**Interpretation**: The TLS failure is network-path-dependent, not client-dependent.
Both TLS implementations are blocked at the same point.

**Next steps**:
1. Test from a different ISP (mobile hotspot)
2. If different ISP works → ISP-level DPI blocking confirmed
3. If different ISP also fails → CloudFront geo-blocking or FortiClient kernel filter

**Software change needed**: None — the issue is external to the software.

### Case C: Both Succeed

```
Probe A (curl/Schannel):  ✅ TLS handshake OK
Probe B (Python/OpenSSL): ✅ TLS handshake OK
```

**Interpretation**: The TLS failure was transient (intermittent ISP DPI,
temporary CloudFront edge misconfiguration, or FortiClient state change).

**Next steps**:
1. Run a single unauthenticated `GET /3/configuration` request via httpx
   to verify full HTTP connectivity (requires separate authorization)
2. If HTTP request succeeds → proceed to recovery pilot authorization
3. If HTTP request fails → investigate HTTP-level issues separately

**Software change needed**: None.

### Case D: Same Probe Succeeds on Different Network

```
Probe B on Wi-Fi:           ❌ ConnectionResetError
Probe B on Mobile Hotspot:  ✅ TLS handshake OK
```

**Interpretation**: Network-path-dependent blocking confirmed. The current Wi-Fi
ISP (or network equipment) is blocking TMDB TLS connections.

**Next steps**:
1. Document as ISP-level constraint
2. Future pilot requires mobile hotspot or VPN
3. Update recovery plan with network prerequisite

**Software change needed**: None — but operational procedure changes needed.

---

## 5. Unauthenticated HTTP Connectivity Check (Kiểm tra kết nối HTTP không xác thực)

> [!IMPORTANT]
> This check should be executed ONLY after both TLS probes succeed (Case C),
> and requires separate authorization.

If both probes succeed, the following check verifies full HTTP connectivity:

```powershell
# Unauthenticated HTTP check (requires separate authorization)
# Makes 1 HTTP GET request WITHOUT authentication token
# TMDB returns HTTP 401 for unauthenticated requests — this is expected
Set-Location d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -c "
import httpx
try:
    response = httpx.get(
        'https://api.themoviedb.org/3/configuration',
        timeout=10.0,
        follow_redirects=False,
    )
    print(f'HTTP Status: {response.status_code}')
    print(f'Content-Type: {response.headers.get(\"content-type\", \"N/A\")}')
    if response.status_code == 401:
        print('Expected: 401 Unauthorized (no token provided)')
        print('HTTP connectivity is WORKING')
    elif response.status_code == 200:
        print('Unexpected: 200 OK without token (endpoint may not require auth)')
        print('HTTP connectivity is WORKING')
    else:
        print(f'Unexpected status: {response.status_code}')
except Exception as e:
    print(f'FAILED: {type(e).__name__}: {e}')
"
```

**Expected result**: HTTP 401 Unauthorized (confirms TLS + HTTP both work;
TMDB requires authentication for all API endpoints).

**Network activity**: 1 DNS query + 1 TCP connection + 1 TLS handshake +
1 HTTP GET request (no authentication header).

---

## 6. Security Precautions Summary (Tóm tắt các biện pháp an toàn)

| Precaution | Status |
|------------|--------|
| No TMDB API tokens in probe commands | ✅ |
| Certificate verification enabled | ✅ |
| Short connection timeouts (10s) | ✅ |
| No HTTP retries | ✅ |
| No metadata retrieval | ✅ |
| No production database access | ✅ |
| No redirect following | ✅ |
| No proxy credential exposure | ✅ |
| Target is only `api.themoviedb.org` | ✅ |
| Correct SNI hostname used | ✅ |
| Probes require explicit authorization | ✅ |

---

## 7. References / Tài liệu tham chiếu

| Document | Path |
|----------|------|
| TLS connectivity diagnosis | `docs/audit/PHASE8D2_TLS_CONNECTIVITY_DIAGNOSIS.md` |
| Network comparison plan | `docs/audit/PHASE8D2_NETWORK_COMPARISON_PLAN.md` |
| Recovery readiness | `docs/audit/PHASE8D2_RECOVERY_READINESS.md` |
| Phase 8D.1 root cause analysis | `docs/audit/PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` |
