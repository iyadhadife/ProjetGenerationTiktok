import React from 'react';
import { ColorField, NumberField } from './fields.jsx';

export const PLATFORM_DEFAULTS = {
  fps: 30, max_duration: 60, title: '',
  sync: 'tempo', min_beat_interval: 0.4, selectivity: 0.45, sensitivity: 0.07, beat_pulse: true, bar_zoom: true,
  ball_color: '#ffffff', ball_radius: 26, jump_height: 275, spread: 280, trail_length: 14,
  platform_length: 170, start_hue: 200, hue_step: 16, saturation: 0.75,
  particles: 26, shake: 14, flash: true, bounce_sound: false, bounce_volume: -10,
  piano: 'mix', piano_volume: -4, color_by_note: true, show_note_names: true, seed: null,
};

function Check({ label, checked, onChange }) {
  return (
    <label className="field check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

// Réglages du mode « Plateformes » : la balle rebondit sur des plateformes qui apparaissent sur le tempo
export default function PlatformSettings({ params, setParams }) {
  const set = (key) => (value) => setParams((p) => ({ ...p, [key]: value }));

  return (
    <>
      <section>
        <h2>🥁 Rythme</h2>
        <label className="field"><span>Les rebonds suivent</span>
          <select value={params.sync} onChange={(e) => set('sync')(e.target.value)}>
            <option value="tempo">Le tempo (pulsation régulière du morceau)</option>
            <option value="onsets">Les attaques les plus fortes (plus libre)</option>
          </select>
        </label>
        <NumberField label="Écart minimum entre rebonds (s)" hint={params.sync === 'tempo' ? 'rebond tous les 1, 2 ou 4 temps' : 'le temps le plus fort l\'emporte'}
          value={params.min_beat_interval} onChange={set('min_beat_interval')} min={0.2} max={2} step={0.05} />
        {params.sync === 'onsets' && (
          <>
            <NumberField label="Sélectivité" hint="ne garde que les attaques les plus fortes" value={params.selectivity} onChange={set('selectivity')} min={0} max={0.9} step={0.05} />
            <NumberField label="Sensibilité" value={params.sensitivity} onChange={set('sensitivity')} min={0.01} max={0.3} step={0.01} />
          </>
        )}
        <Check label="Le fond pulse sur chaque temps" checked={params.beat_pulse} onChange={set('beat_pulse')} />
        <Check label="Petit zoom au début de chaque mesure" checked={params.bar_zoom} onChange={set('bar_zoom')} />
      </section>

      <section>
        <h2>🎹 Piano</h2>
        <label className="field"><span>🎹 Notes de piano <small>chaque rebond joue la note de la musique</small></span>
          <select value={params.piano} onChange={(e) => set('piano')(e.target.value)}>
            <option value="off">Désactivé</option>
            <option value="mix">Piano + musique</option>
            <option value="solo">Piano seul</option>
          </select>
        </label>
        {params.piano !== 'off' && <NumberField label="Volume du piano (dB)" value={params.piano_volume} onChange={set('piano_volume')} min={-24} max={6} />}
        <Check label="Couleur de la plateforme selon la note" checked={params.color_by_note} onChange={set('color_by_note')} />
        <Check label="Afficher le nom des notes" checked={params.show_note_names} onChange={set('show_note_names')} />
      </section>

      <section>
        <h2>🎬 Vidéo</h2>
        <label className="field"><span>Titre affiché</span>
          <input type="text" maxLength={40} value={params.title} placeholder="Attends le drop…" onChange={(e) => set('title')(e.target.value)} />
        </label>
        <NumberField label="Durée max (s)" hint="coupée à la fin de la musique" value={params.max_duration} onChange={set('max_duration')} min={5} max={180} />
        <label className="field"><span>Images par seconde</span>
          <select value={params.fps} onChange={(e) => set('fps')(Number(e.target.value))}>
            <option value={30}>30 (rendu plus rapide)</option>
            <option value={60}>60 (plus fluide)</option>
          </select>
        </label>
      </section>

      <section>
        <h2>⚪ Balle</h2>
        <ColorField label="Couleur" value={params.ball_color} onChange={set('ball_color')} />
        <NumberField label="Taille" value={params.ball_radius} onChange={set('ball_radius')} min={10} max={50} />
        <NumberField label="Hauteur des sauts (px)" hint="règle la gravité" value={params.jump_height} onChange={set('jump_height')} min={80} max={600} step={5} />
        <NumberField label="Écart horizontal (px)" value={params.spread} onChange={set('spread')} min={80} max={450} step={5} />
        <NumberField label="Longueur de la traînée" value={params.trail_length} onChange={set('trail_length')} min={1} max={40} />
      </section>

      <section>
        <h2>🟪 Plateformes</h2>
        <NumberField label="Longueur" value={params.platform_length} onChange={set('platform_length')} min={60} max={320} step={5} />
        <NumberField label="Teinte de départ (°)" value={params.start_hue} onChange={set('start_hue')} min={0} max={360} />
        <NumberField label="Décalage de teinte par plateforme (°)" hint="0 = une seule couleur" value={params.hue_step} onChange={set('hue_step')} min={0} max={60} />
        <NumberField label="Saturation" value={params.saturation} onChange={set('saturation')} min={0} max={1} step={0.05} />
      </section>

      <section>
        <h2>💥 Impact</h2>
        <NumberField label="Particules" value={params.particles} onChange={set('particles')} min={0} max={80} />
        <NumberField label="Tremblement" value={params.shake} onChange={set('shake')} min={0} max={40} />
        <Check label="Flash à chaque rebond" checked={params.flash} onChange={set('flash')} />
        <Check label="Son de rebond (en plus de la musique)" checked={params.bounce_sound} onChange={set('bounce_sound')} />
        {params.bounce_sound && <NumberField label="Volume du rebond (dB)" value={params.bounce_volume} onChange={set('bounce_volume')} min={-30} max={6} />}
        <label className="field"><span>Graine aléatoire <small>vide = différente à chaque fois</small></span>
          <input type="number" value={params.seed ?? ''} onChange={(e) => set('seed')(e.target.value === '' ? null : Number(e.target.value))} />
        </label>
      </section>
    </>
  );
}
