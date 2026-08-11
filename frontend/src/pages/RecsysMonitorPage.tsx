import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  explainRecommendations,
  type ExplainPayload,
  type SignalEntry,
  type RecommendationEntry,
} from '../services/recsysService';
import { getAdminUsers } from '../services/adminService';
import type { AuthUser } from '../services/authService';
import type { TFunction } from 'i18next';

// ─── Small presentational helpers ────────────────────────────────────────────

/** Colored badge for signal type */
function SignalBadge({ type, t }: { type: SignalEntry['signal_type']; t: TFunction }) {
  const map: Record<string, { labelKey: string; bg: string; color: string }> = {
    rating: { labelKey: 'admin:recsys.signalRating', bg: '#fff3cd', color: '#856404' },
    favorite: { labelKey: 'admin:recsys.signalFavorite', bg: '#fce8f3', color: '#842029' },
    watch: { labelKey: 'admin:recsys.signalWatch', bg: '#d1ecf1', color: '#0c5460' },
  };
  const s = map[type] ?? { labelKey: type, bg: '#eee', color: '#333' };
  const label = map[type] ? t(s.labelKey) : type;
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
      {label}
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

function SignalsTable({ signals, t }: { signals: SignalEntry[]; t: TFunction }) {
  if (!signals.length) {
    return (
      <div className="recsys-empty">
        {t("admin:recsys.noColdStart")}
      </div>
    );
  }
  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th>{t("admin:recsys.movie")}</th>
            <th>{t("admin:recsys.signal")}</th>
            <th>{t("admin:recsys.rawValue")}</th>
            <th>{t("admin:recsys.computedWeight")}</th>
            <th>{t("admin:recsys.breakdownFormula")}</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s, i) => (
            <tr key={i}>
              <td style={{ fontWeight: 500 }}>{s.movie_title}</td>
              <td><SignalBadge type={s.signal_type} t={t} /></td>
              <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                {s.signal_type === 'watch'
                  ? t("admin:recsys.watched", { value: s.raw_value })
                  : s.signal_type === 'rating'
                    ? t("admin:recsys.ratingStars", { value: s.raw_value })
                    : t("admin:recsys.saved")}
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

function ScoringTable({ recs, t }: { recs: RecommendationEntry[]; t: TFunction }) {
  if (!recs.length) {
    return <div className="recsys-empty">{t("admin:recsys.noRecommendations")}</div>;
  }
  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th style={{ width: 48 }}>{t("admin:recsys.rank")}</th>
            <th>{t("admin:recsys.movie")}</th>
            <th>{t("admin:recsys.genres")}</th>
            <th>{t("admin:recsys.director")}</th>
            <th>{t("admin:recsys.totalScore")}</th>
            <th>{t("admin:recsys.interpretation")}</th>
            <th>{t("admin:recsys.matchReasons")}</th>
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
  const { t } = useTranslation(['admin', 'common']);

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
          <span className="admin-badge">{t("admin:recsys.thesisTool")}</span>
          <h1 style={{ margin: 0 }}>{t("admin:recsys.title")}</h1>
          <p style={{ margin: '6px 0 0', color: '#888', fontSize: '0.9rem' }}>
            {t("admin:recsys.description")}
          </p>
        </div>
      </div>

      {/* ── User Selector Card ───────────────────────────────────────────── */}
      <div className="recsys-selector-card">
        <h2 className="recsys-section-title">{t("admin:recsys.selectUser")}</h2>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>

          {/* Dropdown selector loaded from /admin/users */}
          <div style={{ flex: 2, minWidth: 260 }}>
            <label className="recsys-label">{t("admin:recsys.chooseUser")}</label>
            <select
              className="filter-select"
              style={{ width: '100%' }}
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              onFocus={loadUsers}
            >
              <option value="">{t("admin:recsys.selectPlaceholder")}</option>
              {usersLoading && <option disabled>{t("admin:recsys.loading")}</option>}
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}  ({u.role}) — {u.id.substring(0, 8)}…
                </option>
              ))}
            </select>
          </div>

          {/* Or paste UUID directly */}
          <div style={{ flex: 2, minWidth: 240 }}>
            <label className="recsys-label">{t("admin:recsys.pasteUserId")}</label>
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
              {t("admin:recsys.topN")} <strong>{topN}</strong>
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
            {loading ? t("admin:recsys.running") : t("admin:recsys.explain")}
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
                <strong>{t("admin:recsys.userLabel")}</strong> {payload.user_email}
              </span>
              <span>
                <strong>{t("admin:recsys.engineLabel")}</strong> {payload.algorithm_version}
              </span>
              <span>
                <strong>{t("admin:recsys.coldStart")}</strong>{' '}
                <span style={{ color: payload.is_cold_start ? '#e74c3c' : '#27ae60', fontWeight: 600 }}>
                  {payload.is_cold_start ? t("admin:recsys.yes") : t("admin:recsys.no")}
                </span>
              </span>
              {payload.weight_summary && (
                <>
                  <span>
                    <strong>{t("admin:recsys.totalSignals")}</strong> {payload.weight_summary.total_signals}
                  </span>
                  <span>
                    <strong>{t("admin:recsys.moviesInProfile")}</strong>{' '}
                    {payload.weight_summary.unique_movies_in_profile}
                  </span>
                </>
              )}
            </div>
            {payload.algorithm_summary && (
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#cde', lineHeight: 1.6 }}>
                <strong>{t("admin:recsys.pipeline")}</strong> {payload.algorithm_summary}
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
              {t("admin:recsys.section1Title")}
              <span className="recsys-section-subtitle">
                {t("admin:recsys.section1Desc")}
              </span>
            </h2>

            {/* Legend */}
            <div className="recsys-legend">
              <span>{t("admin:recsys.weightScale")}</span>
              {[
                { label: t("admin:recsys.legendLoved"), color: '#27ae60' },
                { label: t("admin:recsys.legendLiked"), color: '#f39c12' },
                { label: t("admin:recsys.legendWatched"), color: '#95a5a6' },
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

            <SignalsTable signals={payload.user_context} t={t} />
          </div>

          {/* ── Section 2: Scoring Breakdown ──────────────────────────── */}
          <div className="recsys-section">
            <h2 className="recsys-section-title">
              {t("admin:recsys.section2Title")}
              <span className="recsys-section-subtitle">
                {t("admin:recsys.section2Desc", { count: payload.top_recommendations.length })}
              </span>
            </h2>

            {/* Score legend */}
            <div className="recsys-legend">
              {[
                { label: t("admin:recsys.legendVeryStrong"), color: '#27ae60' },
                { label: t("admin:recsys.legendGoodStrong"), color: '#f39c12' },
                { label: t("admin:recsys.legendWeak"), color: '#95a5a6' },
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

            <ScoringTable recs={payload.top_recommendations} t={t} />
          </div>
        </>
      )}
    </div>
  );
};

export default RecsysMonitorPage;
