// Playwright run-code against the deployed server. Reads existing worker telemetry only.
async page => {
  await page.goto(new URL(page.url()).origin);
  await page.waitForFunction(() => document.querySelector('#status').dataset.state === 'live', null, {timeout: 90000});
  await page.getByRole('button', {name: 'Freeze view'}).click();
  const context = await page.locator('#sample-context').innerText();
  const sequence = Number(context.match(/published #(\d+)/)[1]);
  await page.getByRole('button', {name: 'Timeline', exact: true}).click();
  const event = page.locator('#events button').filter({hasText: new RegExp(`^#${sequence} ·`)});
  const [response] = await Promise.all([
    page.waitForResponse(response => response.url().includes('/api/decision?')),
    event.click(),
  ]);
  const {sample, metadata} = await response.json();
  await page.waitForFunction(() => document.querySelector('#sample-context').textContent.includes('Replay'));
  await page.getByRole('button', {name: 'Inspect in monitor'}).click();
  const action = await page.locator('.choice').innerText();
  if (action !== sample.action.replaceAll('_', ' ')) throw new Error('Replay action differs from the recorded sample');
  const identity = await page.locator('#identity').innerText();
  for (const value of [sample.game_pid, sample.worker_pid, sample.model_revision]) {
    if (!identity.includes(String(value))) throw new Error('Captured identity is missing from monitor');
  }
  await page.getByRole('button', {name: 'Neural activity'}).click();
  const activation = await page.locator('#activation-detail').innerText();
  if (!activation.includes(metadata.input_labels[0] + ' = ' + sample.input[0])) throw new Error('Visible input differs from capture');
  const matrices = await page.locator('#matrix option').count();
  if (matrices) {
    await page.locator('#load-weights').click();
    await page.waitForFunction(() => !document.querySelector('#weight-heat').hidden);
  }
  await page.getByRole('button', {name: 'Learning', exact: true}).click();
  await page.getByRole('heading', {name: 'Performance by cohort and level'}).waitFor();
  const results = await page.locator('#learning-results table').first().locator('tbody tr').count();
  return {game: sample.game_pid, worker: sample.worker_pid, episode: sample.episode, sequence, action,
    phase: sample.phase, stage: sample.stage, revision: sample.model_revision,
    probability: sample.tool_probabilities[sample.tool], inputCount: sample.input.length,
    input0: sample.input[0], hidden0: sample.hidden[0], matrices, results};
}
