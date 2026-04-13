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
  const videoRef = useRef<HTMLVideoElement>(null);

  // Store hls + plyr instances so they can be accessed across effects & cleanup
  const hlsRef = useRef<Hls | null>(null);
  const playerRef = useRef<Plyr | null>(null);

  // ── Effect 1: init HLS + Plyr when src changes ───────────────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Tear down any previous instances before building new ones
    if (playerRef.current) { playerRef.current.destroy(); playerRef.current = null; }
    if (hlsRef.current)    { hlsRef.current.destroy();    hlsRef.current = null;    }

    if (Hls.isSupported()) {
      const hls = new Hls({ maxBufferLength: 30, enableWorker: true });
      hlsRef.current = hls;

      hls.loadSource(src);
      hls.attachMedia(video);

      // Wait for the manifest so we know the available quality levels
      hls.on(Hls.Events.MANIFEST_PARSED, (_event, data) => {
        // Build the quality array: 0 = Auto, then real heights (1080, 720, …)
        // Deduplicate & sort descending so the menu looks natural.
        const heights = Array.from(
          new Set(
            data.levels
              .map((lvl) => lvl.height)
              .filter((h): h is number => Boolean(h))
          )
        ).sort((a, b) => b - a);

        const qualityOptions = [0, ...heights]; // 0 = Auto

        // Initialise Plyr now that we know available qualities.
        // Plyr renders the quality menu once at init time, so we init here.
        const player = new Plyr(video, {
          controls: [
            'play-large', 'play', 'rewind', 'fast-forward',
            'progress', 'current-time', 'duration',
            'mute', 'volume', 'settings', 'fullscreen',
          ],
          settings: ['quality', 'speed'],
          quality: {
            default: 0,           // start on Auto
            options: qualityOptions,
            forced: true,
            // When the user picks a quality in the Plyr settings menu:
            onChange: (selectedQuality: number) => {
              if (!hlsRef.current) return;
              if (selectedQuality === 0) {
                hlsRef.current.currentLevel = -1; // -1 = ABR auto
              } else {
                const idx = hlsRef.current.levels.findIndex(
                  (lvl) => lvl.height === selectedQuality,
                );
                hlsRef.current.currentLevel = idx;
              }
            },
          },
          // Plyr 3 i18n: label the "0" option as "Auto" in the menu
          i18n: { qualityLabel: { 0: 'Auto' } },
          poster,
        });

        playerRef.current = player;

        // ── LEVEL_SWITCHED: keep the Plyr quality badge in sync ─────────────
        // hls.js switches levels asynchronously; without this listener the
        // Plyr menu would show the previously selected value instead of the
        // level that is actually playing.
        hls.on(Hls.Events.LEVEL_SWITCHED, (_ev, { level }) => {
          if (!playerRef.current) return;
          const activeHeight = hlsRef.current?.levels[level]?.height ?? 0;
          // Plyr 3 exposes quality as a writable property.
          // Setting it here updates the badge without re-triggering onChange.
          try {
            (playerRef.current as unknown as { quality: number }).quality =
              activeHeight;
          } catch {
            // Plyr may not be fully initialised on first switch — safe to ignore.
          }
        });

        // Seek to resume position once the manifest is ready
        if (initialTime > 0) {
          video.currentTime = initialTime;
        }
      });

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
      // iOS Safari has native HLS support — no hls.js needed, no quality API
      video.src = src;
      const player = new Plyr(video, { poster });
      playerRef.current = player;

      video.addEventListener('loadedmetadata', () => {
        if (initialTime > 0) video.currentTime = initialTime;
      });
    }

    // Attach progress callbacks directly on the native video element.
    // Plyr wraps the same element so these always fire regardless of
    // which controls the user interacts with.
    const handleTimeUpdate = () => {
      if (onTimeUpdate && videoRef.current) {
        onTimeUpdate(videoRef.current.currentTime, videoRef.current.duration || 0);
      }
    };
    const handlePause = () => {
      if (onPause && videoRef.current) {
        onPause(videoRef.current.currentTime, videoRef.current.duration || 0);
      }
    };
    const handleEnded = () => {
      if (onEnded && videoRef.current) {
        onEnded(videoRef.current.duration || 0);
      }
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('pause',      handlePause);
    video.addEventListener('ended',      handleEnded);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('pause',      handlePause);
      video.removeEventListener('ended',      handleEnded);
      if (playerRef.current) { playerRef.current.destroy(); playerRef.current = null; }
      if (hlsRef.current)    { hlsRef.current.destroy();    hlsRef.current = null;    }
    };
  }, [src]); // only re-init when the stream URL itself changes

  // ── Effect 2: seek when resume time changes (user clicks "Resume") ───────
  // The HLS effect above only runs on [src], so when the parent updates
  // initialTime after the user clicks "Resume", we need this separate effect
  // to actually perform the seek without destroying and rebuilding the player.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || initialTime <= 0) return;
    // readyState >= HAVE_METADATA means the manifest has been parsed and
    // the video element knows the duration — seeking is safe at this point.
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
      video.currentTime = initialTime;
    }
    // If not ready yet, the MANIFEST_PARSED handler in Effect 1 covers it
  }, [initialTime]);

  return (
    // Plyr replaces the <video> element's native controls with its own UI,
    // so we only need a bare <video> tag here. Plyr manages everything else.
    <div style={{ width: '100%', marginBottom: '1.5rem' }}>
      <video ref={videoRef} />
    </div>
  );
};

export default HlsPlayer;
