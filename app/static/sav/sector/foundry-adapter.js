import {clone,validateState} from './sector-core.js';
export function foundryAdapter(host,geography) {
  const {game,Hooks}=host,geo=geography;
  // Foundry checks object prototypes; serialize iframe data into the host realm.
  const native=value=>host.JSON.parse(JSON.stringify(value));
  const key=d=>d.getFlag('world','quietOrbit.key');
  const universe=game.actors.find(a=>key(a)==='actor:universe'),factions=game.actors.find(a=>key(a)==='actor:factions');
  if(!universe||!factions)throw Error('Quiet Orbit’s Universe and Faction Status actors are required.');
  const normal=s=>s.toLowerCase().replace(/[^a-z0-9]/g,'');
  const systemItem=id=>universe.items.find(i=>i.type==='star_system'&&normal(i.name)===normal(geo.systems.find(s=>s.id===id)?.name||''));
  const factionItem=name=>factions.items.find(i=>i.type==='faction'&&normal(i.name)===normal(name));
  const value=v=>Array.isArray(v)?Math.max(0,...v.map(Number)):Number(v)||0;
  const ownsTrackers=()=>universe.testUserPermission(game.user,'OWNER')&&factions.testUserPermission(game.user,'OWNER');
  const canEdit=game.user.isGM||ownsTrackers();
  async function load(){
    const s=clone(geo.defaultState),overlay=universe.getFlag('world','procyonMap')||{};
    for(const field of ['presence','markers','routes','ship'])if(overlay[field])s[field]=clone(overlay[field]);
    for(const system of geo.systems){const item=systemItem(system.id);if(!item)throw Error('Missing native system '+system.name);s.systems[system.id]={heat:value(item.system.heat.value),wanted:value(item.system.wanted.value),notes:overlay.systemNotes?.[system.id]||''};}
    for(const f of geo.factions){const item=factionItem(f);if(!item)throw Error('Missing native faction '+f);s.factionState[f]={status:value(item.system.status.value)-4};}
    return validateState(s,geo);
  }
  async function save(next,op){
    if(!canEdit||!(game.user.isGM||ownsTrackers()))throw Error('Only the GM or an owner of both campaign trackers can edit.');
    validateState(next,geo);
    if(['heat','system','import'].includes(op.type)){
      const ids=op.type==='import'?geo.systems.map(s=>s.id):[op.system];
      await universe.updateEmbeddedDocuments('Item',native(ids.map(id=>({_id:systemItem(id).id,'system.heat.value':[next.systems[id].heat],'system.wanted.value':[next.systems[id].wanted]}))));
    }
    if(['faction','import'].includes(op.type)){
      const names=op.type==='import'?geo.factions:[op.faction];
      await factions.updateEmbeddedDocuments('Item',native(names.map(name=>({_id:factionItem(name).id,'system.status.value':next.factionState[name].status+4}))));
    }
    const changes={};
    if(op.type==='import')changes['flags.world.procyonMap']={presence:next.presence,markers:next.markers,routes:next.routes,ship:next.ship,systemNotes:Object.fromEntries(Object.entries(next.systems).map(([id,s])=>[id,s.notes]))};
    else {
      if(op.type==='system')changes['flags.world.procyonMap.systemNotes.'+op.system]=next.systems[op.system].notes;
      if(['presence','removeMarker'].includes(op.type))changes['flags.world.procyonMap.presence']=next.presence;
      if(['marker','removeMarker'].includes(op.type))changes['flags.world.procyonMap.markers']=next.markers;
      if(op.type==='route')changes['flags.world.procyonMap.routes.'+op.route]=next.routes[op.route];
      if(op.type==='ship')changes['flags.world.procyonMap.ship']=next.ship;
    }
    // Seed untouched overlay sections only once, without ever copying/resetting native trackers.
    const overlay=universe.getFlag('world','procyonMap')||{};
    for(const k of ['presence','markers','routes','ship'])if(!overlay[k]&&!Object.keys(changes).some(path=>path==='flags.world.procyonMap'||path==='flags.world.procyonMap.'+k||path.startsWith('flags.world.procyonMap.'+k+'.')))changes['flags.world.procyonMap.'+k]=next[k];
    if(Object.keys(changes).length)await universe.update(native(changes));
  }
  return {geography:geo,canEdit,load,save,status:canEdit?'Live Foundry state · GM controls available':'Live Foundry state · player view',
    footer:'Heat, Wanted, and relationships use the campaign’s existing Foundry records.',
    subscribe(callback){const ids=[];for(const event of ['updateActor','updateItem','createItem','deleteItem'])ids.push([event,Hooks.on(event,doc=>{if(doc.id===universe.id||doc.id===factions.id||doc.parent?.id===universe.id||doc.parent?.id===factions.id)callback();})]);return ()=>ids.forEach(([e,id])=>Hooks.off(e,id));},
    openSystem(id){systemItem(id)?.sheet.render(true);},
    openFaction(name){factionItem(name)?.sheet.render(true);},
    openLocation(id){const l=[...geo.locations,...(universe.getFlag('world','procyonMap.markers')||[])].find(l=>l.id===id);const item=universe.items.find(i=>i.type==='planet'&&normal(i.name)===normal(l?.name||''));(item||systemItem(l?.system))?.sheet.render(true);}
  };
}
