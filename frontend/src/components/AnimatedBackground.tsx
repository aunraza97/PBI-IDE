import React, { useEffect, useRef } from 'react';

interface AnimatedBackgroundProps {
  theme?: string;
}

const AnimatedBackground: React.FC<AnimatedBackgroundProps> = ({ theme = 'dark' }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animationFrameId: number;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    const mouse = { x: null as number | null, y: null as number | null };
    const handleMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };
    const handleMouseLeave = () => {
      mouse.x = null;
      mouse.y = null;
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);

    // DNA Parameters
    const amplitude = 100;
    const frequency = 0.005;
    const speed = 0.015;
    const yOffset = 0.5;

    let time = 0;

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      time += 1;

      const bgGradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
      let color1, color2, waveColorRGB, glowColor;

      switch(theme) {
        case 'light':
          color1 = '#ffffff';
          color2 = '#f8f9fa';
          waveColorRGB = '242, 200, 17'; // Golden Yellow
          glowColor = '#f2c811';
          break;
        case 'ocean':
          color1 = '#042f2e';
          color2 = '#164e63';
          waveColorRGB = '45, 212, 191'; // Teal
          glowColor = '#5eead4';
          break;
        case 'midnight':
          color1 = '#1e1b4b';
          color2 = '#312e81';
          waveColorRGB = '129, 140, 248'; // Indigo
          glowColor = '#a5b4fc';
          break;
        case 'purple':
          color1 = '#1a0b2e';
          color2 = '#2d1447';
          waveColorRGB = '139, 92, 246'; // Purple
          glowColor = '#a78bfa';
          break;
        case 'dark':
        default:
          color1 = '#020617';
          color2 = '#0f172a';
          waveColorRGB = '59, 130, 246'; // Blue
          glowColor = '#60a5fa';
          break;
      }

      bgGradient.addColorStop(0, color1);
      bgGradient.addColorStop(1, color2);
      ctx.fillStyle = bgGradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Data DNA - Perfect 3D depth sorted drawing
      const segments = [];
      const segmentWidth = Math.max(10, canvas.width / 150); // adaptive detail
      
      for (let x = -100; x <= canvas.width + 100; x += segmentWidth) {
         const angle1 = x * frequency - time * speed;
         const angle2 = angle1 + Math.PI;
         
         const nextAngle1 = (x + segmentWidth) * frequency - time * speed;
         const nextAngle2 = nextAngle1 + Math.PI;
         
         // Add subtle mouse repel to yOffset locally
         let localYOffset = canvas.height * yOffset;
         if (mouse.x !== null && mouse.y !== null) {
            const dx = mouse.x - x;
            const dy = mouse.y - localYOffset;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance < 300) {
              const force = (300 - distance) / 300;
              localYOffset += (dy > 0 ? -1 : 1) * force * 40;
            }
         }

         const y1 = localYOffset + Math.sin(angle1) * amplitude;
         const nextY1 = localYOffset + Math.sin(nextAngle1) * amplitude;
         const z1 = Math.cos(angle1);
         
         const y2 = localYOffset + Math.sin(angle2) * amplitude;
         const nextY2 = localYOffset + Math.sin(nextAngle2) * amplitude;
         const z2 = Math.cos(angle2);
         
         segments.push({
            x1: x, y1: y1, nx1: x + segmentWidth, ny1: nextY1, z1: z1,
            x2: x, y2: y2, nx2: x + segmentWidth, ny2: nextY2, z2: z2,
            localYOffset: localYOffset,
            angle: angle1
         });
      }
      
      // 1. Draw back strands (z <= 0)
      segments.forEach(seg => {
         if (seg.z1 <= 0) {
            ctx.beginPath(); ctx.moveTo(seg.x1, seg.y1); ctx.lineTo(seg.nx1, seg.ny1);
            ctx.strokeStyle = `rgba(${waveColorRGB}, ${0.1 + (seg.z1 + 1) * 0.2})`;
            ctx.lineWidth = 1.5; ctx.stroke();
         }
         if (seg.z2 <= 0) {
            ctx.beginPath(); ctx.moveTo(seg.x2, seg.y2); ctx.lineTo(seg.nx2, seg.ny2);
            ctx.strokeStyle = `rgba(${waveColorRGB}, ${0.1 + (seg.z2 + 1) * 0.2})`;
            ctx.lineWidth = 1.5; ctx.stroke();
         }
      });
      
      // 2. Draw base pairs and data points
      const basePairSpacing = 40;
      for (let x = -100; x <= canvas.width + 100; x += basePairSpacing) {
         // Find matching segment for yOffset
         const seg = segments.find(s => x >= s.x1 && x < s.nx1) || segments[0];
         const angle = x * frequency - time * speed;
         
         const y1 = seg.localYOffset + Math.sin(angle) * amplitude;
         const y2 = seg.localYOffset + Math.sin(angle + Math.PI) * amplitude;
         
         // Draw connector line
         ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x, y2);
         ctx.strokeStyle = `rgba(${waveColorRGB}, 0.15)`;
         ctx.lineWidth = 1; ctx.stroke();
         
         const z1 = Math.cos(angle);
         const z2 = Math.cos(angle + Math.PI);
         
         // Function to draw a single data point
         const drawDataPoint = (py: number, pz: number) => {
            const rad = 2 + (pz + 1) * 1.5; // size based on depth
            ctx.beginPath(); ctx.arc(x, py, rad, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${waveColorRGB}, ${0.3 + (pz + 1) * 0.35})`;
            
            // Add glow if in front
            if (pz > 0) {
               ctx.shadowBlur = 12;
               ctx.shadowColor = glowColor;
            }
            
            ctx.fill(); 
            ctx.shadowBlur = 0; // reset
         };
         
         // Sort points so front is drawn last
         if (z1 < z2) { 
           drawDataPoint(y1, z1); 
           drawDataPoint(y2, z2); 
         } else { 
           drawDataPoint(y2, z2); 
           drawDataPoint(y1, z1); 
         }
      }
      
      // 3. Draw front strands (z > 0)
      segments.forEach(seg => {
         if (seg.z1 > 0) {
            ctx.beginPath(); ctx.moveTo(seg.x1, seg.y1); ctx.lineTo(seg.nx1, seg.ny1);
            ctx.strokeStyle = `rgba(${waveColorRGB}, ${0.3 + (seg.z1 + 1) * 0.3})`;
            ctx.lineWidth = 2.5; ctx.stroke();
         }
         if (seg.z2 > 0) {
            ctx.beginPath(); ctx.moveTo(seg.x2, seg.y2); ctx.lineTo(seg.nx2, seg.ny2);
            ctx.strokeStyle = `rgba(${waveColorRGB}, ${0.3 + (seg.z2 + 1) * 0.3})`;
            ctx.lineWidth = 2.5; ctx.stroke();
         }
      });

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, [theme]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 0,
        pointerEvents: 'none'
      }}
    />
  );
};

export default AnimatedBackground;
