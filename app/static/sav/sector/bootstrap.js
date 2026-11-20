import {mountSectorMap} from './sector-map.js';
import {clone} from './sector-core.js';
import {foundryAdapter} from './foundry-adapter.js';
const root=document.querySelector('#sector-app');
try {
  const config=JSON.parse(document.querySelector('#sector-config')?.textContent||'{}');
  const geo=await fetch(config.geography||new URL('./sector.json',import.meta.url)).then(r=>{if(!r.ok)throw Error('Sector geography is unavailable.');return r.json();});
  let host=null;
  try {if(parent!==window&&parent.game?.ready)host=parent;}catch{/* A cross-origin embed never gets direct campaign access. */}
  let adapter;
  if(host)adapter=foundryAdapter(host,geo);
  else if(config.stateUrl){
    let revision=0,current=clone(geo.defaultState);
    const load=async()=>current;
    const response=await fetch(config.stateUrl);if(!response.ok)throw Error('Sector snapshot unavailable.');
    const saved=await response.json();revision=saved.revision;current=saved.state;
    adapter={geography:geo,canEdit:!!config.canEdit,load,
      status:saved.updatedAt?'Wiki snapshot · '+new Date(saved.updatedAt).toLocaleString():'Wiki reference · initial campaign state',
      footer:'The wiki stores a published snapshot. Import a Foundry export to update it; it does not poll your private host.',
      async save(next){const r=await fetch(config.stateUrl,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRFToken':config.csrfToken},body:JSON.stringify({revision,state:next})});const result=await r.json();if(!r.ok)throw Error(result.error||'Could not save snapshot.');revision=result.revision;current=result.state;},
      openSystem:()=>window.open('/sav/wiki/atlas-notes','_blank','noopener'),openLocation:()=>window.open('/sav/wiki/atlas-notes','_blank','noopener'),openFaction:()=>window.open('/sav/wiki/people-and-factions','_blank','noopener')};
  } else adapter={geography:geo,canEdit:false,load:async()=>clone(geo.defaultState),status:'Reference view · open the Sector Map macro in Foundry for live state',footer:'This standalone view is a reference. In-game edits require the Foundry Sector Map macro.'};
  window.sectorMap=await mountSectorMap(root,adapter);
} catch(error){root.textContent=error.message;root.className='load-error';console.error(error);}
