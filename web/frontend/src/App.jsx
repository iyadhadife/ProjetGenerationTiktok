import React, { useEffect, useMemo, useRef, useState } from 'react';
import Preview from './Preview.jsx';
import PlatformPreview from './PlatformPreview.jsx';
import { ColorField, NumberField } from './fields.jsx';
import PlatformSettings, { PLATFORM_DEFAULTS } from './PlatformSettings.jsx';

const FALLBACK_DEFAULTS = {
  fps: 60, max_duration: 60, title: '', background: '#0f0f14',
  arc_count: 20, arc_spacing: 25, inner_radius: 200, gap_degrees: 54, rotation_speed: 1.2,
  arc_color_start: '#ff0000', arc_color_end: '#280000', arc_thickness: 7,
  ball_names: ['USA', 'China'], ball_colors: ['#ffffff', '#ffffff'], ball_radius: 20, gravity: 0.6,
  beats_per_break: 4, min_beat_interval: 0.35, selectivity: 0.4, sensitivity: 0.07, bounce_sound: true, bounce_volume: -6, piano: 'off', piano_voicing: 'chord', piano_volume: -4, seed: null,
};

export default function App() {
  const [mode, setMode] = useState('arcs');
  const [params, setParams] = useState(FALLBACK_DEFAULTS);
  const [platformParams, setPlatformParams] = useState(PLATFORM_DEFAULTS);
  const [music, setMusic] = useState(null);
  const [score, setScore] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const pollRef = useRef(null);
  const musicUrl = useMemo(() => (music ? URL.createObjectURL(music) : null), [music]);
  useEffect(() => () => musicUrl && URL.revokeObjectURL(musicUrl), [musicUrl]);

  useEffect(() => {
    fetch('/api/defaults').then((r) => (r.ok ? r.json() : null)).then((d) => {
      if (d?.arcs) setParams(d.arcs);
      if (d?.platforms) setPlatformParams(d.platforms);
    }).catch(() => {});
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
    if (mode === 'platforms' && score) form.append('score', score);
    form.append('mode', mode);
    form.append('params', JSON.stringify(mode === 'arcs' ? params : platformParams));
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
        <p>Importe une musique : chaque rebond tombe sur le rythme, et la vidéo 1080×1920 se génère automatiquement.</p>
        <nav className="tabs">
          <button type="button" className={mode === 'arcs' ? 'active' : ''} onClick={() => setMode('arcs')}>⭕ Arcs</button>
          <button type="button" className={mode === 'platforms' ? 'active' : ''} onClick={() => setMode('platforms')}>🟪 Plateformes</button>
        </nav>
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
            {mode === 'platforms' && (
              <label className="field">
                <span>Partition MIDI (facultatif)</span>
                <input type="file" accept=".mid,.midi,audio/midi" onChange={(e) => setScore(e.target.files[0] || null)} />
                <small>{score ? `${score.name} : calée automatiquement sur la musique, utilisée si elle correspond`
                  : 'Si tu as la partition du morceau, ses notes exactes remplacent la transcription automatique'}</small>
                {score && <button type="button" onClick={() => setScore(null)}>Retirer la partition</button>}
              </label>
            )}
          </section>

          {mode === 'platforms' ? (
            <PlatformSettings params={platformParams} setParams={setPlatformParams} />
          ) : (<>
          <section>
            <h2>🥁 Synchronisation</h2>
            <NumberField label="Sensibilité" hint="plus bas = plus de rebonds" value={params.sensitivity} onChange={set('sensitivity')} min={0.01} max={0.3} step={0.01} />
            <NumberField label="Sélectivité" hint="ne garde que les temps les plus forts" value={params.selectivity} onChange={set('selectivity')} min={0} max={0.9} step={0.05} />
            <NumberField label="Écart minimum entre rebonds (s)" hint="le temps le plus fort l'emporte" value={params.min_beat_interval} onChange={set('min_beat_interval')} min={0.1} max={1.5} step={0.05} />
            <NumberField label="Un arc détruit tous les N rebonds" hint="en moyenne, tirage au sort" value={params.beats_per_break} onChange={set('beats_per_break')} min={1} max={12} />
            <label className="field check">
              <input type="checkbox" checked={params.bounce_sound} onChange={(e) => set('bounce_sound')(e.target.checked)} />
              <span>Son de rebond</span>
            </label>
            {params.bounce_sound && <NumberField label="Volume du rebond (dB)" value={params.bounce_volume} onChange={set('bounce_volume')} min={-30} max={6} />}
            <label className="field"><span>🎹 Notes de piano <small>chaque rebond joue la note de la musique</small></span>
              <select value={params.piano} onChange={(e) => set('piano')(e.target.value)}>
                <option value="off">Désactivé</option>
                <option value="solo">Piano seul (sans la musique)</option>
                <option value="mix">Piano + musique</option>
              </select>
            </label>
            {params.piano !== 'off' && (
                  <label className="field"><span>Le piano joue</span>
                    <select value={params.piano_voicing} onChange={(e) => set('piano_voicing')(e.target.value)}>
                      <option value="chord">Les accords détectés (+ basse)</option>
                      <option value="note">La note dominante seule</option>
                    </select>
                  </label>
                )}
            {params.piano !== 'off' && <NumberField label="Volume du piano (dB)" value={params.piano_volume} onChange={set('piano_volume')} min={-24} max={6} />}
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

          </>)}

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
                  {job.result.duration.toFixed(1)} s · {job.result.tempo ? `${job.result.tempo} BPM · ` : ''}
                  {job.result.bounces} rebonds
                  {Object.keys(job.result.scores || {}).length > 0 && ` · ${Object.entries(job.result.scores).map(([n, sc]) => `${n} ${sc}`).join(' – ')}`}
                </p>
              )}
            </>
          ) : (
            <>
              {mode === 'arcs' ? <Preview params={params} /> : <PlatformPreview params={platformParams} />}
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
