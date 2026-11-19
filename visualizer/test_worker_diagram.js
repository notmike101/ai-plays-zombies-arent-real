// Playwright run-code against a local observatory. Uses synthetic worker state.
async page => {
  const a = {id: 'game:100:1', game_pid: 100, copy: 'inst13', stream: 'a', worker_pid: 101};
  const b = {id: 'game:200:1', game_pid: 200, copy: 'inst14', stream: null, worker_pid: null};
  await page.setViewportSize({width: 390, height: 844});
  await page.route('**/api/game-video?**', route => route.fulfill({status: 403}));
  await page.addInitScript(() => {
    window.EventSource = class {
      constructor(url) { window.workerQuery = new URL(url, location.origin).searchParams.get('game'); }
      addEventListener(_, callback) {
        window.publishWorkers = (workers, chosen) => callback({data: JSON.stringify({
          version: 1, status: 'waiting', stream: null, history: [], workers,
          selected_worker: chosen?.id ?? null, game_view: chosen || null,
          worker_pinned: chosen?.id === window.workerQuery,
        })});
      }
      close() {}
    };
  });
  await page.goto(new URL(page.url()).origin);
  await page.waitForFunction(() => typeof window.publishWorkers === 'function');
  await page.evaluate(([a, b]) => window.publishWorkers([a, b], a), [a, b]);
  const nodeA = page.getByRole('button', {name: /inst13/});
  const nodeB = page.getByRole('button', {name: /inst14/});
  if (await nodeA.getAttribute('aria-pressed') !== 'true') throw new Error('First worker must be selected');
  await nodeB.focus();
  await page.keyboard.press('Enter');
  await page.waitForFunction(id => window.workerQuery === id, b.id);
  await page.evaluate(([a, b]) => window.publishWorkers([a, b], b), [a, b]);
  if (await nodeB.getAttribute('aria-pressed') !== 'true') throw new Error('Worker selection was lost');
  await page.route('**/api/learning', route => route.fulfill({json: {runs: [], campaigns: [], ppo: [], updates: []}}));
  await page.getByRole('button', {name: 'Learning', exact: true}).click();
  const diagram = page.locator('.worker-diagram');
  if (await diagram.isVisible()) throw new Error('Learning must hide the worker diagram');
  await page.getByRole('button', {name: 'Monitor', exact: true}).click();
  if (!await diagram.isVisible()) throw new Error('Monitor must show the worker diagram');
  if (await nodeB.getAttribute('aria-pressed') !== 'true') throw new Error('Learning must preserve worker selection');
  await page.getByRole('button', {name: 'Follow live policy'}).click();
  await page.waitForFunction(() => window.workerQuery === null);
  await page.evaluate(a => window.publishWorkers([a], a), a);
  await nodeB.waitFor({state: 'detached'});
  if (await nodeA.getAttribute('aria-pressed') !== 'true') throw new Error('The first remaining worker must be selected');
  await page.evaluate(() => window.publishWorkers([], null));
  await page.getByText('Waiting for an available worker.').waitFor();
  await page.evaluate(b => window.publishWorkers([b], b), b);
  if (await nodeB.getAttribute('aria-pressed') !== 'true') throw new Error('New worker must be selected when none remains');
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Diagram overflows mobile viewport');
  return {keyboardSelection: true, removal: true, autoSelection: true, mobile: true};
}
