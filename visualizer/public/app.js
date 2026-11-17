import {Renderer, formatNumber} from './graph.js';
const $ = id => document.getElementById(id);
let frame=null, graph=null, revision=null, preview=false, paused=false, pinned=null, selectedStream='', generation=0;
const renderer=new Renderer($('network'),$('labels'),(mode,reason)=>{
  $('renderer').textContent=mode; $('renderer').title=reason||'Draws only when a sample or the view changes';
});
await renderer.init(new URLSearchParams(location.search).has('canvas2d'));
const text=(id,value)=>$(id).textContent=value;
const friendly=label=>String(label).replaceAll('_',' ');
const labelFor=(layer,index)=>friendly(graph?.layers.find(l=>l.id===layer)?.labels?.[index]??`${layer} ${index}`);
function element(tag,className,content) {const el=document.createElement(tag);if(className)el.className=className;if(content!==undefined)el.textContent=content;return el;}

function showStatus(status, detail) {
  $('status').className=`badge ${status}`;text('status',status==='waiting'?'WAITING FOR WORKER':status==='preview'?'SYNTHETIC PREVIEW':status.toUpperCase());
  text('connection-detail',detail);
}
function resetView() {
  generation++;
  frame=null;graph=null;revision=null;pinned=null;renderer.graph=null;renderer.layout=null;renderer.frame=null;renderer.focus=null;
  renderer.revision=null;renderer.stream=null;
  renderer.draw();$('empty').hidden=false;$('probabilities').replaceChildren();$('node-select').replaceChildren(new Option('Select a node…',''));
  for(const id of ['game','worker','parameters','phase','value','revision','age'])text(id,'—');
  text('architecture','Awaiting model');text('decision','Awaiting a decision');text('decision-sub','The actual sampled action appears here.');
  text('footer-state','Waiting for telemetry');
  $('inspector').replaceChildren(element('p','small','Select a node to inspect its actual value.'));$('unpin').hidden=true;
}
function setMode(isPreview) {
  preview=isPreview;selectedStream='';$('stream').value='';resetView();
  showStatus('waiting',preview?'Looking for the synthetic stream':'Auto-attach is armed');
  $('live').classList.toggle('active',!preview);$('preview').classList.toggle('active',preview);
  $('preview-banner').hidden=!preview;
  $('empty').querySelector('h2').textContent=preview?'Waiting for a preview stream':'Waiting for a policy worker';
  $('empty').querySelector('p').textContent=preview?'Preview uses a real, separate PyTorch network fed synthetic observations. It never connects to the game.':'The first worker with the observer enabled will connect automatically. Your training keeps running independently.';
  $('empty').querySelector('span').textContent=preview?'Start with: .\\visualizer\\start.ps1 -Preview':'Observer integration is required on the next training launch.';
}
function inspect(node) {
  if(!node||!frame)return;
  const box=$('inspector');box.replaceChildren(element('div','inspect-title',friendly(node.label)),element('div','small',`${node.layer} · unit ${node.index}`),element('div','inspect-value',formatNumber(frame.values?.[node.layer]?.[node.index])));
  const probability=frame.probabilities?.[node.layer]?.[node.index];
  if(probability!==undefined)box.append(element('div','small',`${(probability*100).toFixed(2)}% policy probability${frame.selected?.[node.layer]===node.index?' · sampled action':''}`));
  const incoming=(graph.edges||[]).filter(e=>e.to===node.id).sort((a,b)=>Math.abs(b.weight)-Math.abs(a.weight)).slice(0,4);
  if(incoming.length)box.append(element('p','small','Strongest displayed incoming weights'));
  for(const edge of incoming){const row=element('div','incoming');row.append(element('span','',edge.from),element('span','',formatNumber(edge.weight)));box.append(row);}
  if(incoming.some(e=>e.kind==='gate-rms'))box.append(element('p','small','GRU connections show unsigned RMS across three gate weights. They are summaries, not individual synapses.'));
}
function updateFrame(next) {
  if(next.graph){graph=next.graph;revision=next.model_revision;}
  if(!graph)return;
  const changed=frame?.stream!==next.stream||frame?.model_revision!==next.model_revision;
  frame={...next,graph};renderer.setFrame(frame);$('empty').hidden=true;
  text('game',preview?'Synthetic inputs':`PID ${frame.game_pid}`);
  text('worker',`${frame.worker_pid} / ${frame.episode||'—'}`);
  text('parameters',graph.parameters.toLocaleString());text('phase',friendly(frame.phase).toUpperCase());
  const inputs=graph.layers.find(l=>l.kind==='input'),hidden=graph.layers.find(l=>l.kind==='gru'),heads=graph.layers.filter(l=>['policy','value'].includes(l.kind));
  text('architecture',`${inputs.size} → GRU ${hidden.size} → ${heads.map(l=>l.size).join(' / ')}`);
  text('revision',frame.model_revision.slice(0,10));text('graph-note',`${graph.edge_note} Brightness is normalized per layer.`);
  const actionHead=heads.find(l=>l.kind==='policy'),cellHead=heads.find(l=>l.id==='hc');
  const action=frame.selected?.[actionHead?.id],cell=frame.selected?.[cellHead?.id];
  text('decision',action===undefined?'No sampled action':labelFor(actionHead.id,action));
  const cellRelevant=action!==undefined && !['wait','ready'].includes(actionHead.labels?.[action]);
  text('decision-sub',cell!==undefined?`${labelFor(cellHead.id,cell)}${cellRelevant?'':' · unused for this action'}`:'Observed from the worker’s actual sample');
  $('probabilities').replaceChildren();
  const probabilities=frame.probabilities?.[actionHead?.id]||[];
  const ranked=probabilities.map((p,i)=>({p,i})).sort((a,b)=>b.p-a.p).slice(0,4);
  if(action!==undefined && probabilities[action]!==undefined && !ranked.some(r=>r.i===action))ranked.push({p:probabilities[action],i:action});
  for(const {p,i} of ranked) {const row=element('div',`prob-row ${i===action?'chosen':''}`),label=element('div','prob-label'),track=element('div','prob-track'),fill=element('div','prob-fill');
    label.append(element('span','',`${i===action?'↳ ':''}${labelFor(actionHead.id,i)}`),element('span','',`${(p*100).toFixed(1)}%`));fill.style.width=`${Math.max(0,Math.min(100,p*100))}%`;track.append(fill);row.append(label,track);$('probabilities').append(row);}
  const val=heads.find(l=>l.kind==='value');text('value',formatNumber(frame.values?.[val?.id]?.[0]));
  if(changed){const options=[new Option('Select a node…',''),...renderer.layout.nodes.map(n=>new Option(`${n.layer} / ${friendly(n.label)}`,n.id))];$('node-select').replaceChildren(...options);if(pinned&&!renderer.layout.byId.has(pinned))pinned=null;$('node-select').value=pinned||'';}
  if(pinned)inspect(renderer.layout.byId.get(pinned));
  text('footer-state',`${preview?'Synthetic inference':'Observed inference'} · sample ${frame.sequence} · ${renderer.layout.nodes.length} nodes`);
}
async function poll() {
  const requestedGeneration=generation;
  try {
    const args=new URLSearchParams();if(preview)args.set('preview','1');if(selectedStream)args.set('stream',selectedStream);if(revision)args.set('revision',revision);
    const response=await fetch(`/api/state?${args}`,{signal:AbortSignal.timeout(4000)});if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const data=await response.json();
    if(requestedGeneration!==generation){setTimeout(poll,0);return;}
    const options=[new Option('Automatic attachment',''),...data.streams.map(s=>new Option(`Game ${s.game_pid} · worker ${s.worker_pid}${s.age>15?' · stale':''}`,s.id))];
    if(selectedStream&&!data.streams.some(s=>s.id===selectedStream))options.push(new Option('Selected worker unavailable',selectedStream));
    const optionSignature=options.map(o=>`${o.value}:${o.text}`).join('|');
    if($('stream').dataset.signature!==optionSignature){$('stream').replaceChildren(...options);$('stream').dataset.signature=optionSignature;}
    $('stream').value=selectedStream;
    const detail=data.status==='live'?`Following game ${data.frame.game_pid}`:data.status==='stale'?'No fresh sample · inference may be idle':data.status==='preview'?'Separate model · synthetic observations':data.status==='error'?data.frame.error:'Auto-attach is armed';
    showStatus(data.status,detail);text('age',data.age===undefined?'—':`${data.age.toFixed(1)}s ago`);
    if(!paused){
      if(data.frame?.error){resetView();$('empty').querySelector('h2').textContent='Observer unavailable';$('empty').querySelector('p').textContent=data.frame.error;}
      else if(data.frame)updateFrame(data.frame);
      else if(frame)resetView();
    }
  } catch(error) {showStatus('offline','Server unavailable · retrying');text('age','Disconnected');}
  setTimeout(poll,500);
}
$('live').onclick=()=>setMode(false);$('preview').onclick=()=>setMode(true);
$('stream').onchange=()=>{selectedStream=$('stream').value;resetView();};
$('density').onchange=()=>{renderer.count=Number($('density').value);renderer.draw();};
$('fit').onclick=()=>renderer.fit();
$('pause').onclick=()=>{paused=!paused;$('pause').setAttribute('aria-pressed',String(paused));text('pause',paused?'▶ Resume':'Ⅱ Pause');$('pause-banner').hidden=!paused;};
function pin(node){pinned=node?.id||null;renderer.focus=pinned;$('node-select').value=pinned||'';$('unpin').hidden=!pinned;renderer.draw();if(node){$('details').open=true;inspect(node);}}
$('unpin').onclick=()=>pin(null);$('node-select').onchange=()=>pin(renderer.layout?.byId.get($('node-select').value));
const stage=$('stage');let drag=null;
stage.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,px:renderer.pan.x,py:renderer.pan.y,moved:false};stage.setPointerCapture(e.pointerId);});
stage.addEventListener('pointermove',e=>{const r=stage.getBoundingClientRect();if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>3)drag.moved=true;if(drag.moved){renderer.pan={x:drag.px+dx,y:drag.py+dy};renderer.draw();}}else if(!pinned)inspect(renderer.hit(e.clientX-r.left,e.clientY-r.top));});
stage.addEventListener('pointerup',e=>{if(drag&&!drag.moved){const r=stage.getBoundingClientRect();pin(renderer.hit(e.clientX-r.left,e.clientY-r.top));}drag=null;});
stage.addEventListener('pointercancel',()=>drag=null);
stage.addEventListener('wheel',e=>{e.preventDefault();renderer.zoom=Math.max(.5,Math.min(5,renderer.zoom*Math.exp(-e.deltaY*.001)));renderer.draw();},{passive:false});
new ResizeObserver(()=>renderer.draw()).observe(stage);
poll();
