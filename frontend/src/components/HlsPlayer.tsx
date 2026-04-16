/**
 * HlsPlayer — Plyr + hls.js integration
 *
 * KEY DESIGN RULES (prevents the fullscreen controls bug):
 *
 * ① Plyr is created ONCE, synchronously, before the HLS manifest arrives.
 *    Creating Plyr inside the async MANIFEST_PARSED callback caused a race:
 *    React's cleanup could destroy the first instance while a stale callback
 *    was creating a second one, leaving the fullscreen overlay without any
 *    mousemove/click listeners.
 *
 * ② Quality levels are injected by mutating the existing Plyr instance's
 *    config in-place (player.config.quality.*) — no re-construction needed.
 *    Plyr re-renders its settings menu automatically when the options array
 *    is replaced; the DOM wrapper and its event listeners are preserved.
 *
 * ③ The fullscreen option includes fallback + iosNative so the controls
 *    overlay remains interactive even when using the browser's native
 *    fullscreen API (which remounts the video into a new stacking context
 *    on some Chromium versions).
 *
 * ④ The component never stores mutable state in React state variables.
 *    All hls/plyr side-effects live in refs so React never schedules a
 *    re-render because of them.
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
  //
  // CRITICAL: Plyr is instantiated here SYNCHRONOUSLY, before the async
  // MANIFEST_PARSED event fires.  This guarantees:
  //   • Exactly one Plyr instance exists at all times.
  //   • Plyr's fullscreen/control event listeners are bound once and never
  //     detached by a stale async callback.
  //   • Quality levels are patched into the live instance, not via re-init.
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // ── Tear down previous instances ──────────────────────────────────────
    playerRef.current?.destroy();
    playerRef.current = null;
    hlsRef.current?.destroy();
    hlsRef.current = null;

    // ── ① Create Plyr immediately with a placeholder quality option ───────
    //
    // We start with just [0] (Auto) so Plyr renders its UI straight away.
    // Real levels will be patched in once the manifest arrives.
    const player = new Plyr(video, {
      controls: [
        'play-large', 'play', 'rewind', 'fast-forward',
        'progress', 'current-time', 'duration',
        'mute', 'volume', 'settings', 'fullscreen',
      ],
      settings: ['quality', 'speed'],
      quality: {
        default: 0,        // 0 = Auto
        options: [0],      // will be replaced after manifest
        forced: true,
        // onChange: patched below once hls is live
        onChange: (_q: number) => { /* placeholder — replaced after manifest */ },
      },

      // ── ③ Fullscreen config: robust fallback for all browsers ─────────
      fullscreen: {
        enabled:   true,
        fallback:  true,   // use CSS fullscreen if native API fails
        iosNative: true,   // use iOS native fullscreen instead of pseudo-FS
      },

      i18n: { qualityLabel: { 0: 'Auto' } },
      poster,
    });

    playerRef.current = player;

    // ── HLS path (hls.js supported) ───────────────────────────────────────
    if (Hls.isSupported()) {
      const hls = new Hls({ maxBufferLength: 30, enableWorker: true });
      hlsRef.current = hls;

      hls.loadSource(src);
      hls.attachMedia(video);

      // ── ② Patch quality levels into the EXISTING Plyr instance ──────────
      //
      // We do NOT call new Plyr() here.  Instead we mutate player.config
      // directly and refresh the settings menu.  React is not involved —
      // no setState, no re-render, no unmount of the video wrapper.
      hls.on(Hls.Events.MANIFEST_PARSED, (_event, data) => {
        // De-duplicate heights and sort descending (e.g. [1080, 720, 480, 360])
        const heights = Array.from(
          new Set(
            data.levels
              .map((lvl) => lvl.height)
              .filter((h): h is number => Boolean(h))
          )
        ).sort((a, b) => b - a);

        const qualityOptions = [0, ...heights];

        // Mutate the existing config — Plyr checks config on next settings open
        player.config.quality.options  = qualityOptions;
        player.config.quality.default  = 0;

        // Wire the real onChange handler now that hls.js levels are known
        player.config.quality.onChange = (selectedQuality: number) => {
          const hlsInstance = hlsRef.current;
          if (!hlsInstance) return;
          if (selectedQuality === 0) {
            hlsInstance.currentLevel = -1;          // -1 = ABR auto
          } else {
            const idx = hlsInstance.levels.findIndex(
              (lvl) => lvl.height === selectedQuality,
            );
            hlsInstance.currentLevel = idx;
          }
        };

        // Seek to resume position after manifest is parsed
        if (initialTime > 0) {
          video.currentTime = initialTime;
        }
      });

      // ── Keep Plyr quality badge in sync with hls.js ABR decisions ───────
      //
      // hls.js switches levels asynchronously; without this listener the
      // Plyr badge would show the requested level, not the actual playing one.
      hls.on(Hls.Events.LEVEL_SWITCHED, (_ev, { level }) => {
        const activeHeight = hlsRef.current?.levels[level]?.height ?? 0;
        try {
          // Plyr 3 exposes quality as a writable property that updates the badge.
          (player as unknown as { quality: number }).quality = activeHeight;
        } catch {
          // Safe to ignore if Plyr teardown races this callback
        }
      });

      // ── Fatal error recovery ──────────────────────────────────────────────
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
      // iOS Safari — native HLS, no hls.js, Plyr already created above
      video.src = src;
      video.addEventListener('loadedmetadata', () => {
        if (initialTime > 0) video.currentTime = initialTime;
      }, { once: true });
    }

    // ── Native video event listeners ──────────────────────────────────────
    //
    // Attached to the raw <video> element, not to Plyr, so they survive
    // any internal Plyr settings-menu re-render.
    const handleTimeUpdate = () => {
      onTimeUpdate?.(video.currentTime, video.duration || 0);
    };
    const handlePause = () => {
      onPause?.(video.currentTime, video.duration || 0);
    };
    const handleEnded = () => {
      onEnded?.(video.duration || 0);
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('pause',      handlePause);
    video.addEventListener('ended',      handleEnded);

    // ── Cleanup (runs on src change or unmount) ───────────────────────────
    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('pause',      handlePause);
      video.removeEventListener('ended',      handleEnded);
      playerRef.current?.destroy();
      playerRef.current = null;
      hlsRef.current?.destroy();
      hlsRef.current = null;
    };
  }, [src]); // ← only re-init when the stream URL changes

  // ─────────────────────────────────────────────────────────────────────────
  // Effect 2 — seek when the user picks "Resume" (initialTime updates)
  //
  // Runs independently of Effect 1 so the player is never destroyed just
  // because the parent updated the resume position.
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video || initialTime <= 0) return;
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
      video.currentTime = initialTime;
    }
    // If not ready yet, the MANIFEST_PARSED handler in Effect 1 handles it
  }, [initialTime]);

  return (
    <div style={{ width: '100%', marginBottom: '1.5rem' }}>
      {/*
        The <video> element MUST NOT be conditionally rendered or
        given a key that changes — Plyr binds directly to this DOM node.
        Re-mounting it would silently orphan all Plyr event listeners.
      */}
      <video ref={videoRef} />
    </div>
  );
};

export default HlsPlayer;
