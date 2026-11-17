import assert from 'node:assert/strict';
import {layoutGraph, visibleEdges, formatNumber, Renderer} from './public/graph.js';
const graph = {layers: [{id:'input',size:3,kind:'input',labels:['a','b','c']}, {id:'memory',size:8,kind:'memory',labels:[]}, {id:'gru',size:8,kind:'gru',labels:[]}, {id:'hu',size:4,kind:'policy',labels:[]}], edges:[
  {from:'input:0',to:'gru:0',weight:.2}, {from:'input:1',to:'gru:0',weight:-.8}, {from:'input:2',to:'gru:0',weight:.4},
]};
const layout = layoutGraph(graph);
assert.equal(layout.nodes.length,23);
assert.equal(new Set(layout.nodes.map(n=>n.id)).size,23);
assert(layout.nodes.every(n=>Number.isFinite(n.x)&&n.x>=0&&n.x<=1160&&n.y>=0&&n.y<=700));
assert.equal(visibleEdges(graph.edges, 1)[0].weight, -.8);
assert.equal(visibleEdges(graph.edges, 1, 'input:0').length,1);
assert.equal(formatNumber(NaN),'—');
assert.equal(formatNumber(.123456),'0.1235');
let submissions=0;
globalThis.window={devicePixelRatio:1};
const canvas={getBoundingClientRect:()=>({width:800,height:600})};
const overlay={getContext:()=>({setTransform(){},clearRect(){}})};
const renderer=new Renderer(canvas,overlay,()=>{});
renderer.mode='WebGPU';renderer.context={getCurrentTexture:()=>({createView:()=>({})})};
renderer.device={createCommandEncoder:()=>({beginRenderPass:()=>({end(){}}),finish:()=>({})}),queue:{submit(){submissions++;}}};
renderer.draw();
assert.equal(submissions,1,'Waiting state must clear old GPU inference');
console.log('Graph assertions passed');
