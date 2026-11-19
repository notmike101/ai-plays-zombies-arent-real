// playwright-cli run-code --filename=visualizer/test_stream.js (server with --preview).
async page => {
  const expect=(condition,message)=>{if(!condition)throw new Error(message);};
  const base=new URL(page.url()).origin;
  const requests=[],errors=[];
  const onRequest=request=>requests.push(new URL(request.url()).pathname);
  const onError=error=>errors.push(String(error));
  page.on('request',onRequest);page.on('pageerror',onError);
  try {
    await page.goto(`${base}/legacy?canvas2d=1`);
    await page.locator('#preview').click();
    await page.waitForFunction(()=>document.querySelector('#decision-log')?.children.length>0,{},{timeout:8000});
    expect(requests.includes('/api/events'),'Browser must use the persistent stream');
    expect(!requests.includes('/api/state'),'Browser must not poll the snapshot endpoint');
    await page.locator('#details').evaluate(el=>el.open=true);
    const values=await page.locator('#observations .data-row').count();
    expect(values>0,'Actual input values must be readable without selecting each node');
    const countBefore=await page.locator('#decision-log').getAttribute('data-signature');
    await page.locator('#observations .data-row').first().evaluate(el=>el.dataset.reused='yes');
    await page.waitForFunction(previous=>document.querySelector('#decision-log').dataset.signature!==previous,countBefore);
    expect(await page.locator('#observations .data-row').first().getAttribute('data-reused')==='yes','Input rows must be reused across decisions');
    await page.locator('#pause').click();
    const frozen=await page.locator('#decision-log').innerText();
    const sample=await page.locator('#footer-state').innerText();
    await page.waitForTimeout(1400);
    expect(await page.locator('#decision-log').innerText()===frozen,'View pause must freeze the decision log');
    expect(await page.locator('#footer-state').innerText()===sample,'View pause must freeze the graph');
    await page.locator('#pause').click();
    await page.waitForFunction(previous=>document.querySelector('#footer-state').textContent!==previous,sample);
    const selected=await page.locator('#stream option').nth(1).getAttribute('value');
    await page.locator('#stream').selectOption(selected);
    await page.waitForFunction(()=>document.querySelector('#decision-log')?.children.length>0);
    await page.context().setOffline(true);
    // Chromium offline emulation can leave an already-established SSE socket open.
    await page.locator('#stream').selectOption('');
    await page.waitForFunction(()=>document.querySelector('#status').textContent==='OFFLINE',null,{timeout:8000});
    await page.context().setOffline(false);
    await page.waitForFunction(()=>document.querySelector('#status').textContent==='SYNTHETIC PREVIEW',null,{timeout:8000});
    expect((await page.locator('#footer-state').innerText()).includes('nodes'),'Reconnect must restore graph topology');
    expect(await page.locator('#decision-log li').count()<=50,'History must remain bounded');
    await page.locator('#live').click();
    await page.waitForFunction(()=>document.querySelector('#status').textContent==='WAITING FOR WORKER');
    expect(await page.locator('#decision-log li').count()===0,'Preview history must not leak into Live');
    expect(await page.locator('#observations .data-row').count()===0,'Preview inputs must clear on mode change');
    expect(errors.length===0,errors.join('\n'));
    return {streaming:true,reconnect:true,pause:true,previewIsolation:true,inputValues:values,requests:requests.filter(p=>p.startsWith('/api/'))};
  } finally {
    await page.context().setOffline(false);
    page.off('request',onRequest);page.off('pageerror',onError);
  }
}
