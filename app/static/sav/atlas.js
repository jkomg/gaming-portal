'use strict';
(() => {
  const filter = document.getElementById('faction');
  const controls = [...document.querySelectorAll('[data-site]')];
  const details = [...document.querySelectorAll('[data-detail]')];
  const directory = [...document.querySelectorAll('#directory [data-site]')];
  let selected = null;
  function select(id) {
    selected = id;
    controls.forEach(control => control.setAttribute('aria-pressed', String(control.dataset.site === id)));
    details.forEach(detail => { detail.hidden = detail.dataset.detail !== id; });
  }
  controls.forEach(control => {
    control.addEventListener('click', () => select(control.dataset.site));
    if (control.tagName.toLowerCase() === 'g') {
      control.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          select(control.dataset.site);
        }
      });
    }
  });
  filter.addEventListener('change', () => {
    controls.forEach(control => {
      const visible = filter.value === 'all' || control.dataset.group === filter.value;
      // SVG has no native hidden layout behavior across all supported browsers.
      control.style.display = visible ? '' : 'none';
    });
    const visible = directory.filter(control => control.style.display !== 'none');
    if (!visible.some(control => control.dataset.site === selected)) {
      select(visible[0]?.dataset.site || null);
    }
    document.getElementById('status').textContent = `${visible.length} known sites · all within Rin`;
  });
  select(directory[0]?.dataset.site || null);
})();
