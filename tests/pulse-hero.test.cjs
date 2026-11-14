const test = require('node:test');
const assert = require('node:assert/strict');
const pulse = require('../public/pulse-hero.js');

const money = cents => `CA$${(cents / 100).toFixed(2)}`;

test('the first card uses twelve real paired months and useful destinations', () => {
  const html = pulse.render([
    {date: '2026-09-01', type: 'income', amount: 300000},
    {date: '2026-09-02', type: 'expense', amount: 90000},
    {date: '2026-10-03', type: 'expense', amount: 20000},
  ], '2026-10-31', money, 'CAD');
  assert.equal((html.match(/data-pulse-month=/g) || []).length, 12);
  assert.match(html, /October 2026: CA\$0\.00 income, CA\$200\.00 expenses/);
  assert.match(html, /data-pulse-filter="income"/);
  assert.match(html, /data-pulse-filter="expense"/);
  assert.match(html, /data-pulse-comparison/);
  assert.match(html, /data-pulse-year-report/);
  assert.match(html, /data-import/);
  assert.match(html, /View exact amounts for all 12 months/);
});

test('empty records show a setup path without claiming there was no spending', () => {
  const html = pulse.render([], '2026-10-31', money, 'CAD');
  assert.match(html, /No entries recorded in 2026/);
  assert.match(html, /No prior data/);
  assert.match(html, /Add one to start your picture/);
});

test('comparison does not make a percentage from missing prior records', () => {
  const result = pulse.comparison([], {month: '2026-10', expense: 1500, count: 1}, money);
  assert.equal(result.short, 'No prior data');
});
