import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';

interface HlsPlayerProps {
  src: string;
  poster?: string;
  initialTime?: number;
  onTimeUpdate?: (currentTime: number, duration: number) => void;
  onPause?: (currentTime: number, duration: number) => void;
  onEnded?: (duration: number) => void;
}

interface QualityLevel {
  index: number;
  label: string;
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

  // Store the hls instance in a ref so both effects and the quality handler
  // can access the same object without triggering re-renders.
  const hlsRef = useRef<Hls | null>(null);

  const [levels, setLevels] = useState<QualityLevel[]>([]);
  const [currentLevel, setCurrentLevel] = useState<number>(-1); // -1 = Auto

  // ── Effect 1: initialise HLS when src changes ────────────────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Clean up any previous instance
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    setLevels([]);
    setCurrentLevel(-1);

    if (Hls.isSupported()) {
      const hls = new Hls({ maxBufferLength: 30, enableWorker: true });
      hlsRef.current = hls;

      hls.loadSource(src);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, (_event, data) => {
        // Build quality labels from the parsed levels
        const qualityLevels: QualityLevel[] = data.levels.map((lvl, idx) => ({
          index: idx,
          label: lvl.height ? `${lvl.height}p` : `Level ${idx}`,
        }));
        setLevels(qualityLevels);
        setCurrentLevel(-1); // start on Auto

        // Seek to resume position AFTER manifest is ready
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
      // iOS Safari native HLS — no level API available
      video.src = src;
      video.addEventListener('loadedmetadata', () => {
        if (initialTime > 0) {
          video.currentTime = initialTime;
        }
      });
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [src]); // only re-init when the stream URL changes

  // ── Effect 2: seek when initialTime changes (e.g. user clicks Resume) ───
  // This runs independently so we do NOT rebuild the whole HLS instance.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || initialTime <= 0) return;

    // If the video already has metadata (manifest loaded), seek immediately.
    // Otherwise the MANIFEST_PARSED handler above will handle it.
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
      video.currentTime = initialTime;
    }
  }, [initialTime]);

  // ── Quality change handler ────────────────────────────────────────────────
  const handleQualityChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = parseInt(e.target.value, 10);
    setCurrentLevel(selected);
    if (hlsRef.current) {
      hlsRef.current.currentLevel = selected; // -1 = Auto, 0+ = specific level
    }
  };

  return (
    <div
      className="hls-player-container"
      style={{ width: '100%', marginBottom: '1.5rem', backgroundColor: '#000', borderRadius: '8px', overflow: 'hidden' }}
    >
      <video
        ref={videoRef}
        controls
        poster={poster}
        style={{ width: '100%', display: 'block', maxHeight: '720px' }}
        onTimeUpdate={() => {
          const video = videoRef.current;
          if (onTimeUpdate && video) {
            onTimeUpdate(video.currentTime, video.duration || 0);
          }
        }}
        onPause={() => {
          const video = videoRef.current;
          if (onPause && video) {
            onPause(video.currentTime, video.duration || 0);
          }
        }}
        onEnded={() => {
          const video = videoRef.current;
          if (onEnded && video) {
            onEnded(video.duration || 0);
          }
        }}
      />

      {/* Quality selector — only shown when HLS levels are available */}
      {levels.length > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.4rem 0.75rem',
          backgroundColor: '#111', color: '#ccc', fontSize: '0.85rem',
        }}>
          <label htmlFor="hls-quality-select" style={{ whiteSpace: 'nowrap' }}>
            Quality:
          </label>
          <select
            id="hls-quality-select"
            value={currentLevel}
            onChange={handleQualityChange}
            style={{
              background: '#222', color: '#fff', border: '1px solid #444',
              borderRadius: '4px', padding: '0.2rem 0.4rem', cursor: 'pointer',
            }}
          >
            <option value={-1}>Auto</option>
            {levels.map((lvl) => (
              <option key={lvl.index} value={lvl.index}>
                {lvl.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};

export default HlsPlayer;
