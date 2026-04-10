import React, { useEffect, useRef } from 'react';
import Hls from 'hls.js';

interface HlsPlayerProps {
  src: string;
  poster?: string;
  initialTime?: number;
  onTimeUpdate?: (currentTime: number, duration: number) => void;
  onPause?: (currentTime: number, duration: number) => void;
  onEnded?: (duration: number) => void;
}

const HlsPlayer: React.FC<HlsPlayerProps> = ({ src, poster, initialTime = 0, onTimeUpdate, onPause, onEnded }) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let hls: Hls;

    if (Hls.isSupported()) {
      hls = new Hls({
        maxBufferLength: 30,
        enableWorker: true,
      });

      hls.loadSource(src);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
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
      // iOS Safari native HLS
      video.src = src;
      video.addEventListener('loadedmetadata', () => {
        if (initialTime > 0) {
          video.currentTime = initialTime;
        }
      });
    }

    return () => {
      if (hls) hls.destroy();
    };
  }, [src]);

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
    </div>
  );
};

export default HlsPlayer;
