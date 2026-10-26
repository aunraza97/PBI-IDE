import { useState, useEffect } from 'react';
import { ArrowRight } from 'lucide-react';

interface SplashScreenProps {
  isLoading: boolean;
  statusText?: string;
  minDurationMs?: number;
}

export default function SplashScreen({
  isLoading,
  statusText = 'Initializing Power BI IDE...',
  minDurationMs = 1200,
}: SplashScreenProps) {
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [isFading, setIsFading] = useState(false);
  const [isVisible, setIsVisible] = useState(true);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setMinTimeElapsed(true);
    }, minDurationMs);
    return () => clearTimeout(timer);
  }, [minDurationMs]);

  useEffect(() => {
    if (!isLoading && minTimeElapsed) {
      setIsReady(true);
    }
  }, [isLoading, minTimeElapsed]);

  const handleEnter = () => {
    setIsFading(true);
    setTimeout(() => {
      setIsVisible(false);
    }, 500);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isReady && e.key === 'Enter') {
        handleEnter();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isReady]);

  if (!isVisible) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: '#ffffff',
        zIndex: 999999,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: isFading ? 0 : 1,
        transition: 'opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        pointerEvents: isFading ? 'none' : 'auto',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '40px',
          animation: 'splashFadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Logo */}
        <div style={{ maxWidth: '340px', width: '80vw', display: 'flex', justifyContent: 'center' }}>
          <img
            src="/PBI_Logo.png"
            alt="Power BI IDE"
            style={{
              width: '100%',
              height: 'auto',
              objectFit: 'contain',
              userSelect: 'none',
            }}
          />
        </div>

        {/* Action / Loader Area */}
        <div
          style={{
            height: '90px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '14px',
          }}
        >
          {!isReady ? (
            <>
              <div
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '50%',
                  border: '3.5px solid rgba(242, 200, 17, 0.2)',
                  borderTopColor: '#f2c811',
                  animation: 'splashSpin 0.85s linear infinite',
                }}
              />
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: 500,
                  color: '#64748b',
                  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
                  letterSpacing: '0.02em',
                }}
              >
                {statusText}
              </span>
            </>
          ) : (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px',
                animation: 'buttonEntrance 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              <button
                onClick={handleEnter}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
                title="Launch PBI IDE"
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  backgroundColor: '#f2c811',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: isHovered
                    ? '0 8px 26px rgba(242, 200, 17, 0.55), 0 2px 8px rgba(0, 0, 0, 0.08)'
                    : '0 4px 16px rgba(242, 200, 17, 0.35)',
                  transform: isHovered ? 'scale(1.08)' : 'scale(1)',
                  transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                  outline: 'none',
                }}
              >
                <ArrowRight
                  size={26}
                  color="#1e293b"
                  style={{
                    transform: isHovered ? 'translateX(3px)' : 'translateX(0)',
                    transition: 'transform 0.25s ease',
                  }}
                />
              </button>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#64748b',
                  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}
              >
                Click to Start
              </span>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes splashSpin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes splashFadeIn {
          0% { opacity: 0; transform: translateY(8px) scale(0.98); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes buttonEntrance {
          0% { opacity: 0; transform: scale(0.7); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
