function renderTank(el, gallons, limit) {
  const pct = limit > 0 ? Math.min(100, Math.round((gallons / limit) * 100)) : 0;
  const top = 36;
  const bottom = 292;
  const height = bottom - top;
  const level = bottom - (height * pct) / 100;
  const over = limit > 0 && gallons > limit;
  const fill = over ? '#FF8FA3' : '#59B9EC';
  const fillLight = over ? '#FFC2CD' : '#9EDCFF';

  el.innerHTML = `
    <svg viewBox="0 0 320 340" role="img" aria-label="Tank filled to ${pct} percent of today's water budget">
      <defs>
        <clipPath id="tankClip"><rect x="40" y="${top}" width="240" height="${height}" rx="34"/></clipPath>
        <linearGradient id="waterGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="${fillLight}"/><stop offset="1" stop-color="${fill}"/>
        </linearGradient>
      </defs>
      <ellipse cx="160" cy="320" rx="112" ry="12" fill="currentColor" opacity=".16"/>
      <rect x="40" y="${top}" width="240" height="${height}" rx="34" class="tank-empty"/>
      <g clip-path="url(#tankClip)">
        <g class="tank-water" style="transform:translateY(${level - top}px)">
          <g class="tank-wave">
            <path d="M-240 ${top + 8} q30 -14 60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 V${bottom + 20} H-240 Z" fill="url(#waterGrad)" stroke="currentColor" stroke-width="3"/>
          </g>
        </g>
        <rect x="62" y="${top + 20}" width="12" height="150" rx="6" fill="#fff" opacity=".7"/>
      </g>
      <rect x="40" y="${top}" width="240" height="${height}" rx="34" fill="none" stroke="currentColor" stroke-width="4"/>
      <rect x="116" y="14" width="88" height="26" rx="10" fill="#FFD166" stroke="currentColor" stroke-width="4"/>
      <g stroke="currentColor" stroke-width="3" stroke-linecap="round">
        <line x1="262" y1="${top + 50}" x2="280" y2="${top + 50}"/>
        <line x1="262" y1="${top + 112}" x2="280" y2="${top + 112}"/>
        <line x1="262" y1="${top + 174}" x2="280" y2="${top + 174}"/>
      </g>
      <g class="tank-drop">
        <path d="M160 74 C146 94 140 104 140 114 C140 126 149 134 160 134 C171 134 180 126 180 114 C180 104 174 94 160 74 Z" fill="#fff" stroke="currentColor" stroke-width="3.5" opacity=".92"/>
        <path d="M150 112 C150 118 154 122 158 123" stroke="${fill}" stroke-width="3.5" fill="none" stroke-linecap="round"/>
      </g>
    </svg>`;
}