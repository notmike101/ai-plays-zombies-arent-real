// Run against a server started with --preview using playwright-cli run-code --filename=visualizer/test_mobile.js.
async page => {
  const base=new URL(page.url()).origin;
  const expect=(condition,message)=>{if(!condition)throw new Error(message);};
  const results=[];
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:2});
  const touch=async(type,points)=>{
    await cdp.send('Input.dispatchTouchEvent',{type,touchPoints:points});
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  };
  try {
    for(const fallback of [false,true]){
      await page.setViewportSize({width:390,height:844});
      await page.goto(`${base}/legacy${fallback?'?canvas2d=1':''}`);
      await page.waitForFunction(()=>document.querySelector('#status').textContent!=='CONNECTING');
      await page.locator('#preview').click();
      await page.waitForFunction(()=>document.querySelector('#status').textContent==='SYNTHETIC PREVIEW' && document.querySelector('#footer-state').textContent.includes('nodes'));
      await page.locator('#pause').click();
      await page.evaluate(async()=>{
        const {Renderer}=await import('/graph.js'),draw=Renderer.prototype.draw;
        Renderer.prototype.draw=function(){
          const result=draw.call(this),node=this.layout?.nodes[0];
          window.mobileCamera={zoom:this.zoom,pan:{...this.pan},node:node?this.transform(node.x,node.y):null};
          return result;
        };
      });
      await page.locator('#fit').click();
      const bounds=await page.locator('#stage').boundingBox(),y=bounds.y+bounds.height/2;
      await touch('touchStart',[{x:145,y,id:1},{x:245,y,id:2}]);
      await touch('touchMove',[{x:95,y,id:1},{x:295,y,id:2}]);
      let camera=await page.evaluate(()=>window.mobileCamera);
      expect(Math.abs(camera.zoom-2)<.01,'Pinch must double zoom when finger separation doubles');
      expect(Math.abs(camera.pan.x)<1 && Math.abs(camera.pan.y)<1,'Centered pinch must keep its anchor');
      await touch('touchEnd',[{x:295,y,id:2}]);
      await touch('touchMove',[{x:135,y:y+25,id:1}]);
      camera=await page.evaluate(()=>window.mobileCamera);
      expect(Math.abs(camera.pan.x-40)<1 && Math.abs(camera.pan.y-25)<1,`Lifting one finger must continue a smooth pan: ${JSON.stringify(camera)}`);
      await touch('touchEnd',[]);
      expect(!await page.locator('#details').evaluate(el=>el.open),'Pinch or drag must not select a node');
      await page.locator('#zoom-in').click();
      expect(Math.abs((await page.evaluate(()=>window.mobileCamera.zoom))-3)<.01,'Zoom button must magnify the graph');
      await page.locator('#zoom-out').click();
      await page.locator('#fit').click();
      await touch('touchStart',[{x:145,y,id:1},{x:245,y,id:2}]);
      await touch('touchCancel',[]);
      const node=await page.evaluate(()=>window.mobileCamera.node);
      await touch('touchStart',[{x:node.x,y:bounds.y+node.y,id:1}]);
      await touch('touchEnd',[]);
      expect(await page.locator('#details').evaluate(el=>el.open),'A tap after cancellation must still inspect a node');
      expect((await page.locator('.inspect-value').innerText())!=='—','Tapped nodes must expose their activation');
      expect(await page.locator('.prob-row').count()===15,'All 15 preview action probabilities must be accessible');
      await page.locator('#node-select').selectOption('hc:11');
      expect((await page.locator('#inspector').innerText()).includes('policy probability'),'Map position probabilities must be inspectable');
      for(const size of [{width:320,height:568},{width:390,height:844},{width:844,height:390}]){
        await page.setViewportSize(size);
        await page.locator('#graph-note').scrollIntoViewIfNeeded();
        const layout=await page.evaluate(()=>{
          const body=document.querySelector('.drawer-body'),rect=body.getBoundingClientRect(),note=document.querySelector('#graph-note').getBoundingClientRect();
          return {overflow:document.documentElement.scrollWidth>innerWidth,drawerOverflow:body.scrollWidth>body.clientWidth,bottom:rect.bottom,noteBottom:note.bottom,height:innerHeight};
        });
        expect(!layout.overflow && !layout.drawerOverflow,'Mobile details must not overflow horizontally');
        expect(layout.bottom<=layout.height && layout.noteBottom<=layout.bottom,'Inspector must scroll to the final details within the viewport');
      }
      await page.setViewportSize({width:390,height:844});
      await page.locator('#node-select').scrollIntoViewIfNeeded();
      await page.screenshot({path:`runtime/mobile-inspector-${fallback?'canvas':'gpu'}.png`});
      await page.locator('#unpin').click();
      await page.locator('#details summary').click();
      await page.locator('#fit').click();
      await page.screenshot({path:`runtime/mobile-graph-${fallback?'canvas':'gpu'}.png`});
      results.push({renderer:await page.locator('#renderer').innerText(),checks:'pinch anchor, pan transition, cancellation, tap inspection, zoom buttons, full probabilities, portrait/landscape scrolling'});
    }
    await page.setViewportSize({width:1280,height:720});
    await page.locator('#fit').click();
    const stage=await page.locator('#stage').boundingBox();
    await page.mouse.move(450,stage.y+200);
    await page.mouse.wheel(0,-400);
    await page.waitForFunction(()=>window.mobileCamera.zoom>1);
    const before=await page.evaluate(()=>window.mobileCamera.pan);
    await page.mouse.down();await page.mouse.move(500,stage.y+230,{steps:5});await page.mouse.up();
    const after=await page.evaluate(()=>window.mobileCamera.pan);
    expect(Math.abs(after.x-before.x-50)<1 && Math.abs(after.y-before.y-30)<1,'Desktop mouse dragging must still pan');
    results.push({checks:'desktop wheel zoom and mouse drag'});
  } finally {
    await cdp.detach();
    await page.setViewportSize({width:1280,height:720});
    await page.goto(`${base}/legacy`);
  }
  return results;
}
