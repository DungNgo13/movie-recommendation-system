import React, { useEffect, useRef } from 'react';
import Hls from 'hls.js';
import Plyr from 'plyr';
import 'plyr/dist/plyr.css';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation(['movies']);

  // Stable refs for callback props — lets Effect 1 read the latest callback
  // without listing them as dependencies (which would destroy and re-create
  // the entire HLS + Plyr stack on every parent render).
  const onTimeUpdateRef = useRef(onTimeUpdate);
  const onPauseRef = useRef(onPause);
  const onEndedRef = useRef(onEnded);
  const initialTimeRef = useRef(initialTime);

  // Sync refs in a layout-safe effect (runs after every render).
  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
    onPauseRef.current = onPause;
    onEndedRef.current = onEnded;
    initialTimeRef.current = initialTime;
  });

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

    // Guard flag: prevents LEVEL_SWITCHED → player.quality setter from
    // triggering onChange, which would set currentLevel again in a loop.
    let levelSwitchInProgress = false;

    // Tear down any surviving instances from a previous src
    playerRef.current?.destroy();
    playerRef.current = null;
    hlsRef.current?.destroy();
    hlsRef.current = null;

    // ── STEP 2: HLS path ─────────────────────────────────────────────────
    if (Hls.isSupported()) {
      const hls = new Hls({ maxBufferLength: 30, enableWorker: true });
      hlsRef.current = hls;

      // Cache-bust the master playlist URL so the browser never serves a
      // stale old .m3u8 (e.g. one that predates 4K support).
      const cacheBustedSrc = `${src}${src.includes('?') ? '&' : '?'}v=${Date.now()}`;
      hls.loadSource(cacheBustedSrc);
      hls.attachMedia(video);

      // ── STEP 3: Async callback with isMounted guard ───────────────────
      hls.on(Hls.Events.MANIFEST_PARSED, (_event, data) => {
        // CRITICAL: If cleanup already ran, bail out immediately.
        // This prevents the zombie-Plyr race condition entirely.
        if (!isMounted) return;

        // ── STEP 4: Build quality list, then init Plyr ───────────────────
        // De-duplicate heights and sort descending (e.g. [2160, 1440, 1080, 720, 480, 360])
        const heights = Array.from(
          new Set(
            data.levels
              .map((lvl) => lvl.height)
              .filter((h): h is number => Boolean(h))
          )
        ).sort((a, b) => b - a);

        if (import.meta.env.DEV) {
          console.debug('[HLS] Manifest parsed — levels:', data.levels.map(l => `${l.width}x${l.height}`));
          console.debug('[HLS] Quality menu will show:', [0, ...heights]);
        }

        const qualityOptions = [0, ...heights]; // 0 = Auto

        const player = new Plyr(video, {
          controls: [
            'play-large', 'play', 'rewind', 'fast-forward',
            'progress', 'current-time', 'duration',
            'mute', 'volume', 'settings', 'fullscreen',
          ],
          settings: ['quality', 'speed'],
          hideControls: true,
          clickToPlay: true,
          keyboard: { focused: true, global: true },
          quality: {
            default: 0,              // start on Auto
            options: qualityOptions, // dynamic from manifest
            forced: true,
            // Called by Plyr when the user picks a resolution in the menu.
            //
            // CRITICAL: This is ALSO called when we set player.quality in
            // the LEVEL_SWITCHED handler below. The levelSwitchInProgress
            // guard prevents that from turning into an infinite loop.
            onChange: (selectedQuality: number) => {
              // If this call was triggered by our own LEVEL_SWITCHED handler
              // updating the Plyr badge, ignore it — the level is already set.
              if (levelSwitchInProgress) return;

              const hlsInstance = hlsRef.current;
              const vid = videoRef.current;
              if (!hlsInstance || !vid) return;

              // Capture play state BEFORE the switch
              const wasPlaying = !vid.paused && !vid.ended;

              if (selectedQuality === 0) {
                // Auto ABR
                hlsInstance.currentLevel = -1;
              } else {
                const idx = hlsInstance.levels.findIndex(
                  (lvl) => lvl.height === selectedQuality,
                );
                if (idx >= 0) {
                  hlsInstance.currentLevel = idx;
                }
              }

              // DO NOT call hls.startLoad() here — hls.js already handles
              // segment loading internally when currentLevel changes.
              // Calling startLoad() interferes with the level-switch state
              // machine and can cause buffer stalls.

              // Resume playback if needed. requestAnimationFrame ensures the
              // browser has processed the level change before we nudge play.
              if (wasPlaying) {
                requestAnimationFrame(() => {
                  vid.play().catch(() => {
                    // Browser may reject play() without user gesture — safe to ignore
                  });
                });
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
          i18n: { 
            qualityLabel: { 0: t('movies:plyr.auto', 'Auto') },
            quality: t('movies:plyr.quality', 'Quality'),
            speed: t('movies:plyr.speed', 'Speed'),
            normal: t('movies:plyr.normal', 'Normal'),
          },
        });

        playerRef.current = player;

        // Keep the Plyr quality badge in sync with hls.js ABR decisions.
        //
        // When hls.js finishes switching to a new level (either from user
        // selection or ABR), update Plyr's displayed quality label.
        //
        // The levelSwitchInProgress flag prevents the circular loop:
        //   LEVEL_SWITCHED → set player.quality → Plyr calls onChange
        //   → onChange sets currentLevel → triggers another LEVEL_SWITCHED
        hls.on(Hls.Events.LEVEL_SWITCHED, (_ev, { level }) => {
          if (!playerRef.current || !hlsRef.current) return;
          const activeHeight = hlsRef.current.levels[level]?.height ?? 0;

          if (import.meta.env.DEV) {
            console.debug('[HLS] Level switched to:', level, `(${activeHeight}p)`);
          }

          // Set flag BEFORE touching player.quality to block the onChange callback
          levelSwitchInProgress = true;
          try {
            (playerRef.current as unknown as { quality: number }).quality =
              activeHeight;
          } catch {
            // Plyr teardown may race this callback — safe to ignore
          }
          levelSwitchInProgress = false;
        });

        // Seek to resume position once the manifest is ready
        if (initialTimeRef.current > 0) {
          video.currentTime = initialTimeRef.current;
          if (import.meta.env.DEV) {
            console.debug('[watch-progress] resume applied', {
              appliedPosition: initialTimeRef.current,
            });
          }
        }
      });

      // Fatal HLS error recovery
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (import.meta.env.DEV) {
          console.debug('[HLS] Error:', data.type, data.details, 'fatal:', data.fatal);
        }
        if (!data.fatal) return;

        const vid = videoRef.current;

        if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
          hls.recoverMediaError();
          // After recovery, resume playback if the video was playing
          if (vid && !vid.paused) {
            vid.play().catch(() => {});
          }
          return;
        }

        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
          hls.startLoad(vid?.currentTime ?? 0);
          return;
        }

        // Unrecoverable error — destroy
        hls.destroy();
      });

    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // iOS Safari — native HLS, Plyr without quality API
      video.src = src;
      const player = new Plyr(video, {
        fullscreen: { enabled: true, fallback: true, iosNative: true },
      });
      playerRef.current = player;
      video.addEventListener('loadedmetadata', () => {
        if (initialTimeRef.current > 0) video.currentTime = initialTimeRef.current;
      }, { once: true });
    }

    // Native video event listeners — attached to the <video> element directly
    // so they survive any internal Plyr DOM operations.
    let tuCount = 0;
    const handleTimeUpdate = () => {
      const ct = video.currentTime;
      const dur = video.duration || 0;
      // Log every ~60th timeupdate (~once per 15s at 4Hz) to avoid flooding
      if (import.meta.env.DEV && tuCount % 60 === 0) {
        console.debug('[watch-progress] video event', {
          event: 'timeupdate', movieSrc: src.split('/').pop(),
          currentTime: ct, duration: dur,
          paused: video.paused, readyState: video.readyState,
        });
      }
      tuCount++;
      onTimeUpdateRef.current?.(ct, dur);
    };
    const handlePause = () => {
      if (import.meta.env.DEV) {
        console.debug('[watch-progress] video event', {
          event: 'pause', currentTime: video.currentTime,
          duration: video.duration || 0,
        });
      }
      onPauseRef.current?.(video.currentTime, video.duration || 0);
    };
    const handleEnded = () => {
      if (import.meta.env.DEV) {
        console.debug('[watch-progress] video event', {
          event: 'ended', duration: video.duration || 0,
        });
      }
      onEndedRef.current?.(video.duration || 0);
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

    // ── STEP 5: Cleanup ──────────────────────────────────────────────────
    // isMounted = false MUST be the very first line so the async
    // MANIFEST_PARSED callback sees it before anything else is torn down.
    return () => {
      isMounted = false;                        // ← kills the zombie callback
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('pause',      handlePause);
      video.removeEventListener('ended',      handleEnded);
      video.removeEventListener('playing',    handlePlaying);
      playerRef.current?.destroy();
      playerRef.current = null;
      hlsRef.current?.destroy();
      hlsRef.current = null;
    };
  }, [src]); // only re-init when the stream URL changes

  // ─────────────────────────────────────────────────────────────────────────
  // Effect 3 — Fullscreen bottom-edge event forwarding
  //
  // Problem: When the cursor hits the absolute bottom pixel of the monitor
  // in fullscreen, the browser stops firing mousemove on the .plyr container
  // (treats it as mouseleave).  Plyr's internal idle timer expires and it
  // hides the controls.
  //
  // Fix: Listen for mousemove on `window` (always receives events, even at
  // screen edges).  If we're in fullscreen AND the cursor is within the
  // bottom 30px, dispatch a synthetic mousemove directly onto the Plyr
  // container.  This resets Plyr's 3s auto-hide timer naturally, without
  // overriding any config or fighting its internal state machine.
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const EDGE_THRESHOLD = 30;

    const handleWindowMouseMove = (e: MouseEvent) => {
      // Only act when in fullscreen
      if (!document.fullscreenElement) return;

      // Only act when cursor is at the bottom edge
      if (window.innerHeight - e.clientY > EDGE_THRESHOLD) return;

      // Forward the event to the Plyr container so its internal timer resets
      const plyrContainer = playerRef.current?.elements?.container;
      if (plyrContainer) {
        plyrContainer.dispatchEvent(new MouseEvent('mousemove', {
          bubbles: true,
          clientX: e.clientX,
          clientY: e.clientY,
        }));
      }
    };

    window.addEventListener('mousemove', handleWindowMouseMove);
    return () => window.removeEventListener('mousemove', handleWindowMouseMove);
  }, []);

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
    <div className="hls-player-inner">
      {/*
        This <video> element must NEVER be conditionally rendered or given a
        changing key — Plyr binds directly to this DOM node and re-mounting
        it would silently detach all event listeners.
      */}
      <video ref={videoRef} poster={poster} />
    </div>
  );
};

export default HlsPlayer;
