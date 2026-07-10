import React, { useState } from 'react';
import {
  explainRecommendations,
  type ExplainPayload,
  type SignalEntry,
  type RecommendationEntry,
} from '../services/recsysService';
import { getAdminUsers } from '../services/adminService';
import type { AuthUser } from '../services/authService';

// ─── Small presentational helpers ────────────────────────────────────────────

/** Colored badge for signal type */
function SignalBadge({ type }: { type: SignalEntry['signal_type'] }) {
  const map: Record<string, { label: string; bg: string; color: string }> = {
    rating: { label: 'Rating', bg: '#fff3cd', color: '#856404' },
    favorite: { label: 'Favorite', bg: '#fce8f3', color: '#842029' },
    watch: { label: 'Watch', bg: '#d1ecf1', color: '#0c5460' },
  };
  const s = map[type] ?? { label: type, bg: '#eee', color: '#333' };
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 10px',
      borderRadius: 12,
      fontSize: '0.75rem',
      fontWeight: 600,
      background: s.bg,
      color: s.color,
      whiteSpace: 'nowrap',
    }}>
      {s.label}
    </span>
  );
}

/** Horizontal progress bar — value 0-5 scale (max weight = 5) */
function WeightBar({ value }: { value: number }) {
  const pct = Math.min(100, (value / 5) * 100);
  const color =
    value >= 4 ? '#27ae60' :   // high — green
      value >= 2.5 ? '#f39c12' :   // mid  — amber
        '#95a5a6';    // low  — grey
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        flex: 1,
        height: 8,
        borderRadius: 4,
        background: '#e9ecef',
        overflow: 'hidden',
        minWidth: 80,
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          borderRadius: 4,
          background: color,
          transition: 'width 0.4s ease',
        }} />
      </div>
      <span style={{ fontSize: '0.8rem', fontWeight: 600, color, minWidth: 28 }}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}

/** Score badge — green / yellow / grey */
function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.5 ? '#27ae60' :
      score >= 0.15 ? '#f39c12' :
        '#95a5a6';
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: 12,
      fontSize: '0.78rem',
      fontWeight: 700,
      background: color,
      color: '#fff',
    }}>
      {pct}%
    </span>
  );
}

/** Pill badge list for genres/keywords */
function PillList({ items, color = '#3498db' }: { items: string[]; color?: string }) {
  if (!items.length) return <span style={{ color: '#bbb', fontSize: '0.8rem' }}>—</span>;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {items.map((item) => (
        <span key={item} style={{
          display: 'inline-block',
          padding: '1px 8px',
          borderRadius: 10,
          fontSize: '0.72rem',
          background: `${color}22`,
          color,
          fontWeight: 500,
          border: `1px solid ${color}44`,
        }}>
          {item}
        </span>
      ))}
    </div>
  );
}

// ─── Section 1: User Profile Signals table ───────────────────────────────────

function SignalsTable({ signals }: { signals: SignalEntry[] }) {
  if (!signals.length) {
    return (
      <div className="recsys-empty">
        No interactions recorded — this user is in cold-start mode.
      </div>
    );
  }
  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th>Movie</th>
            <th>Signal</th>
            <th>Raw Value</th>
            <th>Computed Weight  (0 – 5)</th>
            <th>Breakdown Formula</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s, i) => (
            <tr key={i}>
              <td style={{ fontWeight: 500 }}>{s.movie_title}</td>
              <td><SignalBadge type={s.signal_type} /></td>
              <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                {s.signal_type === 'watch'
                  ? `${s.raw_value}% watched`
                  : s.signal_type === 'rating'
                    ? `${s.raw_value} / 5 stars`
                    : 'Saved'}
              </td>
              <td style={{ minWidth: 160 }}>
                <WeightBar value={s.calculated_weight} />
              </td>
              <td style={{ fontSize: '0.8rem', color: '#555', maxWidth: 280 }}>
                {s.weight_breakdown}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Section 2: Scoring Breakdown table ──────────────────────────────────────

function ScoringTable({ recs }: { recs: RecommendationEntry[] }) {
  if (!recs.length) {
    return <div className="recsys-empty">No recommendations generated.</div>;
  }
  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th style={{ width: 48 }}>Rank</th>
            <th>Movie</th>
            <th>Genres</th>
            <th>Director</th>
            <th>Total Score</th>
            <th>Interpretation</th>
            <th>Match Reasons</th>
          </tr>
        </thead>
        <tbody>
          {recs.map((r) => (
            <tr key={r.rank}>
              {/* Rank */}
              <td style={{ textAlign: 'center' }}>
                <span style={{
                  display: 'inline-block',
                  width: 28,
                  height: 28,
                  lineHeight: '28px',
                  borderRadius: '50%',
                  background: r.rank === 1 ? '#f1c40f' : r.rank <= 3 ? '#bdc3c7' : '#ecf0f1',
                  color: r.rank <= 3 ? '#333' : '#666',
                  fontWeight: 700,
                  fontSize: '0.82rem',
                  textAlign: 'center',
                }}>
                  {r.rank}
                </span>
              </td>

              {/* Title + year */}
              <td>
                <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{r.movie_title}</div>
                {r.release_year && (
                  <div style={{ fontSize: '0.75rem', color: '#999' }}>{r.release_year}</div>
                )}
              </td>

              {/* Genres */}
              <td><PillList items={r.genres} color="#3498db" /></td>

              {/* Director */}
              <td style={{ fontSize: '0.85rem', color: '#444' }}>
                {r.director ?? <span style={{ color: '#bbb' }}>—</span>}
              </td>

              {/* Score */}
              <td>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <ScoreBadge score={r.total_score} />
                  <div style={{
                    height: 6,
                    borderRadius: 3,
                    background: '#e9ecef',
                    overflow: 'hidden',
                    width: 80,
                  }}>
                    <div style={{
                      height: '100%',
                      width: `${Math.round(r.total_score * 100)}%`,
                      borderRadius: 3,
                      background:
                        r.total_score >= 0.5 ? '#27ae60' :
                          r.total_score >= 0.15 ? '#f39c12' : '#95a5a6',
                    }} />
                  </div>
                  <span style={{ fontSize: '0.7rem', color: '#888', fontFamily: 'monospace' }}>
                    {r.total_score.toFixed(4)}
                  </span>
                </div>
              </td>

              {/* Interpretation */}
              <td>
                <span style={{
                  fontSize: '0.78rem',
                  fontWeight: 500,
                  color:
                    r.score_interpretation === 'Very strong match' ? '#27ae60' :
                      r.score_interpretation === 'Strong match' ? '#2980b9' :
                        r.score_interpretation === 'Good match' ? '#f39c12' :
                          '#95a5a6',
                }}>
                  {r.score_interpretation}
                </span>
              </td>

              {/* Contributing factors */}
              <td style={{ maxWidth: 300 }}>
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: '0.78rem', color: '#444' }}>
                  {r.contributing_factors.map((f, i) => (
                    <li key={i} style={{ marginBottom: 2 }}>{f}</li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const RecsysMonitorPage: React.FC = () => {
  // User list for the dropdown selector
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [usersLoaded, setUsersLoaded] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);

  // Selected user + query state
  const [selectedUserId, setSelectedUserId] = useState('');
  const [topN, setTopN] = useState(10);

  // Diagnostic result state
  const [payload, setPayload] = useState<ExplainPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load user list once when the dropdown is first opened
  const loadUsers = async () => {
    if (usersLoaded) return;
    setUsersLoading(true);
    try {
      const data = await getAdminUsers();
      setUsers(data);
      setUsersLoaded(true);
    } catch {
      // Graceful degradation — user can still paste a UUID manually
    } finally {
      setUsersLoading(false);
    }
  };

  const handleExplain = async () => {
    if (!selectedUserId.trim()) return;
    setLoading(true);
    setError(null);
    setPayload(null);
    try {
      const data = await explainRecommendations(selectedUserId.trim(), topN);
      setPayload(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-page">

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="admin-header">
        <div>
          <span className="admin-badge">Thesis Tool</span>
          <h1 style={{ margin: 0 }}>Recommendation System Monitor</h1>
          <p style={{ margin: '6px 0 0', color: '#888', fontSize: '0.9rem' }}>
            Diagnostic explainer — shows exactly how recommendation scores are computed for any user.
          </p>
        </div>
      </div>

      {/* ── User Selector Card ───────────────────────────────────────────── */}
      <div className="recsys-selector-card">
        <h2 className="recsys-section-title">Select User</h2>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>

          {/* Dropdown selector loaded from /admin/users */}
          <div style={{ flex: 2, minWidth: 260 }}>
            <label className="recsys-label">Choose from registered users</label>
            <select
              className="filter-select"
              style={{ width: '100%' }}
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              onFocus={loadUsers}
            >
              <option value="">— select a user —</option>
              {usersLoading && <option disabled>Loading…</option>}
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}  ({u.role}) — {u.id.substring(0, 8)}…
                </option>
              ))}
            </select>
          </div>

          {/* Or paste UUID directly */}
          <div style={{ flex: 2, minWidth: 240 }}>
            <label className="recsys-label">Or paste a User ID (UUID) directly</label>
            <input
              type="text"
              className="search-input"
              style={{ width: '100%' }}
              placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
            />
          </div>

          {/* Top-N slider */}
          <div style={{ minWidth: 160 }}>
            <label className="recsys-label">
              Top N recommendations: <strong>{topN}</strong>
            </label>
            <input
              type="range"
              min={3}
              max={20}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              style={{ width: '100%', accentColor: '#3498db' }}
            />
          </div>

          {/* Run button */}
          <button
            className="btn btn-primary"
            style={{ padding: '10px 24px', fontSize: '0.95rem', alignSelf: 'flex-end' }}
            disabled={!selectedUserId.trim() || loading}
            onClick={handleExplain}
            id="recsys-explain-btn"
          >
            {loading ? 'Running...' : 'Explain'}
          </button>
        </div>

        {error && (
          <div className="error-message" style={{ marginTop: 16 }}>
            {error}
          </div>
        )}
      </div>

      {/* ── Results ─────────────────────────────────────────────────────── */}
      {payload && (
        <>
          {/* Algorithm summary banner */}
          <div className="recsys-algo-banner">
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 8 }}>
              <span>
                <strong>User:</strong> {payload.user_email}
              </span>
              <span>
                <strong>Engine:</strong> {payload.algorithm_version}
              </span>
              <span>
                <strong>Cold start:</strong>{' '}
                <span style={{ color: payload.is_cold_start ? '#e74c3c' : '#27ae60', fontWeight: 600 }}>
                  {payload.is_cold_start ? 'Yes' : 'No'}
                </span>
              </span>
              {payload.weight_summary && (
                <>
                  <span>
                    <strong>Total signals:</strong> {payload.weight_summary.total_signals}
                  </span>
                  <span>
                    <strong>Movies in profile:</strong>{' '}
                    {payload.weight_summary.unique_movies_in_profile}
                  </span>
                </>
              )}
            </div>
            {payload.algorithm_summary && (
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#cde', lineHeight: 1.6 }}>
                <strong>Pipeline:</strong> {payload.algorithm_summary}
              </p>
            )}
            {payload.is_cold_start && payload.cold_start_reason && (
              <p style={{ margin: '8px 0 0', fontSize: '0.85rem', color: '#f1c40f' }}>
                {payload.cold_start_reason}
              </p>
            )}
          </div>

          {/* ── Section 1: User Profile Signals ───────────────────────── */}
          <div className="recsys-section">
            <h2 className="recsys-section-title">
              Section 1 — User Profile Signals
              <span className="recsys-section-subtitle">
                Every interaction that shaped this user's preference vector,
                with computed weights. Higher weight = stronger influence.
              </span>
            </h2>

            {/* Legend */}
            <div className="recsys-legend">
              <span>Weight scale:</span>
              {[
                { label: '5.0 — Loved (5/5)', color: '#27ae60' },
                { label: '3.0 — Liked / Favorite', color: '#f39c12' },
                { label: '1.0+  — Watched (scaled by progress + time decay)', color: '#95a5a6' },
              ].map(({ label, color }) => (
                <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    display: 'inline-block', width: 12, height: 12,
                    borderRadius: '50%', background: color,
                  }} />
                  <span style={{ fontSize: '0.78rem' }}>{label}</span>
                </span>
              ))}
            </div>

            <SignalsTable signals={payload.user_context} />
          </div>

          {/* ── Section 2: Scoring Breakdown ──────────────────────────── */}
          <div className="recsys-section">
            <h2 className="recsys-section-title">
              Section 2 — Scoring Breakdown
              <span className="recsys-section-subtitle">
                Top {payload.top_recommendations.length} movies ranked by cosine similarity
                between the user's weighted preference vector and each movie's TF-IDF vector.
              </span>
            </h2>

            {/* Score legend */}
            <div className="recsys-legend">
              {[
                { label: '≥ 50% — Very strong match', color: '#27ae60' },
                { label: '15–49% — Good / Strong match', color: '#f39c12' },
                { label: '< 15% — Weak match', color: '#95a5a6' },
              ].map(({ label, color }) => (
                <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    display: 'inline-block', width: 12, height: 12,
                    borderRadius: '50%', background: color,
                  }} />
                  <span style={{ fontSize: '0.78rem' }}>{label}</span>
                </span>
              ))}
            </div>

            <ScoringTable recs={payload.top_recommendations} />
          </div>
        </>
      )}
    </div>
  );
};

export default RecsysMonitorPage;
