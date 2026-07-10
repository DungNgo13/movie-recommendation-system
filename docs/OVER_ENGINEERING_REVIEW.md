# Over-Engineering Review — Mov-Sug Movie Recommendation System

**Audit Date:** 2026-07-10  
**Scope:** Identification of features that may be over-engineered relative to the project's goal as an academic graduation/demo project with AI recommendation as the central feature.

---

## 1. Review Criteria

Per the user's requirements:
- **The AI recommendation feature must remain central**
- **Features that distract from AI recommendation should be reduced, hidden, or moved to future work**
- **A graduation/demo project should be impressive but explainable**
- **Do not over-engineer**

Each module is classified as:
- ✅ **Core** — Essential to the project's identity and demo value
- ✅ **Good Supporting** — Adds genuine value without excessive complexity
- ⚠️ **Over-Engineered** — More complex than needed for academic scope
- ❌ **Remove/Simplify** — Should be cut or drastically simplified

---

## 2. Module-by-Module Assessment

### ✅ Core: Recommendation Engine (6 files, ~800 lines)

| File | Lines | Verdict | Notes |
|------|-------|---------|-------|
| `engine.py` | ~100 | ✅ Essential | Orchestrator — clean, well-structured |
| `movie_profile.py` | ~50 | ✅ Essential | Movie text builder — simple and correct |
| `user_profile.py` | ~120 | ✅ Essential | Multi-signal profiling — appropriate complexity |
| `vectorizer.py` | ~100 | ✅ Essential | TF-IDF + caching — necessary optimization |
| `explainer.py` | ~50 | ✅ Essential | User-facing reasons — core UX |
| `explainer_admin.py` | ~230 | ✅ Essential | **Thesis defense tool** — most impressive feature |

**Verdict:** Perfectly scoped. Every line serves the core goal.

---

### ✅ Good Supporting: Admin Recommendation Explainer

| Component | Verdict | Notes |
|-----------|---------|-------|
| `admin_recommendations.py` router | ✅ | Clean API endpoint |
| `RecsysMonitorPage.tsx` (~520 lines) | ✅ | Rich diagnostic UI — excellent for thesis demo |
| `recsysService.ts` | ✅ | Clean frontend service |
| Type definitions for explain payload | ✅ | Well-typed, matches backend |

**Verdict:** This is the project's showpiece feature. Keep it prominent.

---

### ✅ Good Supporting: HLS Video Streaming (1 file, ~563 lines)

| Component | Verdict | Notes |
|-----------|---------|-------|
| `hls_service.py` | ✅ | Multi-quality encoding with fallback |
| Encoding queue (asyncio.Queue) | ✅ | Demonstrates async systems knowledge |
| Process cancellation | ✅ | Practical feature, well-implemented |
| Progress tracking via ffmpeg stderr | ✅ | Impressive engineering |
| `HlsPlayer.tsx` component | ✅ | Functional video player with hls.js |

**Verdict:** Appropriate for a movie streaming platform. Demonstrates real systems engineering. The encoding queue is elegant and explainable.

---

### ✅ Good Supporting: Authentication System

| Component | Verdict | Notes |
|-----------|---------|-------|
| JWT auth with bcrypt | ✅ | Standard, appropriate |
| Login tracking + brute-force detection | ✅ | Demonstrates security awareness |
| Password reset via email | ✅ | Real-world feature, well-implemented |
| Sliding session (token refresh) | ✅ | Good UX practice |
| Password complexity validator | ✅ | Centralized, testable |

**Verdict:** Appropriate. Each auth feature serves a clear purpose and demonstrates competence.

---

### ⚠️ Over-Engineered: Source & License Tracking System

| Component | Lines | Issue |
|-----------|-------|-------|
| `Movie.source_name`, `source_url`, `license_type`, `license_url`, `attribution`, `is_public_domain`, `media_rights_status` | 7 columns | 7 columns on the Movie model for content rights |
| `MovieAsset` model and table | ~100+ lines | Separate table for per-asset licensing |
| `movie_assets.py` router | ~150 lines | Full CRUD for asset management |
| `movie_asset_service.py` | ~65 lines | Service layer for assets |
| `SourceAttribution.tsx` component | ~100 lines | Frontend component for displaying attribution |
| Alembic migration for movie_assets | ~60 lines | Separate migration |

**Total:** ~7 model columns + 1 separate table + ~500 lines of code for a feature that is tangential to the AI recommendation core.

**Root Cause:** This was likely added to handle image/video copyright attribution — a real concern, but the implementation is enterprise-grade.

**Recommendation:**
- For thesis: Reduce to a simple `source_notes` text column on Movie. Mention "content sourced from public domain" in footer.
- Keep `SourceAttribution.tsx` if you have real attribution requirements, but simplify the per-asset system.
- The separate `MovieAsset` table adds no value to the AI recommendation demo.

**Action:** ⚠️ Do NOT remove — but in thesis presentation, de-emphasize this feature. It's "bonus polish" not "core AI capability."

---

### ⚠️ Over-Engineered: Security Audit Page

| Component | Lines | Issue |
|-----------|-------|-------|
| `UserSecurityAuditSchema` | ~15 lines | Full security audit schema |
| `GET /admin/users/security-audit` | ~12 lines | Endpoint returning all user security data |
| Related frontend components | ~100+ lines | Security audit dashboard |

**Root Cause:** Demonstrates security awareness, which is good. But it's not related to AI recommendation.

**Recommendation:** Keep in codebase but de-emphasize in thesis. Mention it as "additional security features" in one sentence, don't dedicate a section.

---

### ⚠️ Over-Engineered: 5 Data Import Scripts

| Script | Purpose | Assessment |
|--------|---------|------------|
| `import_movielens.py` | Import from MovieLens dataset | ✅ Useful — primary data source |
| `import_public_domain.py` | Import public domain movies | ⚠️ Overlaps with MovieLens |
| `import_tmdb_posters.py` | Fetch TMDB poster images | ✅ Useful for visual quality |
| `seed.py` | Seed initial movies | ✅ Essential for dev setup |
| `migrate_sqlite_to_pg.py` | SQLite → PostgreSQL migration | ✅ Useful for deployment |

**Root Cause:** Each script was created for a specific use case, but having 5 import scripts creates the impression of a data management platform rather than a focused AI demo.

**Recommendation:** Keep `seed.py` and `import_movielens.py`. The rest can stay in the repo but should be documented as "deployment utilities" not "features."

---

### ⚠️ Over-Engineered: Email-Confirmed Password Change

| Component | Complexity | Simpler Alternative |
|-----------|-----------|---------------------|
| Step 1: Verify old password, hash new password, create JWT with hash, send email | High — bcrypt hash in JWT body | Step 1: Verify old password, update immediately, send notification email |
| Step 2: User clicks email link, JWT decoded, hash applied | High — two HTTP round-trips | No step 2 needed |

**Root Cause:** The two-step email-confirmed flow is a legitimate security pattern used by banks and enterprise apps. For an academic movie recommendation project, it's over-engineered.

**Security Note:** Embedding a bcrypt hash inside a JWT token sent via email is a non-standard practice. The hash is safe (one-way), but it expands the token size and exposes the hash to email infrastructure.

**Recommendation:** Keep as-is — it works and demonstrates security knowledge. But in thesis defense, spend 10 seconds on it max.

---

### ✅ Good Supporting: Guest Watch History / Cold-Start Merge

| Component | Verdict | Notes |
|-----------|---------|-------|
| `localStorage` guest tracking | ✅ | Demonstrates cold-start mitigation |
| `merge_guest_history` on login | ✅ | Smart: converts anonymous behavior into user profile |
| `GuestWatchEntry` schema | ✅ | Well-typed, validated |

**Verdict:** Directly supports the AI recommendation narrative. Guest-to-user data merge is a real recommendation system challenge. **Highlight this in thesis.**

---

### ✅ Good Supporting: Admin Dashboard

| Component | Verdict | Notes |
|-----------|---------|-------|
| User management | ✅ | Basic CRUD, role management |
| Audit log | ✅ | Demonstrates accountability |
| Force password reset | ✅ | Practical admin tool |
| Movie management | ✅ | Content management |
| HLS processing controls | ✅ | Queue management, cancel |

**Verdict:** Standard admin panel. Not over-engineered — these are minimum viable admin features.

---

### ✅ Good Supporting: IP Address Extraction

| Component | Lines | Verdict |
|-----------|-------|---------|
| `_extract_client_ip()` in `auth.py` | ~60 lines | ✅ Well-implemented |
| Private IP detection | ~30 lines | ✅ Proper proxy handling |
| IP regex validation | ~10 lines | ✅ Input sanitization |

**Root Cause:** Needed for login tracking. The implementation is thorough (handles `X-Forwarded-For`, `X-Real-IP`, private IP filtering) without being excessive.

**Verdict:** Good engineering. The comments explain the "why" (Nginx topology) clearly.

---

## 3. Complexity Budget

For an academic project, I recommend a mental "complexity budget" — the amount of complexity a reviewer can absorb. Here's how the current project allocates it:

| Feature Area | Complexity Share | Ideal Share |
|-------------|-----------------|-------------|
| AI Recommendation Engine | 25% | **40%** ← should be higher |
| HLS Video Streaming | 20% | 15% |
| Auth + Security | 20% | 15% |
| Admin Dashboard | 10% | 10% |
| Source/License/Asset System | 10% | **3%** ← too much |
| Data Import Scripts | 5% | 5% |
| Frontend UX | 10% | 12% |

**Key insight:** The recommendation engine should be 40% of the perceived complexity, but source/license tracking and advanced security features dilute it. The engine is well-built but doesn't get enough "screen time."

---

## 4. Recommendations for Thesis Presentation

### Slide Time Allocation (30-minute defense)

| Topic | Minutes | Why |
|-------|---------|-----|
| Problem statement + architecture overview | 3 | Context |
| **AI Recommendation Algorithm (TF-IDF + Cosine Similarity)** | **8** | **Core — explain math, show admin explainer** |
| **Multi-signal user profiling** | **4** | **Core — show weight formulas, time decay** |
| **Cold-start handling + guest merge** | **3** | **Core — real recommendation system challenge** |
| Live demo: user interactions → recommendation changes | 5 | Proof of concept |
| HLS streaming + encoding architecture | 3 | Supporting technical achievement |
| Auth + security design | 2 | Briefly demonstrate competence |
| Limitations + future work | 2 | Academic honesty |

### Features to Demo

1. **Must demo:** Admin Recommendation Explainer — show exactly how scores are computed
2. **Must demo:** Two different users getting different recommendations based on their interactions
3. **Must demo:** Cold-start → rate some movies → get personalized recommendations
4. **Should demo:** Video streaming working with quality selection
5. **Optional:** Password reset flow, admin user management

### Features to NOT Demo

1. ❌ Source/License attribution system — distracts from AI
2. ❌ Security audit page — distracts from AI
3. ❌ Data import scripts — implementation detail
4. ❌ Brute-force detection — mention in passing only

---

## 5. "Would an Advisor Flag This?" Test

| Feature | Would advisor flag as over-engineered? | Explainable in 30 seconds? |
|---------|----------------------------------------|--------------------------|
| TF-IDF + Cosine Similarity | No — well-established technique | Yes |
| Multi-signal user profile | No — demonstrates understanding | Yes |
| Time decay on watch history | No — real-world concern | Yes |
| Admin recommendation explainer | No — excellent pedagogical tool | Yes |
| HLS multi-quality encoding queue | Maybe — impressive but complex | Takes 60 seconds |
| Email-confirmed password change | **Yes** — enterprise pattern, unnecessary | No — requires explanation |
| Per-asset license tracking | **Yes** — enterprise feature | No — requires explanation |
| Security audit dashboard | Borderline — nice but tangential | Yes, but "why?" is hard to answer |
| 5 data import scripts | **Yes** — implies data platform scope | No — "why 5?" |
| Guest-to-user history merge | No — directly supports AI recommendation | Yes |

---

## 6. Final Verdict

### Keep Prominent (Core)
- AI Recommendation Engine (all 6 files)
- Admin Recommendation Explainer
- Guest watch history → user profile merge
- Multi-signal user profiling

### Keep But De-Emphasize
- HLS streaming (good supporting feature)
- Auth + JWT + password reset (standard web security)
- Admin dashboard (necessary utility)
- IP tracking + brute-force detection (security awareness demo)

### Keep But Don't Present
- Source/License/Attribution system (don't mention in thesis defense)
- Security audit page (mention once as "additional feature")
- Email-confirmed password change (don't demo this flow)
- Multiple data import scripts (implementation detail)

### Nothing to Remove
The project is well-built and nothing is broken or harmful. The over-engineering is "nice-to-have features" rather than "wrong architecture." No code needs to be deleted — just adjust the thesis presentation to focus on the AI core.

---

*This review was conducted as an advisory opinion. No application code was modified.*
