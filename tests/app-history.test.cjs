const test = require('node:test');
const assert = require('node:assert/strict');
const history = require('../public/app-history.js');

test('back and forward follow screens and chosen dates, without duplicate renders', () => {
  const restored = [];
  global.document = {
    getElementById(id) { return {set disabled(value) { /* no browser needed */ }, set onclick(value) { /* no browser needed */ }}; },
  };
  history.bind(item => {
    restored.push(item);
    history.record(item.page, item.selected, item.period);
  });
  history.record('overview', '2026-10-31', 'month');
  history.record('money', '2026-10-31', 'month');
  history.record('money', '2026-09-30', 'month');
  history.record('money', '2026-09-30', 'month');
  assert.equal(history.canBack(), true);
  assert.equal(history.canForward(), false);
  assert.equal(history.move(-1), true);
  assert.deepEqual(restored.at(-1), {page:'money', selected:'2026-10-31', period:'month'});
  assert.equal(history.move(-1), true);
  assert.deepEqual(restored.at(-1), {page:'overview', selected:'2026-10-31', period:'month'});
  assert.equal(history.canBack(), false);
  assert.equal(history.move(1), true);
  assert.deepEqual(restored.at(-1), {page:'money', selected:'2026-10-31', period:'month'});
  delete global.document;
});
