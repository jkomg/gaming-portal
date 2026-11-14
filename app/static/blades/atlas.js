/* Public locations only. GM plans belong in staff-protected wiki records. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const status = $('status');
  if (!window.L) {
    status.textContent = 'The map library could not load. Read the district guide from the wiki.';
    return;
  }
  const width = 2754, height = 2043;
  const bounds = [[0, 0], [height, width]];
  const map = L.map('map', { crs: L.CRS.Simple, minZoom: -3, maxZoom: 2, scrollWheelZoom: false });
  const overlay = L.imageOverlay(document.body.dataset.image, bounds).addTo(map);
  overlay.on('error', () => { status.textContent = 'The map image could not load. The directory remains available.'; });
  map.fitBounds(bounds);
  $('fit').addEventListener('click', () => map.fitBounds(bounds));
  const layer = L.layerGroup().addTo(map);
  const colors = { Crows: '#d59a63', Lampblacks: '#a0b5cb', 'Red Sashes': '#ef7c83', Bluecoats: '#7ebcdd', Neutral: '#d4c6a3', 'First score': '#d8ba73' };
  let records = [], selected = null;

  function select(site, marker) {
    selected = site.id;
    for (const button of $('directory').children) {
      button.setAttribute('aria-pressed', String(button.dataset.id === selected));
    }
    const title = document.createElement('h2'); title.textContent = site.name;
    const faction = document.createElement('p'); faction.textContent = site.faction + ' · ' + site.provenance;
    const description = document.createElement('p'); description.textContent = site.description;
    const link = document.createElement('a'); link.href = '/blades/wiki/' + site.wiki; link.textContent = 'Read the wiki entry →';
    $('details').replaceChildren(title, faction, description, link);
    map.panTo(marker.getLatLng());
    marker.openTooltip();
  }

  function render() {
    layer.clearLayers();
    $('directory').replaceChildren();
    const filter = $('faction').value;
    const visible = records.filter((s) => filter === 'all' || s.faction === filter);
    if (!visible.some((s) => s.id === selected)) {
      selected = null;
      const note = document.createElement('p'); note.textContent = 'Select a visible site to read its details.';
      $('details').replaceChildren(note);
    }
    for (const site of visible) {
      const label = document.createElement('span'); label.textContent = site.name;
      const marker = L.circleMarker([height * (1 - site.y), width * site.x], {
        radius: 9, color: '#171e24', weight: 2, fillColor: colors[site.faction], fillOpacity: 1,
      }).bindTooltip(label).addTo(layer);
      marker.on('click', () => select(site, marker));
      const button = document.createElement('button'); button.type = 'button'; button.dataset.id = site.id;
      button.setAttribute('aria-pressed', String(selected === site.id));
      const name = document.createElement('span'); name.textContent = site.name;
      const faction = document.createElement('small'); faction.textContent = site.faction;
      button.append(name, faction); button.addEventListener('click', () => select(site, marker));
      $('directory').append(button);
    }
    status.textContent = `${visible.length} known sites. Approximate locations; no territorial borders.`;
    if (selected) {
      // Preserve selection when it remains visible after a filter change.
      $('directory').querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' });
    }
  }
  $('faction').addEventListener('change', render);
  fetch(document.body.dataset.sites).then((response) => {
    if (!response.ok) throw new Error('Unavailable');
    return response.json();
  }).then((data) => { records = data; render(); })
    .catch(() => { status.textContent = 'The site directory could not load. Reload or read the district guide in the wiki.'; });
})();
