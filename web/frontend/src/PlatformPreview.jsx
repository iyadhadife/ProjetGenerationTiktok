import React, { useEffect, useRef } from 'react';

const W = 1080;
const H = 1920;

const hsl = (hue, sat, light = 60) => `hsl(${hue}, ${Math.round(sat * 100)}%, ${light}%)`;

// Aperçu animé du mode Plateformes : la balle saute de plateforme en plateforme à un rythme fixe
// (le rendu final suit le tempo réel de la musique)
export default function PlatformPreview({ params }) {
  const canvasRef = useRef(null);
  const paramsRef = useRef(params);
  paramsRef.current = params;

  useEffect(() => {
    const ctx = canvasRef.current.getContext('2d');
    const period = 36; // images entre deux rebonds dans l'aperçu
    let frame = 0;
    let raf;
    const draw = () => {
      const p = paramsRef.current;
      const k = Math.floor(frame / period);
      const t = (frame % period) / period;
      // Points de chute en zigzag ; la caméra reste centrée sur le saut en cours
      const point = (i) => ({ x: (i % 2 ? 1 : -1) * p.spread / 2, y: i * 160 });
      const a = point(k);
      const b = point(k + 1);
      const ball = { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t - 4 * p.jump_height * t * (1 - t) };
      const cam = { x: (a.x + b.x) / 2, y: a.y + 80 };
      const hit = Math.max(0, 1 - t * 4);
      const hue = p.start_hue + p.hue_step * k;

      ctx.fillStyle = hsl(hue, 0.6, 6 + (p.flash ? 8 * hit : 0));
      ctx.fillRect(0, 0, W, H);
      ctx.save();
      const zoom = p.bar_zoom && k % 4 === 0 ? 1 + 0.06 * hit : 1;
      ctx.translate(W / 2, H / 2);
      ctx.scale(zoom, zoom);
      ctx.translate(-cam.x + (Math.random() - 0.5) * p.shake * hit, -cam.y);

      for (let i = k - 1; i <= k + 2; i += 1) {
        const q = point(i);
        ctx.strokeStyle = i === k && hit > 0.6 ? '#fff' : hsl(p.start_hue + p.hue_step * i, p.saturation);
        ctx.globalAlpha = i < k ? 0.35 : 1;
        ctx.lineWidth = 14;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(q.x - p.platform_length / 2, q.y + p.ball_radius + 7);
        ctx.lineTo(q.x + p.platform_length / 2, q.y + p.ball_radius + 7);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      if (hit > 0) {
        ctx.strokeStyle = hsl(hue, p.saturation);
        ctx.globalAlpha = hit;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.arc(a.x, a.y, 30 + (1 - hit) * 180, 0, 2 * Math.PI);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      for (let i = p.trail_length; i > 0; i -= 1) {
        const tt = Math.max(0, t - i * 0.012);
        const tx = a.x + (b.x - a.x) * tt;
        const ty = a.y + (b.y - a.y) * tt - 4 * p.jump_height * tt * (1 - tt);
        ctx.globalAlpha = 0.5 * (1 - i / p.trail_length);
        ctx.fillStyle = p.ball_color;
        ctx.beginPath();
        ctx.arc(tx, ty, p.ball_radius * (1 - i / (p.trail_length + 1)), 0, 2 * Math.PI);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      ctx.fillStyle = p.ball_color;
      ctx.shadowColor = p.ball_color;
      ctx.shadowBlur = 40;
      ctx.beginPath();
      ctx.arc(ball.x, ball.y, p.ball_radius, 0, 2 * Math.PI);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();

      if (p.title) {
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 72px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(p.title, W / 2, 280);
      }
      frame += 1;
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvasRef} width={W} height={H} className="phone" />;
}
