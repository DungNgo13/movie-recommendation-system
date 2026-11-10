# Phase 8D — Network Diagnostics Report (Báo cáo chẩn đoán mạng)

**Date**: 2026-11-10  
**Phase**: Phase 8D — Controlled Live TMDB Pilot (40 movies)  
**Purpose**: Raw diagnostic data collected after pilot failure to identify TLS handshake root cause  
**Machine**: Windows, Wi-Fi Intel AX211, IP 172.35.53.78

---

## 1. Phân giải DNS / DNS Resolution

### 1.1 A Records (IPv4)

```
api.themoviedb.org → 3.175.86.103
                     3.175.86.37
                     3.175.86.50
                     3.175.86.67
```

**CDN**: Amazon CloudFront (3.175.86.x range)  
**Status**: ✅ OK — resolves to 4 IPv4 addresses

### 1.2 AAAA Records (IPv6)

```
api.themoviedb.org → 2600:9000:21b3:... (8 records)
```

**Status**: ✅ OK — resolves to 8 IPv6 addresses

### 1.3 Assessment

DNS resolution is functioning correctly. The domain resolves to Amazon CloudFront
edge servers, consistent with TMDB's CDN infrastructure. No DNS poisoning,
hijacking, or override detected.

---

## 2. Kết nối TCP / TCP Connectivity

| Parameter | Value |
|-----------|-------|
| **Target** | `api.themoviedb.org:443` |
| **Protocol** | TCP |
| **Result** | ✅ Connected |
| **Latency** | 277ms |
| **Assessment** | TCP 3-way handshake completes successfully; the server is network-reachable |

The 277ms latency is consistent with a connection from Vietnam to a CloudFront
edge server (likely in the Asia-Pacific region).

---

## 3. Bắt tay TLS / TLS Handshake

### 3.1 Result

| Parameter | Value |
|-----------|-------|
| **Target** | `api.themoviedb.org:443` |
| **Protocol** | TLS 1.3 (attempted) |
| **Result** | 🔴 **FAILED** |
| **Error** | `ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host` |
| **Phase** | During TLS ClientHello / ServerHello exchange |

### 3.2 Error Analysis

```
ConnectionResetError: [WinError 10054] An existing connection was forcibly
closed by the remote host
```

**WinError 10054** (`WSAECONNRESET`) indicates the remote host sent a TCP RST
(reset) segment. In the context of a TLS handshake:

1. Client sends TLS ClientHello (including SNI: `api.themoviedb.org`)
2. Before the server can respond with ServerHello, an intermediary or the
   server itself sends TCP RST
3. The connection is torn down before any TLS negotiation completes

### 3.3 Failure Consistency

All 74 HTTP attempts during the pilot produced this identical error:
- 19 movies reached the API layer (4 attempts each for 18 movies + 2 for 1 movie)
- Every attempt failed with the same `[WinError 10054]`
- No variation in error type or timing across the 86-second execution window

---

## 4. Kiểm thử TLS đối chứng / Control TLS Test

| Parameter | Value |
|-----------|-------|
| **Target** | `google.com:443` |
| **Protocol** | TLS 1.3 |
| **Result** | ✅ OK |
| **TLS Version** | TLSv1.3 |
| **Assessment** | The Python/OpenSSL TLS stack is fully functional |

This control test confirms:
- The client's TLS implementation works correctly
- OpenSSL 3.0.18 negotiates TLSv1.3 successfully
- The CA certificate store is valid and current
- The issue is **domain-specific** to `api.themoviedb.org`, not a general TLS failure

---

## 5. Phiên bản phần mềm / Software Versions

| Component | Version | Status |
|-----------|---------|--------|
| **Python** | 3.14.3 | ✅ Current |
| **OpenSSL** | 3.0.18 | ✅ Current |
| **httpx** | 0.28.1 | ✅ Current |
| **httpcore** | 1.0.9 | ✅ Current |
| **certifi** | 2026.06.17 | ✅ Current |
| **h2** | Not installed | ⚠️ HTTP/2 unavailable (HTTP/1.1 only) |

### 5.1 HTTP/2 Note

The `h2` package is not installed, so httpx operates in HTTP/1.1 mode only.
This is **not** the cause of the TLS failure — HTTP version negotiation occurs
after TLS handshake via ALPN extension, and the failure occurs before ALPN
negotiation. TMDB's API server supports HTTP/1.1.

---

## 6. Cấu hình proxy / Proxy Configuration

| Variable | Value |
|----------|-------|
| `HTTP_PROXY` | Not set |
| `HTTPS_PROXY` | Not set |
| `NO_PROXY` | Not set |
| `http_proxy` | Not set |
| `https_proxy` | Not set |
| httpx proxy config | None |

**Status**: ✅ No proxy configured — httpx connects directly to target hosts.

---

## 7. VPN / Enterprise Security Software

### 7.1 FortiClient

| Parameter | Value |
|-----------|-------|
| **Service** | FortiClient VPN Service Scheduler |
| **Status** | ⚠️ **Running** |
| **Type** | Enterprise VPN / Endpoint Security |
| **Capabilities** | VPN tunneling, web filtering, TLS/SSL deep packet inspection, application control |

**Significance**: FortiClient is a Fortinet enterprise security product that can
perform **TLS/SSL deep packet inspection**. When enabled, it intercepts TLS
connections, inspects the SNI (Server Name Indication) field in the ClientHello
message, and can selectively allow, block, or proxy connections based on URL
category policies.

The observed failure pattern (TCP OK → TLS RST) is consistent with FortiClient
or a Fortinet FortiGate appliance performing SNI-based domain blocking.

### 7.2 VirtualBox Adapters

VirtualBox Host-Only Ethernet Adapters detected (typical for development
environments). These do not route internet traffic and are not relevant to the
TMDB connection failure.

---

## 8. Tường lửa Windows / Windows Firewall

| Profile | Status |
|---------|--------|
| Domain | ✅ Enabled |
| Private | ✅ Enabled |
| Public | ✅ Enabled |

**Status**: ✅ Normal — Windows Firewall is enabled with default configuration on
all profiles. Windows Firewall operates at the network/transport layer and does
not perform TLS/SNI inspection. It is **not** the cause of the TLS handshake
failure.

---

## 9. Bộ mã hóa SSL / SSL Cipher Suites

### 9.1 Available Ciphers

**17 cipher suites** available in the Python/OpenSSL stack:

#### TLS 1.3 Ciphers (3)
| Cipher | Key Exchange | Authentication |
|--------|-------------|----------------|
| `TLS_AES_256_GCM_SHA384` | — | — |
| `TLS_CHACHA20_POLY1305_SHA256` | — | — |
| `TLS_AES_128_GCM_SHA256` | — | — |

#### TLS 1.2 Ciphers (14)
| Cipher | Key Exchange | Authentication |
|--------|-------------|----------------|
| `ECDHE-ECDSA-AES256-GCM-SHA384` | ECDHE | ECDSA |
| `ECDHE-RSA-AES256-GCM-SHA384` | ECDHE | RSA |
| `ECDHE-ECDSA-AES128-GCM-SHA256` | ECDHE | ECDSA |
| `ECDHE-RSA-AES128-GCM-SHA256` | ECDHE | RSA |
| `ECDHE-ECDSA-CHACHA20-POLY1305` | ECDHE | ECDSA |
| `ECDHE-RSA-CHACHA20-POLY1305` | ECDHE | RSA |
| `DHE-RSA-AES256-GCM-SHA384` | DHE | RSA |
| `DHE-RSA-AES128-GCM-SHA256` | DHE | RSA |
| `DHE-RSA-CHACHA20-POLY1305` | DHE | RSA |
| `ECDHE-ECDSA-AES256-SHA384` | ECDHE | ECDSA |
| `ECDHE-RSA-AES256-SHA384` | ECDHE | RSA |
| `ECDHE-ECDSA-AES128-SHA256` | ECDHE | ECDSA |
| `ECDHE-RSA-AES128-SHA256` | ECDHE | RSA |
| `DHE-RSA-AES256-SHA256` | DHE | RSA |

### 9.2 Assessment

✅ Full TLS 1.3 support with all 3 standard cipher suites. The cipher suite
configuration is complete and modern — no cipher negotiation mismatch can cause
the observed failure. The failure occurs before cipher negotiation begins.

---

## 10. Bảng định tuyến / Traceroute

| Hop | IP Range | Identity |
|-----|----------|----------|
| 1 | Gateway | Local router |
| 2 | ISP edge | Vietnamese ISP |
| 3 | 42.116.x.x | Vietnamese ISP backbone |
| 4 | Transit | International transit |
| 5 | 3.175.86.x | CloudFront edge (destination) |

**Total hops**: 5  
**ISP**: Vietnamese ISP (42.116.x.x range)  
**Status**: ✅ Normal route — traffic exits via Vietnamese ISP and reaches
CloudFront edge servers. No anomalous routing, blackholing, or loops detected.

---

## 11. Tập tin hosts / Hosts File

| Entry | Status |
|-------|--------|
| `api.themoviedb.org` override | ✅ **Not present** |
| Other TMDB overrides | ✅ **Not present** |

**Status**: ✅ Clean — the Windows hosts file does not contain any entries that
would redirect TMDB DNS resolution.

---

## 12. Giao diện mạng / Network Interfaces

### 12.1 Active Interface

| Parameter | Value |
|-----------|-------|
| **Adapter** | Wi-Fi |
| **Hardware** | Intel AX211 |
| **IPv4 Address** | 172.35.53.78 |
| **Connection** | Connected |
| **Speed** | Wi-Fi 6E |

### 12.2 Other Interfaces

- VirtualBox Host-Only Ethernet Adapter (multiple) — not routed to internet
- Loopback (127.0.0.1) — local only

---

## 13. Summary / Tổng kết

| Category | Result | Impact on TMDB |
|----------|--------|----------------|
| DNS | ✅ OK | No impact |
| TCP | ✅ OK (277ms) | No impact |
| TLS | 🔴 FAILED | **Root cause of pilot failure** |
| Control TLS | ✅ OK (google.com) | Confirms domain-specific issue |
| Software | ✅ Current | No impact |
| Proxy | ✅ None | No impact |
| VPN/Enterprise | ⚠️ FortiClient running | **Primary suspect** |
| Firewall | ✅ Normal | No impact |
| Ciphers | ✅ 17 available | No impact |
| Route | ✅ Normal (5 hops) | No impact |
| Hosts | ✅ Clean | No impact |
| Interface | ✅ Wi-Fi connected | No impact |

**Conclusion**: All diagnostic tests pass except the TLS handshake to
`api.themoviedb.org`. The failure is domain-specific and occurs at the
TLS/SNI layer, consistent with middlebox interception (FortiClient or ISP DPI).
See `PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` for detailed hypothesis evaluation.
