export const clone = value => JSON.parse(JSON.stringify(value));
export const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const integer=(n,min,max)=>Number.isInteger(n)&&n>=min&&n<=max;
const text=(s,n=500)=>typeof s==='string'&&s.length<=n;
export function validateState(state,geo) {
  if(!state||state.version!==1)throw Error('Expected a Procyon map version 1 snapshot.');
  for(const s of geo.systems){const v=state.systems?.[s.id];if(!v||!integer(v.heat,0,8)||!integer(v.wanted,0,4)||!text(v.notes))throw Error('Invalid system: '+s.name);}
  const known=new Set(geo.locations.map(l=>l.id));
  if(!Array.isArray(state.markers)||state.markers.length>100)throw Error('At most 100 custom locations are supported.');
  for(const m of state.markers){if(!text(m.id,80)||!/^[a-z0-9-]+$/.test(m.id)||known.has(m.id)||!text(m.name,80)||!m.name.trim()||!geo.systems.some(s=>s.id===m.system)||!Number.isFinite(m.x)||!Number.isFinite(m.y)||m.x<0||m.x>1800||m.y<0||m.y>1150||!text(m.summary)||!text(m.kind,80))throw Error('Invalid custom location');known.add(m.id);}
  if(!Array.isArray(state.presence)||state.presence.length>300)throw Error('Invalid presence list');
  const keys=new Set();
  for(const p of state.presence){const k=p.location+'|'+p.faction;if(!known.has(p.location)||!geo.factions.includes(p.faction)||!['HQ','Presence','Contested'].includes(p.strength)||!text(p.note)||keys.has(k))throw Error('Invalid or duplicate faction presence');keys.add(k);}
  for(const r of geo.routes){const v=state.routes?.[r.id];if(!v||!['open','watched','blocked','sealed'].includes(v.status)||!text(v.notes))throw Error('Invalid route');}
  for(const f of geo.factions)if(!integer(state.factionState?.[f]?.status,-3,3))throw Error('Invalid faction status');
  if(!known.has(state.ship?.location))throw Error('Invalid ship location');
  return clone(state);
}
export function applyOperation(current,op,geo) {
  const s=clone(current);
  if(op.type==='heat'){const v=s.systems[op.system];if(!v)throw Error('Unknown system');const amount=Math.max(0,v.heat+op.delta);v.wanted=Math.min(4,v.wanted+Math.floor(amount/8));v.heat=amount%8;}
  else if(op.type==='system'){const heat=Number(op.heat),wanted=Number(op.wanted);if(!integer(heat,0,8)||!integer(wanted,0,4))throw Error('Invalid Heat or Wanted');s.systems[op.system]={heat:heat%8,wanted:Math.min(4,wanted+Math.floor(heat/8)),notes:String(op.notes)};}
  else if(op.type==='faction'){if(!s.factionState[op.faction])throw Error('Unknown faction');s.factionState[op.faction].status=Number(op.status);}
  else if(op.type==='presence'){s.presence=s.presence.filter(p=>!(p.location===op.location&&p.faction===op.faction));if(!op.remove)s.presence.push({location:op.location,faction:op.faction,strength:op.strength,note:String(op.note||'')});}
  else if(op.type==='route'){s.routes[op.route]={status:op.status,notes:String(op.notes||'')};}
  else if(op.type==='ship'){s.ship.location=op.location;}
  else if(op.type==='marker'){const marker={id:op.id,name:op.name,system:op.system,x:Number(op.x),y:Number(op.y),kind:op.kind||'Crew discovery',summary:op.summary||''};s.markers=s.markers.filter(m=>m.id!==op.id);s.markers.push(marker);}
  else if(op.type==='removeMarker'){if(s.ship.location===op.id)throw Error('Move the ship before removing this location.');s.markers=s.markers.filter(m=>m.id!==op.id);s.presence=s.presence.filter(p=>p.location!==op.id);}
  else throw Error('Unsupported change');
  return validateState(s,geo);
}
export function planRoute(geo,state,start,end) {
  if(start===end)return [start];
  const q=[[start]],seen=new Set([start]);
  while(q.length){const path=q.shift(),at=path.at(-1);for(const r of geo.routes){if(['blocked','sealed'].includes(state.routes[r.id].status))continue;const next=r.a===at?r.b:r.b===at?r.a:null;if(!next||!geo.systems.some(s=>s.id===next)||seen.has(next))continue;const p=[...path,next];if(next===end)return p;seen.add(next);q.push(p);}}
  return null;
}
