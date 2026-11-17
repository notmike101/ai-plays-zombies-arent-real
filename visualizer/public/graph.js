export const formatNumber = v => Number.isFinite(v) ? (Math.abs(v) >= 1000 ? v.toFixed(1) : v.toFixed(4)) : '—';
export const palette = {positive:[.29,.91,.72], negative:[.65,.54,1], memory:[.35,.66,.91], selected:[1,.78,.38]};

export function layoutGraph(graph) {
  const nodes = [], titles = [];
  const heads = graph.layers.filter(l => l.kind === 'policy' || l.kind === 'value');
  const columns=layer=>layer.size>256?48:layer.size>24?8:layer.id==='hc'?4:1;
  const headRows=heads.reduce((sum,layer)=>sum+Math.ceil(layer.size/columns(layer)),0);
  let headY = 135;
  for (const layer of graph.layers) {
    let x, y, cols, dx, dy, title;
    if (layer.kind === 'input') { cols=Math.ceil(layer.size/48); x=cols>1?100:188; y=150; dx=cols>1?160/(cols-1):0; dy=Math.min(21,440/Math.max(1,Math.ceil(layer.size/cols)-1)); title='INPUTS'; }
    else if (layer.kind === 'memory') { x=340; y=485; cols=16; dx=10; dy=Math.min(12,120/Math.ceil(layer.size/16)); title='PREVIOUS MEMORY'; }
    else if (layer.kind === 'gru') { x=565; y=178; cols=8; dx=16; dy=Math.min(23,360/Math.ceil(layer.size/8)); title='GRU HIDDEN STATE'; }
    else {
      x=900; y=headY; cols=columns(layer); dx=cols>8?168/(cols-1):23;
      dy=Math.min(21,(420-65*(heads.length-1))/Math.max(1,headRows));
      title=layer.kind==='value' ? 'EXPECTED RETURN' : layer.id==='hc' ? 'MAP POSITION' : 'ACTION';
      headY += Math.ceil(layer.size/cols)*dy+65;
    }
    titles.push({x:layer.kind==='input'?65:x, y:y-35, text:title, subtitle:`${layer.size} ${layer.kind==='input'?'features':layer.kind==='gru'?'hidden units':layer.kind==='memory'?'units · t − 1':'outputs'}`, layer:layer.id});
    for(let i=0;i<layer.size;i++) nodes.push({id:`${layer.id}:${i}`,layer:layer.id,index:i,label:layer.labels?.[i]||`${layer.id} ${i}`,kind:layer.kind,compact:cols>1,radius:Math.min(7,dy*.35,cols>1?dx*.35:7),x:x+(i%cols)*dx,y:y+Math.floor(i/cols)*dy});
  }
  return {nodes, titles, byId:new Map(nodes.map(n=>[n.id,n]))};
}

export function visibleEdges(edges, perTarget=2, focus=null) {
  const groups = new Map();
  for(const edge of edges) {
    if(focus && edge.from!==focus && edge.to!==focus) continue;
    const group=groups.get(edge.to)||[]; group.push(edge); groups.set(edge.to,group);
  }
  return [...groups.values()].flatMap(group=>group.sort((a,b)=>Math.abs(b.weight)-Math.abs(a.weight)).slice(0,focus?6:perTarget));
}

const shader = `
struct Out { @builtin(position) position: vec4f, @location(0) color: vec4f, @location(1) uv: vec2f, @location(2) circle: f32 };
@vertex fn vs(@location(0) pos: vec2f, @location(1) color: vec4f, @location(2) uv: vec2f, @location(3) circle: f32) -> Out {
  var o: Out; o.position=vec4f(pos,0,1); o.color=color; o.uv=uv; o.circle=circle; return o;
}
@fragment fn fs(i: Out) -> @location(0) vec4f {
  var alpha=i.color.a;
  if(i.circle > 0.5) { let d=length(i.uv); if(d>1.0){discard;} alpha*=1.0-smoothstep(0.35,1.0,d); }
  return vec4f(i.color.rgb,alpha);
}`;

export class Renderer {
  constructor(canvas, labels, onMode) {
    this.canvas=canvas; this.overlay=labels; this.onMode=onMode; this.zoom=1; this.pan={x:0,y:0}; this.focus=null; this.count=2;
    this.mode='Canvas 2D'; this.graph=null; this.frame=null;
  }
  async init(force2d=false) {
    if(!force2d && navigator.gpu) {
      try {
        const adapter=await navigator.gpu.requestAdapter({powerPreference:'low-power'});
        if(!adapter) throw new Error('No WebGPU adapter');
        const device=await adapter.requestDevice(); this.device=device;
        device.pushErrorScope('validation');
        const context=this.canvas.getContext('webgpu'); if(!context) throw new Error('No WebGPU canvas');
        const format=navigator.gpu.getPreferredCanvasFormat();
        context.configure({device,format,alphaMode:'opaque'}); this.context=context;
        const module=device.createShaderModule({code:shader});
        const descriptor={layout:'auto',vertex:{module,entryPoint:'vs',buffers:[{arrayStride:36,attributes:[
          {shaderLocation:0,offset:0,format:'float32x2'}, {shaderLocation:1,offset:8,format:'float32x4'},
          {shaderLocation:2,offset:24,format:'float32x2'}, {shaderLocation:3,offset:32,format:'float32'}]}]},
          fragment:{module,entryPoint:'fs',targets:[{format,blend:{color:{srcFactor:'src-alpha',dstFactor:'one-minus-src-alpha'},alpha:{srcFactor:'one',dstFactor:'one-minus-src-alpha'}}}]}};
        this.lines=await device.createRenderPipelineAsync({...descriptor,primitive:{topology:'line-list'}});
        this.dots=await device.createRenderPipelineAsync({...descriptor,primitive:{topology:'triangle-list'}});
        const error=await device.popErrorScope(); if(error) throw new Error(error.message);
        this.buffer=device.createBuffer({size:4*1024*1024,usage:GPUBufferUsage.VERTEX|GPUBufferUsage.COPY_DST});
        this.mode='WebGPU'; device.lost.then(()=>this.fallback('Device lost'));
        device.addEventListener('uncapturederror',event=>this.fallback(event.error.message));
      } catch(error) { this.fallback(error.message); }
    }
    if(this.mode!=='WebGPU') this.context=this.canvas.getContext('2d');
    this.onMode(this.mode); this.draw();
  }
  fallback(reason) {
    if(this.canvas.getContext('webgpu')) {
      const replacement=this.canvas.cloneNode(); this.canvas.replaceWith(replacement); this.canvas=replacement;
    }
    this.mode='Canvas 2D'; this.context=this.canvas.getContext('2d'); this.onMode(this.mode,reason); this.draw();
  }
  setFrame(frame) {
    if(frame.graph && (this.revision!==frame.model_revision || this.stream!==frame.stream)) {
      this.graph=frame.graph; this.layout=layoutGraph(frame.graph); this.revision=frame.model_revision; this.stream=frame.stream;
      if(!this.layout.byId.has(this.focus)) this.focus=null;
    }
    this.frame=frame; this.draw();
  }
  fit() { this.zoom=1; this.pan={x:0,y:0}; this.draw(); }
  zoomAt(zoom,x=this.width/2,y=this.height/2) {
    const next=Math.max(.5,Math.min(12,zoom)),ratio=next/this.zoom;
    this.pan={x:x-this.width/2-(x-this.width/2-this.pan.x)*ratio,
              y:y-this.height/2-(y-this.height/2-this.pan.y)*ratio};
    this.zoom=next;this.draw();
  }
  transform(x,y) {
    const scale=Math.min(this.width/1160,this.height/700)*this.zoom;
    return {x:(x-580)*scale+this.width/2+this.pan.x,y:(y-350)*scale+this.height/2+this.pan.y,scale};
  }
  hit(x,y) {
    let best=null,distance=14;
    for(const n of this.layout?.nodes||[]) {const p=this.transform(n.x,n.y),d=Math.hypot(x-p.x,y-p.y);if(d<distance){best=n;distance=d;}}
    return best;
  }
  draw() {
    const rect=this.canvas.getBoundingClientRect(); if(!rect.width || !rect.height || !this.context) return;
    this.width=rect.width; this.height=rect.height; const ratio=Math.min(window.devicePixelRatio||1,2);
    for(const canvas of [this.canvas,this.overlay]) {const w=Math.round(rect.width*ratio),h=Math.round(rect.height*ratio);if(canvas.width!==w)canvas.width=w;if(canvas.height!==h)canvas.height=h;}
    const ctx=this.overlay.getContext('2d'); ctx.setTransform(ratio,0,0,ratio,0,0); ctx.clearRect(0,0,this.width,this.height);
    if(!this.layout) {
      if(this.mode==='Canvas 2D') this.context.clearRect(0,0,this.canvas.width,this.canvas.height);
      else {
        const encoder=this.device.createCommandEncoder();
        const pass=encoder.beginRenderPass({colorAttachments:[{view:this.context.getCurrentTexture().createView(),clearValue:{r:.027,g:.043,b:.055,a:1},loadOp:'clear',storeOp:'store'}]});
        pass.end();this.device.queue.submit([encoder.finish()]);
      }
      return;
    }
    const {nodes,byId,titles}=this.layout, values=this.frame?.values||{}, maximum={};
    for(const [id,vs] of Object.entries(values)) maximum[id]=Math.max(.001,...vs.map(v=>Math.abs(v)));
    const activation=n=>Math.min(1,Math.abs(values[n.layer]?.[n.index]||0)/(maximum[n.layer]||1));
    const edges=visibleEdges(this.graph.edges,this.count,this.focus), lines=[],dots=[];
    const vertex=(array,x,y,color,u=0,v=0,circle=0)=>{const p=this.transform(x,y); array.push(p.x/this.width*2-1,1-p.y/this.height*2,...color,u,v,circle);};
    const rgba=(rgb,a)=>`rgba(${rgb.map(v=>Math.round(v*255)).join(',')},${a})`;
    const plain=this.mode==='Canvas 2D'?this.context:null;
    if(plain){plain.setTransform(ratio,0,0,ratio,0,0);plain.clearRect(0,0,this.width,this.height);}
    for(const edge of edges) {
      const a=byId.get(edge.from),b=byId.get(edge.to); if(!a||!b)continue;
      const rgb=edge.kind==='gate-rms'?palette.memory:edge.weight<0?palette.negative:palette.positive;
      const alpha=this.focus ? .6:.06+activation(a)*.19;
      vertex(lines,a.x,a.y,[...rgb,alpha]);vertex(lines,b.x,b.y,[...rgb,alpha]);
      if(plain){const p=this.transform(a.x,a.y),q=this.transform(b.x,b.y);plain.strokeStyle=rgba(rgb,alpha);plain.lineWidth=.7;plain.beginPath();plain.moveTo(p.x,p.y);plain.lineTo(q.x,q.y);plain.stroke();}
    }
    for(const node of nodes) {
      const isChosen=this.frame?.selected?.[node.layer]===node.index;
      const rgb=isChosen||node.id===this.focus?palette.selected:node.kind==='memory'?palette.memory:(values[node.layer]?.[node.index]||0)<0?palette.negative:palette.positive;
      const strength=activation(node),radius=node.kind==='gru'||node.kind==='memory'?5:node.radius;
      const color=[...rgb,.22+.78*strength];
      for(const [u,v] of [[-1,-1],[1,-1],[-1,1],[-1,1],[1,-1],[1,1]]) vertex(dots,node.x+u*radius,node.y+v*radius,color,u,v,1);
      if(plain){const p=this.transform(node.x,node.y);plain.fillStyle=rgba(rgb,color[3]);plain.beginPath();plain.arc(p.x,p.y,Math.max(1,radius*p.scale*.5),0,Math.PI*2);plain.fill();}
      if(isChosen){const p=this.transform(node.x,node.y);ctx.strokeStyle='#ffd283';ctx.lineWidth=1;ctx.beginPath();ctx.arc(p.x,p.y,9*p.scale,0,Math.PI*2);ctx.stroke();}
      if(this.transform(0,0).scale>=.5 && (node.id===this.focus || (!node.compact && (node.kind==='input'||(node.kind==='policy'&&this.graph.layers.find(l=>l.id===node.layer).size<=24&&node.layer!=='hc'))))) {
        const p=this.transform(node.x+(node.kind==='input'?-14:15),node.y+3); ctx.font=`${Math.max(8,10*p.scale)}px ui-monospace,monospace`;ctx.fillStyle=isChosen?'#ffe0a0':'#8d9da9';ctx.textAlign=node.kind==='input'?'right':'left';ctx.fillText(node.label.replaceAll('_',' '),p.x,p.y);
      }
    }
    for(const node of nodes) {
      const p=this.transform(1040,node.y),chosen=this.frame.selected?.[node.layer]===node.index;
      if(p.scale<.5)continue;
      if(node.kind==='policy' && node.layer!=='hc' && this.graph.layers.find(l=>l.id===node.layer).size<=24) {
        const probability=this.frame.probabilities?.[node.layer]?.[node.index];
        if(Number.isFinite(probability)) {
          const width=64*p.scale;
          ctx.fillStyle='#1a2b32';ctx.fillRect(p.x,p.y-2*p.scale,width,4*p.scale);
          ctx.fillStyle=chosen?'#ecc67e':'#5cae91';ctx.fillRect(p.x,p.y-2*p.scale,width*Math.max(0,Math.min(1,probability)),4*p.scale);
          ctx.font=`${Math.max(8,9*p.scale)}px ui-monospace,monospace`;ctx.textAlign='left';ctx.fillStyle=chosen?'#ecc67e':'#90a7b2';ctx.fillText(`${(probability*100).toFixed(1)}%`,p.x+width+6*p.scale,p.y+3*p.scale);
        }
      }
      if(node.kind==='value') {
        const label=this.transform(node.x+16,node.y+4);ctx.font=`${Math.max(9,12*p.scale)}px ui-monospace,monospace`;ctx.textAlign='left';ctx.fillStyle='#b6d4c8';ctx.fillText(formatNumber(values[node.layer]?.[node.index]),label.x,label.y);
      }
    }
    if(!plain){
      const data=new Float32Array([...lines,...dots]);
      if(data.byteLength>this.buffer.size) {this.buffer.destroy();this.buffer=this.device.createBuffer({size:data.byteLength*2,usage:GPUBufferUsage.VERTEX|GPUBufferUsage.COPY_DST});}
      this.device.queue.writeBuffer(this.buffer,0,data);
      const encoder=this.device.createCommandEncoder(),pass=encoder.beginRenderPass({colorAttachments:[{view:this.context.getCurrentTexture().createView(),clearValue:{r:.027,g:.043,b:.055,a:1},loadOp:'clear',storeOp:'store'}]});
      pass.setVertexBuffer(0,this.buffer);pass.setPipeline(this.lines);pass.draw(lines.length/9);pass.setPipeline(this.dots);pass.draw(dots.length/9,1,lines.length/9);pass.end();this.device.queue.submit([encoder.finish()]);
    }
    ctx.textAlign='left';
    for(const title of titles){const p=this.transform(title.x,title.y);ctx.font=`600 ${Math.max(9,10*p.scale)}px system-ui`;ctx.fillStyle='#cbd7dd';ctx.fillText(p.scale<.5?title.layer.toUpperCase():title.text,p.x,p.y);if(p.scale>=.5){ctx.font=`${Math.max(9,10*p.scale)}px ui-monospace,monospace`;ctx.fillStyle='#657783';ctx.fillText(title.subtitle,p.x,p.y+17*p.scale);}}
    const p=this.transform(340,615);if(p.scale>=.5){ctx.font=`${Math.max(8,10*p.scale)}px system-ui`;ctx.fillStyle='#668798';ctx.fillText('Recurrent memory feeds the next decision',p.x,p.y);}
  }
}
