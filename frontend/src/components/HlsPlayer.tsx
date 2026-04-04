import React, { useEffect, useRef } from 'react';
import Hls from 'hls.js';

interface HlsPlayerProps {
  src: string;
  poster?: string;
  initialTime?: number;
  onTimeUpdate?: (currentTime: number) => void;
}

const HlsPlayer: React.FC<HlsPlayerProps> = ({ src, poster, initialTime = 0, onTimeUpdate }) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let hls: Hls;

    if (Hls.isSupported()) {
      hls = new Hls({
        // Optional configuration bindings
        maxBufferLength: 30,
        enableWorker: true
      });
      
      hls.loadSource(src);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        // Video is completely ready. 
        if (initialTime > 0) {
          video.currentTime = initialTime;
        }
      });

      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              console.error('HLS Network Error, attempting recovery...');
              hls.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              console.error('HLS Media Error, attempting recovery...');
              hls.recoverMediaError();
              break;
            default:
              // Cannot recover native crash out
              console.error('HLS Unrecoverable Error:', data);
              hls.destroy();
              break;
          }
        }
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Direct pass-through for iOS Safari
      video.src = src;
      video.addEventListener('loadedmetadata', () => {
        if (initialTime > 0) {
          video.currentTime = initialTime;
        }
      });
    }

    return () => {
      if (hls) {
        hls.destroy();
      }
    };
  }, [src]);

  return (
    <div className="hls-player-container" style={{ width: '100%', marginBottom: '1.5rem', backgroundColor: '#000', borderRadius: '8px', overflow: 'hidden' }}>
      <video
        ref={videoRef}
        controls
        poster={poster}
        style={{ width: '100%', display: 'block', maxHeight: '720px' }}
        onTimeUpdate={() => {
          if (onTimeUpdate && videoRef.current) {
            onTimeUpdate(videoRef.current.currentTime);
          }
        }}
      />
    </div>
  );
};

export default HlsPlayer;
