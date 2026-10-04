import React from 'react';

export function NumberField({ label, hint, value, onChange, min, max, step = 1 }) {
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

export function ColorField({ label, value, onChange }) {
  return (
    <label className="field color">
      <span>{label}</span>
      <input type="color" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
