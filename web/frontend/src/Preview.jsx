import React, { useEffect, useRef } from 'react';

const W = 1080;
const H = 1920;

const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));

// Aperçu animé des réglages : mêmes proportions et mêmes conventions d'angles que le rendu Python
export default function Preview({ params }) {
  const canvasRef = useRef(null);
  const paramsRef = useRef(params);
  paramsRef.current = params;

  useEffect(() => {
    const ctx = canvasRef.current.getContext('2d');
    let frame = 0;
    let raf;
    const draw = () => {
      const p = paramsRef.current;
      const cx = W / 2;
      const cy = H / 2;
      const gap = (p.gap_degrees * Math.PI) / 180;
      const rot = (p.rotation_speed * Math.PI) / 180;
      const from = hexToRgb(p.arc_color_start);
      const to = hexToRgb(p.arc_color_end);

      ctx.fillStyle = p.background;
      ctx.fillRect(0, 0, W, H);
      ctx.lineWidth = p.arc_thickness;
      for (let i = 0; i < p.arc_count; i += 1) {
        const r = p.inner_radius + (i + 1) * p.arc_spacing;
        const start = 0.1 * (i + 1) + rot * frame;
        // pygame mesure les angles dans le sens anti-horaire : on inverse pour le canvas
        ctx.strokeStyle = `rgb(${mix(from, to, p.arc_count > 1 ? i / (p.arc_count - 1) : 0).join(',')})`;
        ctx.beginPath();
        ctx.arc(cx, cy, r - p.arc_thickness / 2, -start, -(start + 2 * Math.PI - gap), true);
        ctx.stroke();
      }

      const n = p.ball_names.length;
      p.ball_names.forEach((name, i) => {
        const angle = (2 * Math.PI * i) / n + frame * 0.03;
        const x = cx + Math.cos(angle) * p.inner_radius * 0.5;
        const y = cy + Math.sin(angle) * p.inner_radius * 0.5;
        ctx.fillStyle = p.ball_colors[i];
        ctx.beginPath();
        ctx.arc(x, y, p.ball_radius, 0, 2 * Math.PI);
        ctx.fill();
        ctx.font = 'bold 56px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`${name} 0`, (W * (i + 1)) / (n + 1), 540);
      });
      if (p.title) {
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 72px Arial';
        ctx.fillText(p.title, cx, 350);
      }
      frame += 1;
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvasRef} width={W} height={H} className="phone" />;
}
