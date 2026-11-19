// Playwright run-code against a local observatory. Uses synthetic UI fixtures only.
async page => {
  const captureRequests = [];
  let secondVideoRequests = 0;
  await page.setViewportSize({width: 390, height: 844});
  await page.route('**/api/game-video?**', route => {
    const stream = new URL(route.request().url()).searchParams.get('stream');
    return route.fulfill({status: stream === 'second' && ++secondVideoRequests === 1 ? 409 : 503});
  });
  await page.route('**/api/screenshot?**', async route => {
    captureRequests.push(new URL(route.request().url()).searchParams.get('stream'));
    await route.fulfill({
      contentType: 'image/png',
      headers: {'X-Captured-At': String(Date.now() / 1000)},
      body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ/wAAAAASUVORK5CYII=', 'base64'),
    });
  });
  await page.addInitScript(() => {
    window.EventSource = class {
      addEventListener(_, receive) {
        window.showFixture = (stream, game = null) => receive({data: JSON.stringify({
          version: 1, status: stream ? 'live' : 'waiting', age: 0, stream, history: [],
          streams: stream ? [{id: stream, game_pid: 123, worker_pid: 456, age: 0}] : [],
          game_view: game,
          metadata: {input_labels: [], tools: ['wait']},
          sample: stream ? {stream, sequence: 1, timestamp: Date.now() / 1000, phase: 'planning',
            model_revision: 'fixture', action: 'wait', tool: 0, game_pid: 123,
            input: [], tool_probabilities: [1], tool_logits: [0], location_probabilities: []} : null,
        })});
      }
      close() {}
    };
  });
  await page.goto(new URL(page.url()).origin);
  await page.waitForFunction(() => typeof window.showFixture === 'function');
  if (!await page.locator('#game-view').evaluate(details => details.open)) throw new Error('Game view must start expanded');
  if (captureRequests.length) throw new Error('Game view must wait for a live game');
  await page.evaluate(() => window.showFixture('first'));
  await page.waitForFunction(() => document.querySelector('#game-screenshot').naturalWidth > 0);
  await page.evaluate(() => window.showFixture('second'));
  await page.waitForFunction(() => window.document.querySelector('#game-capture-status').textContent === 'Waiting for the previous video to close.',
    null, {timeout: 3000});
  if (captureRequests.includes('second')) throw new Error('A busy handoff must retry live video before falling back');
  await page.waitForTimeout(900);
  await page.evaluate(() => window.showFixture('second'));
  await page.waitForFunction(() => document.querySelector('#game-screenshot').naturalWidth > 0);
  if (!captureRequests.includes('second') || secondVideoRequests !== 2) throw new Error('Worker changes must retry and switch streams');
  await page.evaluate(() => window.showFixture(null, {id: 'game:999:1000', game_pid: 999, copy: 'inst17'}));
  await page.getByText(/Game image only · inst17/).waitFor();
  if (!captureRequests.includes('game:999:1000')) throw new Error('Game view must use owned game fallback');
  if (!await page.locator('#sample-context').isHidden()) throw new Error('A game-only view must not display a policy sample');
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Game view overflows mobile');
  await page.getByText('Game view', {exact: true}).click();
  await page.locator('#game-screenshot').waitFor({state: 'hidden'});
  return {expandedByDefault: true, imageDecoded: true, targeted: true, mobile: true};
}
