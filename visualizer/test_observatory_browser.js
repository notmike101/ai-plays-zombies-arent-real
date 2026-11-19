// Playwright run-code against an isolated server with a synthetic preview.
async page => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const errors = [], requested = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => requested.push(new URL(request.url()).pathname));
  const root = new URL(page.url()).origin;
  await page.goto(root);
  await page.locator('#mode').selectOption('preview');
  await page.waitForFunction(() => document.querySelector('#status').textContent === 'Synthetic preview');
  await page.getByRole('button', {name: 'Neural activity'}).click();
  await page.waitForFunction(() => document.querySelector('#feature-page').textContent.includes('4889'));
  assert(await page.locator('#feature-list button').count() === 16, 'Keep feature DOM bounded');
  assert(await page.locator('option').count() < 100, 'No per-unit dropdowns');
  await page.locator('#feature-search').fill('damaged buildings');
  await page.waitForFunction(() => document.querySelector('#feature-page').textContent.includes('of 48'));
  await page.locator('#activation-heat').focus();
  await page.keyboard.press('ArrowRight');
  assert((await page.locator('#activation-detail').innerText()).includes('damaged buildings'), 'Inspect a labeled activation');
  await page.locator('#load-weights').click();
  await page.waitForFunction(() => !document.querySelector('#weight-heat').hidden);
  assert((await page.locator('#weight-detail').innerText()).includes('[0, 0]'), 'Read a captured coefficient');
  await page.getByRole('button', {name: 'Timeline'}).click();
  await page.waitForFunction(() => document.querySelector('#events').children.length >= 3);
  await page.locator('#events button').last().click();
  await page.waitForFunction(() => document.querySelector('#sample-context').textContent.includes('Replay'));
  const initial = await page.locator('#sample-context').innerText();
  await page.locator('#compare').selectOption({index: 1});
  await page.getByRole('heading', {name: 'Largest observation changes'}).waitFor();
  await page.getByRole('button', {name: 'Inspect in monitor'}).click();
  assert(await page.locator('#sample-context').innerText() === initial, 'Replay selection remains fixed');
  for (const width of [320, 390, 844, 1440]) {
    await page.setViewportSize({width, height: 700});
    for (const name of ['Neural activity', 'Timeline', 'Monitor']) {
      await page.getByRole('button', {name, exact: true}).click();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} must fit ${width}px`);
    }
  }
  await page.context().setOffline(true);
  await page.locator('#stream').selectOption({index: 1});
  await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Disconnected'));
  await page.context().setOffline(false);
  await page.waitForFunction(() => document.querySelector('#status').textContent === 'Synthetic preview');
  await page.locator('#mode').selectOption('live');
  await page.waitForFunction(() => document.querySelector('#status').textContent === 'Waiting for worker');
  assert(await page.locator('#sample-context').isHidden(), 'Preview data must clear when switching to live');
  assert(!requested.includes('/api/state'), 'Use SSE for live traffic');
  assert(!errors.length, errors.join('\n'));
  return {responsiveWidths: [320, 390, 844, 1440], replay: true, rawWeights: true, reconnect: true, boundedDOM: true};
}
