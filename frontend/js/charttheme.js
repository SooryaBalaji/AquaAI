let GRID = 'rgba(41,76,98,.12)';
const CHART_COLORS = {
  water: '#59B9EC',
  waterFill: 'rgba(158,220,255,.35)',
  sand: '#FFD166',
  coral: '#FF8FA3',
  violet: '#7056DD',
  outline: '#294C62',
  track: '#E7F8FF'
};

function applyChartTheme() {
  const dark = document.documentElement.dataset.theme === 'dark';
  const css = getComputedStyle(document.documentElement);
  GRID = dark ? 'rgba(255,255,255,.1)' : 'rgba(41,76,98,.12)';
  CHART_COLORS.outline = dark ? '#06101D' : '#294C62';
  CHART_COLORS.track = dark ? '#24405F' : '#E7F8FF';
  CHART_COLORS.waterFill = dark ? 'rgba(89,185,236,.25)' : 'rgba(158,220,255,.35)';
  if (window.Chart) {
    Chart.defaults.color = css.getPropertyValue('--graphite').trim() || '#40506A';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.borderColor = GRID;
  }
}

applyChartTheme();
document.addEventListener('aquaai-theme', () => {
  applyChartTheme();
  if (typeof reloadAllTabs === 'function') reloadAllTabs();
});