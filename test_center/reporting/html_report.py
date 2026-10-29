"""HTML report generator for the MovSug Test & Evaluation Center.

Generates a self-contained, offline-capable HTML report with embedded CSS and JS.
No external CDN dependencies — everything is inlined.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known metric directionality: True = higher is better, False = lower is better
# ---------------------------------------------------------------------------
_HIGHER_IS_BETTER: dict[str, bool] = {
    "precision": True, "recall": True, "ndcg": True,
    "hit_rate": True, "map": True, "catalog_coverage": True,
    "intra_list_diversity": True, "novelty": True,
    "p50_ms": False, "p90_ms": False, "p95_ms": False, "mean_ms": False,
}


def _esc(value: Any) -> str:
    """HTML-escape a value."""
    return html.escape(str(value))


def _status_class(status: str) -> str:
    """Map a status string to a CSS class name."""
    s = status.upper()
    if s in ("PASS", "PASSED", "SUCCESS"):
        return "status-pass"
    if s in ("FAIL", "FAILED", "ERROR"):
        return "status-fail"
    if s in ("SKIP", "SKIPPED", "WARNING", "MIXED"):
        return "status-warn"
    return "status-skip"


def _fmt_num(value: Any, decimals: int = 6) -> str:
    """Format a numeric value for display."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return _esc(value)


def _fmt_pct(value: Any) -> str:
    """Format a value as a percentage."""
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return _esc(value)


def _fmt_ms(value: Any) -> str:
    """Format a milliseconds value."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f} ms"
    except (TypeError, ValueError):
        return _esc(value)


# ═══════════════════════════════════════════════════════════════════════════
# CSS (embedded, with CSS variables for theming)
# ═══════════════════════════════════════════════════════════════════════════
_CSS = """\
:root {
  --bg: #ffffff; --bg-alt: #f8f9fa; --bg-card: #ffffff;
  --text: #1a1a2e; --text-muted: #6c757d;
  --border: #dee2e6; --border-light: #e9ecef;
  --primary: #2563eb; --primary-light: #dbeafe;
  --pass: #16a34a; --pass-bg: #dcfce7;
  --fail: #dc2626; --fail-bg: #fee2e2;
  --warn: #d97706; --warn-bg: #fef3c7;
  --skip: #6b7280; --skip-bg: #f3f4f6;
  --radius: 8px; --shadow: 0 1px 3px rgba(0,0,0,.1);
  --font: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
[data-theme="dark"] {
  --bg: #0f172a; --bg-alt: #1e293b; --bg-card: #1e293b;
  --text: #e2e8f0; --text-muted: #94a3b8;
  --border: #334155; --border-light: #475569;
  --primary: #3b82f6; --primary-light: #1e3a5f;
  --pass: #4ade80; --pass-bg: #064e3b;
  --fail: #f87171; --fail-bg: #450a0a;
  --warn: #fbbf24; --warn-bg: #451a03;
  --skip: #9ca3af; --skip-bg: #1f2937;
}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.6}
.container{max-width:1200px;margin:0 auto;padding:1rem 1.5rem}
header{background:var(--primary);color:#fff;padding:1.25rem 0}
header .container{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem}
header h1{margin:0;font-size:1.5rem;font-weight:700}
.badge{display:inline-block;padding:.25rem .75rem;border-radius:9999px;font-weight:700;font-size:.85rem;text-transform:uppercase}
.badge-pass{background:var(--pass-bg);color:var(--pass)}
.badge-fail{background:var(--fail-bg);color:var(--fail)}
.badge-warn{background:var(--warn-bg);color:var(--warn)}
.badge-skip{background:var(--skip-bg);color:var(--skip)}
.meta{font-size:.8rem;opacity:.85}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1rem;margin:1.5rem 0}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;box-shadow:var(--shadow)}
.card h3{margin:0 0 .25rem;font-size:.85rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em}
.card .big-num{font-size:2rem;font-weight:800;line-height:1.1}
.status-pass{color:var(--pass)} .status-fail{color:var(--fail)}
.status-warn{color:var(--warn)} .status-skip{color:var(--skip)}
table{width:100%;border-collapse:collapse;margin:.75rem 0;font-size:.875rem}
th,td{padding:.5rem .75rem;text-align:left;border-bottom:1px solid var(--border-light)}
th{background:var(--bg-alt);font-weight:600;position:sticky;top:0;cursor:pointer;user-select:none}
tr:nth-child(even){background:var(--bg-alt)}
tr:hover{background:var(--primary-light)}
details{margin:.75rem 0;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
summary{padding:.75rem 1rem;background:var(--bg-alt);cursor:pointer;font-weight:600;user-select:none}
summary:hover{background:var(--border-light)}
details[open] summary{border-bottom:1px solid var(--border)}
details .inner{padding:1rem}
.bar-chart{display:flex;flex-direction:column;gap:.35rem;margin:.5rem 0}
.bar-row{display:flex;align-items:center;gap:.5rem;font-size:.8rem}
.bar-label{min-width:100px;text-align:right}
.bar-track{flex:1;background:var(--bg-alt);border-radius:4px;height:18px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;transition:width .3s}
.bar-value{min-width:60px;font-weight:600;font-size:.75rem}
section{margin:2rem 0}
section h2{font-size:1.25rem;border-bottom:2px solid var(--primary);padding-bottom:.3rem;margin-bottom:1rem}
.theme-toggle{background:transparent;border:1px solid rgba(255,255,255,.4);color:#fff;
  padding:.3rem .7rem;border-radius:var(--radius);cursor:pointer;font-size:.8rem}
.theme-toggle:hover{background:rgba(255,255,255,.15)}
footer{text-align:center;padding:1.5rem;color:var(--text-muted);font-size:.75rem;border-top:1px solid var(--border);margin-top:2rem}
.severity-critical{color:var(--fail);font-weight:700}
.severity-high{color:var(--fail)}
.severity-medium{color:var(--warn)}
.severity-low{color:var(--skip)}
.severity-info{color:var(--text-muted)}
pre{background:var(--bg-alt);padding:.75rem;border-radius:var(--radius);overflow-x:auto;font-size:.8rem;white-space:pre-wrap}
"""

# ═══════════════════════════════════════════════════════════════════════════
# JS (minimal, inline)
# ═══════════════════════════════════════════════════════════════════════════
_JS = """\
(function(){
  // Theme toggle
  const btn=document.getElementById('themeToggle');
  if(btn) btn.addEventListener('click',()=>{
    const d=document.documentElement;
    d.setAttribute('data-theme',d.getAttribute('data-theme')==='dark'?'light':'dark');
    btn.textContent=d.getAttribute('data-theme')==='dark'?'☀ Light':'☾ Dark';
  });
  // Table sorting
  document.querySelectorAll('th[data-sort]').forEach(th=>{
    th.addEventListener('click',()=>{
      const table=th.closest('table'), idx=[...th.parentNode.children].indexOf(th);
      const tbody=table.querySelector('tbody')||table;
      const rows=[...tbody.querySelectorAll('tr')].filter(r=>!r.querySelector('th'));
      const asc=th.dataset.asc!=='1'; th.dataset.asc=asc?'1':'0';
      rows.sort((a,b)=>{
        let va=a.children[idx]?.textContent.trim()??'',vb=b.children[idx]?.textContent.trim()??'';
        const na=parseFloat(va),nb=parseFloat(vb);
        if(!isNaN(na)&&!isNaN(nb)) return asc?na-nb:nb-na;
        return asc?va.localeCompare(vb):vb.localeCompare(va);
      });
      rows.forEach(r=>tbody.appendChild(r));
    });
  });
})();
"""


# ═══════════════════════════════════════════════════════════════════════════
# Section renderers
# ═══════════════════════════════════════════════════════════════════════════

def _render_header(data: dict) -> str:
    """Render the report header with overall status and metadata."""
    meta = data.get("metadata", {})
    status = data.get("overall_status", "UNKNOWN")
    badge_cls = {
        "PASS": "badge-pass", "FAIL": "badge-fail",
        "MIXED": "badge-warn",
    }.get(status, "badge-skip")
    run_id = _esc(meta.get("run_id", "—"))
    ts = _esc(meta.get("timestamp_utc", "—"))
    git = _esc(meta.get("git_commit", "—")[:12]) if meta.get("git_commit") else "—"
    return f"""<header>
  <div class="container">
    <div>
      <h1>🎬 MovSug — Test &amp; Evaluation Report</h1>
      <div class="meta">Run: {run_id} &nbsp;|&nbsp; {ts} &nbsp;|&nbsp; Commit: {git}</div>
    </div>
    <div>
      <span class="badge {badge_cls}">{_esc(status)}</span>
      <button id="themeToggle" class="theme-toggle">☾ Dark</button>
    </div>
  </div>
</header>"""


def _render_summary_cards(data: dict) -> str:
    """Render summary cards: pass rate, backend, frontend, rec, security."""
    summary = data.get("summary", {})
    functional = summary.get("functional", {})
    total = functional.get("total", 0)
    passed = functional.get("passed", 0)
    failed = functional.get("failed", 0)
    skipped = functional.get("skipped", 0)
    rate = (passed / total * 100) if total > 0 else 0

    rec = summary.get("recommendations", {})
    rec_status = rec.get("status", "—")
    sec = summary.get("security", {})
    sec_findings = sec.get("total_findings", 0)

    rate_cls = "status-pass" if rate >= 95 else ("status-warn" if rate >= 80 else "status-fail")
    sec_cls = "status-pass" if sec_findings == 0 else (
        "status-fail" if sec.get("critical", 0) + sec.get("high", 0) > 0 else "status-warn"
    )

    return f"""<section>
  <div class="cards">
    <div class="card">
      <h3>Test Pass Rate</h3>
      <div class="big-num {rate_cls}">{rate:.1f}%</div>
      <div style="font-size:.8rem;color:var(--text-muted)">{passed}/{total} passed</div>
    </div>
    <div class="card">
      <h3>Backend Tests</h3>
      <div class="big-num">{_esc(str(summary.get("backend_tests", {}).get("total", "—")))}</div>
      <div style="font-size:.8rem;color:var(--text-muted)">
        ✓ {summary.get("backend_tests", {}).get("passed", 0)} &nbsp;
        ✗ {summary.get("backend_tests", {}).get("failed", 0)} &nbsp;
        ⊘ {summary.get("backend_tests", {}).get("skipped", 0)}
      </div>
    </div>
    <div class="card">
      <h3>Frontend Tests</h3>
      <div class="big-num">{_esc(str(summary.get("frontend_tests", {}).get("total", "—")))}</div>
      <div style="font-size:.8rem;color:var(--text-muted)">
        ✓ {summary.get("frontend_tests", {}).get("passed", 0)} &nbsp;
        ✗ {summary.get("frontend_tests", {}).get("failed", 0)}
      </div>
    </div>
    <div class="card">
      <h3>Rec. Experiments</h3>
      <div class="big-num {_status_class(rec_status)}">{_esc(rec_status)}</div>
      <div style="font-size:.8rem;color:var(--text-muted)">{rec.get("algorithm", "—")}</div>
    </div>
    <div class="card">
      <h3>Security Findings</h3>
      <div class="big-num {sec_cls}">{sec_findings}</div>
      <div style="font-size:.8rem;color:var(--text-muted)">
        {sec.get("critical", 0)} critical · {sec.get("high", 0)} high
      </div>
    </div>
  </div>
</section>"""


def _render_functional_tests(data: dict) -> str:
    """Render the functional test results table."""
    tests = data.get("functional_tests", [])
    if not tests:
        return ""
    failures = [t for t in tests if t.get("status", "").upper() in ("FAIL", "FAILED", "ERROR")]
    rows = []
    for t in tests:
        st = t.get("status", "UNKNOWN").upper()
        cls = _status_class(st)
        dur = _fmt_ms(t.get("duration_ms")) if t.get("duration_ms") is not None else _fmt_ms(
            t.get("duration", 0) * 1000 if t.get("duration") is not None else None
        )
        rows.append(f'<tr><td>{_esc(t.get("name", "—"))}</td>'
                     f'<td>{_esc(t.get("classname", "—"))}</td>'
                     f'<td class="{cls}">{_esc(st)}</td>'
                     f'<td>{dur}</td></tr>')

    failure_section = ""
    if failures:
        fail_rows = []
        for t in failures:
            msg = t.get("failure_message", t.get("message", ""))
            fail_rows.append(
                f'<details><summary>{_esc(t.get("name", "—"))}</summary>'
                f'<div class="inner"><pre>{_esc(msg)}</pre></div></details>'
            )
        failure_section = f"""
  <details>
    <summary>⚠ {len(failures)} Failure(s) — click to expand</summary>
    <div class="inner">{"".join(fail_rows)}</div>
  </details>"""

    return f"""<section>
  <h2>Functional Test Results</h2>
  <table>
    <thead><tr>
      <th data-sort>Test Name</th><th data-sort>Class</th>
      <th data-sort>Status</th><th data-sort>Duration</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  {failure_section}
</section>"""


def _render_rec_metrics(data: dict) -> str:
    """Render recommendation metrics tables (by-K and latency)."""
    rec = data.get("recommendation_metrics", {})
    if not rec:
        return ""

    by_k = rec.get("by_k", {})
    latency = rec.get("latency", {})

    # Build by-K table
    k_html = ""
    if by_k:
        # Gather all metric names from first K entry
        first_k = next(iter(by_k.values()), {})
        metric_names = [m for m in first_k if m not in ("k",)]
        k_headers = "".join(f"<th data-sort>{_esc(m)}</th>" for m in metric_names)
        k_rows = []
        for k_label, metrics in sorted(by_k.items()):
            cells = "".join(f"<td>{_fmt_num(metrics.get(m), 6)}</td>" for m in metric_names)
            k_rows.append(f"<tr><td><strong>{_esc(k_label)}</strong></td>{cells}</tr>")
        k_html = f"""
  <details open>
    <summary>Recommendation Metrics by K</summary>
    <div class="inner" style="overflow-x:auto">
      <table>
        <thead><tr><th data-sort>K</th>{k_headers}</tr></thead>
        <tbody>{"".join(k_rows)}</tbody>
      </table>
    </div>
  </details>"""

    # Latency table
    lat_html = ""
    if latency:
        lat_rows = "".join(
            f"<tr><td>{_esc(k)}</td><td>{_fmt_ms(v)}</td></tr>"
            for k, v in latency.items()
        )
        lat_html = f"""
  <details open>
    <summary>Latency</summary>
    <div class="inner">
      <table>
        <thead><tr><th data-sort>Percentile</th><th data-sort>Value</th></tr></thead>
        <tbody>{lat_rows}</tbody>
      </table>
    </div>
  </details>"""

    return f"""<section>
  <h2>Recommendation Experiment Metrics</h2>
  {k_html}
  {lat_html}
</section>"""


def _render_mmr_tradeoff(data: dict) -> str:
    """Render the MMR relevance-diversity trade-off table if data exists."""
    mmr = data.get("mmr_tradeoff", data.get("mmr_data", {}))
    if not mmr:
        return ""

    variants = mmr.get("variants", {})
    if not variants:
        return ""

    rows = []
    bar_rows = []
    for vid, vdata in variants.items():
        name = _esc(vdata.get("name", vid))
        metrics = vdata.get("metrics", {})
        by_k = metrics.get("by_k", {})
        lat = metrics.get("latency", {})
        k10 = by_k.get("k_10", {})
        ndcg = k10.get("ndcg", "—")
        ild = k10.get("intra_list_diversity", "—")
        cov = k10.get("catalog_coverage", "—")
        p50 = lat.get("p50_ms", "—")
        rows.append(
            f"<tr><td>{name}</td>"
            f"<td>{_fmt_num(ndcg)}</td>"
            f"<td>{_fmt_num(ild, 4)}</td>"
            f"<td>{_fmt_num(cov, 4)}</td>"
            f"<td>{_fmt_ms(p50)}</td></tr>"
        )
        # Bar chart data for ILD
        try:
            ild_pct = float(ild) * 100
            bar_rows.append(
                f'<div class="bar-row">'
                f'<span class="bar-label">{name}</span>'
                f'<div class="bar-track">'
                f'<div class="bar-fill" style="width:{ild_pct:.1f}%;background:var(--primary)"></div>'
                f'</div>'
                f'<span class="bar-value">{ild_pct:.1f}%</span>'
                f'</div>'
            )
        except (TypeError, ValueError):
            pass

    chart_html = ""
    if bar_rows:
        chart_html = f"""
  <details>
    <summary>Diversity Bar Chart (ILD @K=10)</summary>
    <div class="inner"><div class="bar-chart">{"".join(bar_rows)}</div></div>
  </details>"""

    return f"""<section>
  <h2>MMR Relevance–Diversity Trade-off</h2>
  <table>
    <thead><tr>
      <th data-sort>Variant</th><th data-sort>NDCG@10</th>
      <th data-sort>ILD@10</th><th data-sort>Coverage@10</th><th data-sort>P50 Latency</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  {chart_html}
</section>"""


def _render_latency_comparison(data: dict) -> str:
    """Render latency comparison table across experiments."""
    latency = data.get("latency_comparison", [])
    if not latency:
        return ""
    rows = []
    bar_rows = []
    max_lat = max((e.get("mean_ms", 0) or 0) for e in latency) or 1
    for entry in latency:
        name = _esc(entry.get("name", "—"))
        mean = entry.get("mean_ms", 0) or 0
        rows.append(
            f"<tr><td>{name}</td>"
            f"<td>{_fmt_ms(entry.get('p50_ms'))}</td>"
            f"<td>{_fmt_ms(entry.get('p90_ms'))}</td>"
            f"<td>{_fmt_ms(entry.get('p95_ms'))}</td>"
            f"<td>{_fmt_ms(mean)}</td></tr>"
        )
        pct = (mean / max_lat * 100) if max_lat else 0
        bar_rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{name}</span>'
            f'<div class="bar-track">'
            f'<div class="bar-fill" style="width:{pct:.1f}%;background:var(--warn)"></div>'
            f'</div>'
            f'<span class="bar-value">{_fmt_ms(mean)}</span>'
            f'</div>'
        )
    return f"""<section>
  <h2>Latency Comparison</h2>
  <table>
    <thead><tr>
      <th data-sort>Experiment</th><th data-sort>P50</th>
      <th data-sort>P90</th><th data-sort>P95</th><th data-sort>Mean</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  <details>
    <summary>Latency Bar Chart (Mean)</summary>
    <div class="inner"><div class="bar-chart">{"".join(bar_rows)}</div></div>
  </details>
</section>"""


def _render_security(data: dict) -> str:
    """Render security findings section."""
    findings = data.get("security_findings", [])
    if not findings:
        return ""
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    findings = sorted(findings, key=lambda f: sev_order.get(f.get("severity", "INFO").upper(), 5))
    rows = []
    for f in findings:
        sev = f.get("severity", "INFO").upper()
        rows.append(
            f'<tr><td class="severity-{sev.lower()}">{_esc(sev)}</td>'
            f'<td>{_esc(f.get("title", "—"))}</td>'
            f'<td>{_esc(f.get("location", "—"))}</td>'
            f'<td>{_esc(f.get("description", "—"))}</td></tr>'
        )
    return f"""<section>
  <h2>Security Findings</h2>
  <table>
    <thead><tr>
      <th data-sort>Severity</th><th data-sort>Title</th>
      <th data-sort>Location</th><th>Description</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>"""


def _render_history(data: dict) -> str:
    """Render historical run data if available."""
    history = data.get("history", data.get("historical_records", []))
    if not history:
        return ""
    rows = []
    for rec in history:
        st = rec.get("validation_status", "—")
        cls = _status_class(st)
        rows.append(
            f'<tr><td>{_esc(rec.get("phase", "—"))}</td>'
            f'<td>{_esc(rec.get("experiment_id", "—"))}</td>'
            f'<td>{_esc(rec.get("algorithm_name", "—"))}</td>'
            f'<td class="{cls}">{_esc(st)}</td>'
            f'<td>{_esc(rec.get("evidence_type", "—"))}</td>'
            f'<td>{_esc(rec.get("timestamp_utc", "—")[:10] if rec.get("timestamp_utc") else "—")}</td></tr>'
        )
    return f"""<section>
  <h2>Run History</h2>
  <details open>
    <summary>{len(history)} historical record(s)</summary>
    <div class="inner" style="overflow-x:auto">
      <table>
        <thead><tr>
          <th data-sort>Phase</th><th data-sort>Experiment</th>
          <th data-sort>Algorithm</th><th data-sort>Status</th>
          <th data-sort>Evidence</th><th data-sort>Date</th>
        </tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>
  </details>
</section>"""


def _render_limitations(data: dict) -> str:
    """Render known limitations section."""
    limitations = data.get("known_limitations", [])
    if not limitations:
        return ""
    items = "".join(f"<li>{_esc(lim)}</li>" for lim in limitations)
    return f"""<section>
  <h2>Known Limitations</h2>
  <ul>{items}</ul>
</section>"""


def _render_footer() -> str:
    """Render the footer with generation timestamp."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<footer>
  <p>Generated by MovSug Test &amp; Evaluation Center &nbsp;|&nbsp; {now}</p>
  <p style="font-size:.65rem">This is a self-contained report. No external resources required.</p>
</footer>"""


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def generate_html_report(report_data: dict, output_path: Path) -> Path:
    """Generate a self-contained HTML report with embedded CSS and JS.

    Args:
        report_data: The dict from ``ConsolidatedReport.to_dict()``.
        output_path: Destination path for the HTML file.

    Returns:
        The resolved output path that was written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sections = [
        _render_header(report_data),
        '<main class="container">',
        _render_summary_cards(report_data),
        _render_functional_tests(report_data),
        _render_rec_metrics(report_data),
        _render_mmr_tradeoff(report_data),
        _render_latency_comparison(report_data),
        _render_security(report_data),
        _render_history(report_data),
        _render_limitations(report_data),
        "</main>",
        _render_footer(),
    ]

    body = "\n".join(s for s in sections if s)

    html_doc = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>MovSug — Test &amp; Evaluation Report</title>
  <style>{_CSS}</style>
</head>
<body>
{body}
<script>{_JS}</script>
</body>
</html>"""

    output_path.write_text(html_doc, encoding="utf-8")
    logger.info("HTML report written to %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path
