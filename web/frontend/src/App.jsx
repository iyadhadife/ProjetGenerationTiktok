import React, { useEffect, useMemo, useRef, useState } from 'react';
import Preview from './Preview.jsx';

const FALLBACK_DEFAULTS = {
  fps: 60, max_duration: 60, title: '', background: '#0f0f14',
  arc_count: 20, arc_spacing: 25, inner_radius: 200, gap_degrees: 54, rotation_speed: 1.2,
  arc_color_start: '#ff0000', arc_color_end: '#280000', arc_thickness: 7,
  ball_names: ['USA', 'China'], ball_colors: ['#ffffff', '#ffffff'], ball_radius: 20, gravity: 0.6,
  beats_per_break: 4, min_beat_interval: 0.25, sensitivity: 0.07, bounce_sound: true, bounce_volume: -6, seed: null,
};

function NumberField({ label, hint, value, onChange, min, max, step = 1 }) {
  return (
    <label className="field">
      <span>{label}{hint && <small>{hint}</small>}</span>
      <div className="range">
        <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
        <input type="number" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      </div>
    </label>
  );
}

function ColorField({ label, value, onChange }) {
  return (
    <label className="field color">
      <span>{label}</span>
      <input type="color" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export default function App() {
  const [params, setParams] = useState(FALLBACK_DEFAULTS);
  const [music, setMusic] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const pollRef = useRef(null);
  const musicUrl = useMemo(() => (music ? URL.createObjectURL(music) : null), [music]);
  useEffect(() => () => musicUrl && URL.revokeObjectURL(musicUrl), [musicUrl]);

  useEffect(() => {
    fetch('/api/defaults').then((r) => (r.ok ? r.json() : null)).then((d) => d && setParams(d)).catch(() => {});
    return () => clearInterval(pollRef.current);
  }, []);

  const set = (key) => (value) => setParams((p) => ({ ...p, [key]: value }));

  const setBall = (index, key, value) => setParams((p) => {
    const list = [...p[key]];
    list[index] = value;
    return { ...p, [key]: list };
  });

  const setBallCount = (count) => setParams((p) => ({
    ...p,
    ball_names: Array.from({ length: count }, (_, i) => p.ball_names[i] ?? `Balle ${i + 1}`),
    ball_colors: Array.from({ length: count }, (_, i) => p.ball_colors[i] ?? '#ffffff'),
  }));

  const pickFile = (file) => {
    if (!file) return;
    if (!file.type.startsWith('audio/') && !/\.(mp3|wav|ogg|flac|m4a|aac)$/i.test(file.name)) {
      setError('Choisis un fichier audio (mp3, wav, ogg, flac, m4a).');
      return;
    }
    setError('');
    setMusic(file);
  };

  const poll = (id) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const res = await fetch(`/api/jobs/${id}`);
      const data = await res.json();
      setJob(data);
      if (data.status === 'done' || data.status === 'error' || !res.ok) clearInterval(pollRef.current);
    }, 1000);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!music) { setError('Ajoute d\'abord une musique.'); return; }
    setError('');
    const form = new FormData();
    form.append('music', music);
    form.append('params', JSON.stringify(params));
    const res = await fetch('/api/render', { method: 'POST', body: form });
    const data = await res.json().catch(() => ({ error: `Erreur ${res.status}` }));
    if (!res.ok) { setError(data.error); return; }
    setJob({ id: data.id, status: 'queued', progress: 0, logs: [] });
    poll(data.id);
  };

  const busy = job && (job.status === 'queued' || job.status === 'running');

  return (
    <div className="app">
      <header>
        <h1>Générateur TikTok</h1>
        <p>Importe une musique : chaque rebond tombe sur un temps fort, et la vidéo 1080×1920 se génère automatiquement.</p>
      </header>

      <main>
        <form onSubmit={submit} className="panel settings">
          <section>
            <h2>🎵 Musique</h2>
            <label
              className={`dropzone ${dragging ? 'dragging' : ''} ${music ? 'filled' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]); }}
            >
              <input type="file" accept="audio/*" onChange={(e) => pickFile(e.target.files[0])} hidden />
              {music ? <><strong>{music.name}</strong><small>Clique pour changer</small></>
                : <><strong>Glisse ta musique ici</strong><small>ou clique pour choisir (mp3, wav, ogg, flac, m4a – 50 Mo max)</small></>}
            </label>
            {musicUrl && <audio controls src={musicUrl} />}
          </section>

          <section>
            <h2>🥁 Synchronisation</h2>
            <NumberField label="Sensibilité" hint="plus bas = plus de rebonds" value={params.sensitivity} onChange={set('sensitivity')} min={0.01} max={0.3} step={0.01} />
            <NumberField label="Écart minimum entre rebonds (s)" value={params.min_beat_interval} onChange={set('min_beat_interval')} min={0.1} max={1.5} step={0.05} />
            <NumberField label="Un arc détruit tous les N rebonds" hint="en moyenne, tirage au sort" value={params.beats_per_break} onChange={set('beats_per_break')} min={1} max={12} />
            <label className="field check">
              <input type="checkbox" checked={params.bounce_sound} onChange={(e) => set('bounce_sound')(e.target.checked)} />
              <span>Son de rebond</span>
            </label>
            {params.bounce_sound && <NumberField label="Volume du rebond (dB)" value={params.bounce_volume} onChange={set('bounce_volume')} min={-30} max={6} />}
          </section>

          <section>
            <h2>🎬 Vidéo</h2>
            <label className="field"><span>Titre affiché</span>
              <input type="text" maxLength={40} value={params.title} placeholder="Qui va gagner ?" onChange={(e) => set('title')(e.target.value)} />
            </label>
            <NumberField label="Durée max (s)" hint="coupée à la fin de la musique" value={params.max_duration} onChange={set('max_duration')} min={5} max={180} />
            <label className="field"><span>Images par seconde</span>
              <select value={params.fps} onChange={(e) => set('fps')(Number(e.target.value))}>
                <option value={30}>30 (rendu plus rapide)</option>
                <option value={60}>60 (plus fluide)</option>
              </select>
            </label>
            <ColorField label="Fond" value={params.background} onChange={set('background')} />
          </section>

          <section>
            <h2>⭕ Arcs</h2>
            <NumberField label="Nombre d'arcs" value={params.arc_count} onChange={set('arc_count')} min={1} max={40} />
            <NumberField label="Rayon intérieur" value={params.inner_radius} onChange={set('inner_radius')} min={100} max={400} step={5} />
            <NumberField label="Espacement" value={params.arc_spacing} onChange={set('arc_spacing')} min={10} max={60} />
            <NumberField label="Ouverture (°)" value={params.gap_degrees} onChange={set('gap_degrees')} min={20} max={120} />
            <NumberField label="Vitesse de rotation (°/image)" value={params.rotation_speed} onChange={set('rotation_speed')} min={0} max={5} step={0.1} />
            <NumberField label="Épaisseur" value={params.arc_thickness} onChange={set('arc_thickness')} min={2} max={20} />
            <div className="row">
              <ColorField label="Couleur intérieure" value={params.arc_color_start} onChange={set('arc_color_start')} />
              <ColorField label="Couleur extérieure" value={params.arc_color_end} onChange={set('arc_color_end')} />
            </div>
          </section>

          <section>
            <h2>⚪ Balles</h2>
            <label className="field"><span>Nombre de balles</span>
              <select value={params.ball_names.length} onChange={(e) => setBallCount(Number(e.target.value))}>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            {params.ball_names.map((name, i) => (
              <div className="row ball" key={i}>
                <input type="text" maxLength={16} value={name} onChange={(e) => setBall(i, 'ball_names', e.target.value)} />
                <input type="color" value={params.ball_colors[i]} onChange={(e) => setBall(i, 'ball_colors', e.target.value)} />
              </div>
            ))}
            <NumberField label="Taille" value={params.ball_radius} onChange={set('ball_radius')} min={8} max={40} />
            <NumberField label="Gravité" value={params.gravity} onChange={set('gravity')} min={0} max={2} step={0.05} />
            <label className="field"><span>Graine aléatoire <small>vide = différente à chaque fois</small></span>
              <input type="number" value={params.seed ?? ''} onChange={(e) => set('seed')(e.target.value === '' ? null : Number(e.target.value))} />
            </label>
          </section>

          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? 'Génération en cours…' : '🚀 Générer la vidéo'}</button>
        </form>

        <div className="panel output">
          {job?.status === 'done' ? (
            <>
              <video key={job.id} src={`/api/jobs/${job.id}/video`} controls autoPlay className="phone" />
              <a className="button" href={`/api/jobs/${job.id}/video?download=1`}>⬇️ Télécharger le MP4</a>
              {job.result && (
                <p className="stats">
                  {job.result.duration.toFixed(1)} s · {job.result.beats} temps forts · {job.result.bounces} rebonds ·{' '}
                  {Object.entries(job.result.scores).map(([n, s]) => `${n} ${s}`).join(' – ')}
                </p>
              )}
            </>
          ) : (
            <>
              <Preview params={params} />
              <p className="caption">Aperçu des réglages (la vidéo finale suit le rythme de ta musique)</p>
            </>
          )}

          {busy && (
            <div className="progress">
              <div className="bar"><div style={{ width: `${Math.round((job.progress || 0) * 100)}%` }} /></div>
              <p>
                {job.status === 'queued'
                  ? `En attente${job.queue_position ? ` (position ${job.queue_position})` : ''}…`
                  : `${job.logs?.at(-1) ?? 'Démarrage…'} ${Math.round((job.progress || 0) * 100)} %`}
              </p>
            </div>
          )}
          {job?.status === 'error' && <p className="error">Le rendu a échoué : {job.error}</p>}
        </div>
      </main>
    </div>
  );
}
