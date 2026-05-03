/**
 * HlsPlayer — Plyr + hls.js integration
 *
 * RACE CONDITION FIX — isMounted flag pattern:
 *
 * Problem: new Plyr() must be called INSIDE MANIFEST_PARSED (async) because
 * Plyr builds its quality-selector DOM at init time and requires the level
 * heights to be known. But if React's cleanup runs before the callback fires
 * (e.g. parent re-renders), a zombie Plyr instance gets created on an
 * already-unmounted video element — its fullscreen listeners are then orphaned.
 *
 * Solution: `let isMounted = true` is declared in the effect closure.
 * The cleanup sets it to false FIRST, before destroying anything.
 * The MANIFEST_PARSED callback checks the flag before touching the DOM.
 * If the effect has already cleaned up, the callback exits immediately and
 * no second Plyr instance is ever created.
 */
import React, { useEffect, useRef } from 'react';
import Hls from 'hls.js';
import Plyr from 'plyr';
import 'plyr/dist/plyr.css';

interface HlsPlayerProps {
  src: string;
  poster?: string;
  initialTime?: number;
  onTimeUpdate?: (currentTime: number, duration: number) => void;
  onPause?: (currentTime: number, duration: number) => void;
  onEnded?: (duration: number) => void;
}

const HlsPlayer: React.FC<HlsPlayerProps> = ({
  src,
  poster,
  initialTime = 0,
  onTimeUpdate,
  onPause,
  onEnded,
}) => {
  const videoRef  = useRef<HTMLVideoElement>(null);
  const hlsRef    = useRef<Hls | null>(null);
  const playerRef = useRef<Plyr | null>(null);

  // ─────────────────────────────────────────────────────────────────────────
  // Effect 1 — init HLS + Plyr whenever the stream URL changes
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // ── STEP 1: Mounted flag ─────────────────────────────────────────────
    // Declared at the very top of the effect so the async MANIFEST_PARSED
    // callback can check whether this effect is still alive before touching
    // any DOM nodes or creating a Plyr instance.
    let isMounted = true;

    // Tear down any surviving instances from a previous src
    playerRef.current?.destroy();
    playerRef.current = null;
    hlsRef.current?.destroy();
    hlsRef.current = null;

    // ── STEP 2: HLS path ─────────────────────────────────────────────────
    if (Hls.isSupported()) {
      const hls = new Hls({ maxBufferLength: 30, enableWorker: true });
      hlsRef.current = hls;

      hls.loadSource(src);
      hls.attachMedia(video);

      // ── STEP 3: Async callback with isMounted guard ───────────────────
      hls.on(Hls.Events.MANIFEST_PARSED, (_event, data) => {
        // CRITICAL: If cleanup already ran, bail out immediately.
        // This prevents the zombie-Plyr race condition entirely.
        if (!isMounted) return;

        // ── STEP 4: Build quality list, then init Plyr ───────────────────
        // De-duplicate heights and sort descending (e.g. [1080, 720, 480, 360])
        const heights = Array.from(
          new Set(
            data.levels
              .map((lvl) => lvl.height)
              .filter((h): h is number => Boolean(h))
          )
        ).sort((a, b) => b - a);

        const qualityOptions = [0, ...heights]; // 0 = Auto

        const player = new Plyr(video, {
          controls: [
            'play-large', 'play', 'rewind', 'fast-forward',
            'progress', 'current-time', 'duration',
            'mute', 'volume', 'settings', 'fullscreen',
          ],
          settings: ['quality', 'speed'],
          // Slightly longer idle timer (3s vs default 2s) so the controls
          // stay visible a bit longer after the user stops moving the cursor.
          hideControls: 3000,
          clickToPlay: true,
          keyboard: { focused: true, global: true },
          quality: {
            default: 0,              // start on Auto
            options: qualityOptions, // full list available at init time
            forced: true,
            // Called by Plyr when the user picks a resolution in the menu
            onChange: (selectedQuality: number) => {
              const hlsInstance = hlsRef.current;
              if (!hlsInstance) return;
              if (selectedQuality === 0) {
                hlsInstance.currentLevel = -1; // -1 = ABR auto
              } else {
                const idx = hlsInstance.levels.findIndex(
                  (lvl) => lvl.height === selectedQuality,
                );
                hlsInstance.currentLevel = idx;
              }
            },
          },
          // Robust fullscreen: fallback keeps controls alive when the browser
          // remounts the video element into the fullscreen stacking context
          fullscreen: {
            enabled:   true,
            fallback:  true,   // CSS pseudo-fullscreen if native API fails
            iosNative: true,   // use iOS native FS instead of pseudo-FS
          },
          i18n: { qualityLabel: { 0: 'Auto' } },
          poster,
        });

        playerRef.current = player;

        // Keep the Plyr quality badge in sync with hls.js ABR decisions.
        // hls.js switches levels asynchronously; without this the badge
        // would show the requested level, not the one actually playing.
        hls.on(Hls.Events.LEVEL_SWITCHED, (_ev, { level }) => {
          if (!playerRef.current) return;
          const activeHeight = hlsRef.current?.levels[level]?.height ?? 0;
          try {
            (playerRef.current as unknown as { quality: number }).quality =
              activeHeight;
          } catch {
            // Plyr teardown may race this callback — safe to ignore
          }
        });

        // Seek to resume position once the manifest is ready
        if (initialTime > 0) {
          video.currentTime = initialTime;
        }
      });

      // Fatal HLS error recovery
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              hls.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              hls.recoverMediaError();
              break;
            default:
              hls.destroy();
              break;
          }
        }
      });

    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // iOS Safari — native HLS, Plyr without quality API
      video.src = src;
      const player = new Plyr(video, {
        poster,
        fullscreen: { enabled: true, fallback: true, iosNative: true },
      });
      playerRef.current = player;
      video.addEventListener('loadedmetadata', () => {
        if (initialTime > 0) video.currentTime = initialTime;
      }, { once: true });
    }

    // Native video event listeners — attached to the <video> element directly
    // so they survive any internal Plyr DOM operations.
    const handleTimeUpdate = () => {
      onTimeUpdate?.(video.currentTime, video.duration || 0);
    };
    const handlePause = () => {
      onPause?.(video.currentTime, video.duration || 0);
    };
    const handleEnded = () => {
      onEnded?.(video.duration || 0);
    };

    // Sliding Session: signal user activity while video is playing.
    // The custom event is picked up by useAutoRefreshSession to prevent
    // the JWT from expiring during a long viewing session.
    const handlePlaying = () => {
      window.dispatchEvent(new Event('video-play-activity'));
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('pause',      handlePause);
    video.addEventListener('ended',      handleEnded);
    video.addEventListener('playing',    handlePlaying);

    // ── Fullscreen bottom-edge hover fix ──────────────────────────────────
    // Problem: When the cursor reaches the absolute bottom pixel of the
    // screen in fullscreen, the browser fires `mouseleave` on the player
    // container, which Plyr interprets as "user stopped interacting" and
    // hides the control bar.  The CSS ::after pseudo-element catches some
    // cases, but browsers are inconsistent about hit-testing at y=max.
    //
    // Fix: Listen for mousemove on the document (survives the Plyr wrapper
    // re-parenting during fullscreen transitions).  If the cursor is within
    // the bottom 50px of the viewport AND Plyr is fullscreen, force the
    // controls to show via Plyr's toggleControls API.
    const BOTTOM_THRESHOLD_PX = 50;
    let fsHideTimer: ReturnType<typeof setTimeout> | null = null;

    const handleFullscreenMouseMove = (e: MouseEvent) => {
      const player = playerRef.current;
      if (!player || !player.fullscreen?.active) return;

      const distFromBottom = window.innerHeight - e.clientY;

      if (distFromBottom <= BOTTOM_THRESHOLD_PX) {
        // Cursor is near the bottom edge — force controls visible
        player.toggleControls(true);

        // Clear any pending auto-hide so the controls stay up while
        // the user is hovering the bottom zone.
        if (fsHideTimer) {
          clearTimeout(fsHideTimer);
          fsHideTimer = null;
        }
      } else {
        // Cursor moved away from the bottom zone — let Plyr resume its
        // normal auto-hide behaviour after a short delay.
        if (!fsHideTimer) {
          fsHideTimer = setTimeout(() => {
            fsHideTimer = null;
            // No explicit hide call — Plyr's own idle timer will handle it
          }, 2000);
        }
      }
    };

    document.addEventListener('mousemove', handleFullscreenMouseMove);

    // ── STEP 5: Cleanup ──────────────────────────────────────────────────
    // isMounted = false MUST be the very first line so the async
    // MANIFEST_PARSED callback sees it before anything else is torn down.
    return () => {
      isMounted = false;                        // ← kills the zombie callback
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('pause',      handlePause);
      video.removeEventListener('ended',      handleEnded);
      video.removeEventListener('playing',    handlePlaying);
      document.removeEventListener('mousemove', handleFullscreenMouseMove);
      if (fsHideTimer) clearTimeout(fsHideTimer);
      playerRef.current?.destroy();
      playerRef.current = null;
      hlsRef.current?.destroy();
      hlsRef.current = null;
    };
  }, [src]); // only re-init when the stream URL changes

  // ─────────────────────────────────────────────────────────────────────────
  // Effect 2 — seek when parent updates initialTime (user clicks "Resume")
  // Runs independently so the player is never destroyed just because
  // the user chose a resume position.
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video || initialTime <= 0) return;
    // readyState >= HAVE_METADATA means the seek is safe
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
      video.currentTime = initialTime;
    }
    // If not ready yet, MANIFEST_PARSED handler in Effect 1 covers it
  }, [initialTime]);

  return (
    <div style={{ width: '100%', marginBottom: '1.5rem' }}>
      {/*
        This <video> element must NEVER be conditionally rendered or given a
        changing key — Plyr binds directly to this DOM node and re-mounting
        it would silently detach all event listeners.
      */}
      <video ref={videoRef} />
    </div>
  );
};

export default HlsPlayer;
