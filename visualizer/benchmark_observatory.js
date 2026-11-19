// Playwright run-code against benchmark_observatory.py --serve.
async page => {
  const origin = new URL(page.url()).origin;
  const results = {};
  await page.setViewportSize({width: 1440, height: 900});
  await page.addInitScript(() => {
    const add = EventSource.prototype.addEventListener;
    const parse = JSON.parse;
    window.benchmark = [];
    let current;
    JSON.parse = function (value, ...args) {
      const before = performance.now();
      const decoded = parse.call(this, value, ...args);
      if (current) current.parse += performance.now() - before;
      return decoded;
    };
    EventSource.prototype.addEventListener = function (event, listener, ...args) {
      if (event !== 'state') return add.call(this, event, listener, ...args);
      return add.call(this, event, function (sample) {
        const value = parse(sample.data);
        if (!(value.frame || value.sample)) return listener.call(this, sample);
        const row = current = {parse: 0, bytes: new TextEncoder().encode(sample.data).length};
        const start = performance.now();
        try { return listener.call(this, sample); } finally {
          row.handler = performance.now() - start;
          row.render = row.handler - row.parse;
          current = null;
          window.benchmark.push(row);
        }
      }, ...args);
    };
  });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  for (const [kind, route] of [['legacy', '/legacy?canvas2d=1'], ['monitor', '/'], ['activity', '/']]) {
    await page.goto(origin + route);
    await page.waitForFunction(() => window.benchmark.length > 0);
    if (kind === 'activity') await page.getByRole('button', {name: 'Neural activity'}).click();
    await page.waitForFunction(() => window.benchmark.length >= 10);
    await cdp.send('HeapProfiler.collectGarbage');
    const {metrics} = await cdp.send('Performance.getMetrics');
    const recorded = await page.evaluate(() => ({
      events: window.benchmark.slice(0, 10),
      options: document.querySelectorAll('option').length,
      inputRows: document.querySelectorAll('.data-row, .feature').length,
    }));
    const median = key => {
      const values = recorded.events.slice(2).map(row => row[key]).sort((a, b) => a - b);
      return Number(((values[3] + values[4]) / 2).toFixed(3));
    };
    results[kind] = {
      firstBytes: recorded.events[0].bytes,
      firstHandlerMs: Number(recorded.events[0].handler.toFixed(3)),
      steadyParseMs: median('parse'), steadyRenderHandlerMs: median('render'),
      heapBytes: metrics.find(item => item.name === 'JSHeapUsedSize').value,
      options: recorded.options, inputRows: recorded.inputRows,
    };
  }
  await cdp.detach();
  return results;
}
