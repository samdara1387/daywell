const test = require('node:test');
const assert = require('node:assert/strict');
const chart = require('../public/monthly-compare.js');

test('each month keeps income and expenses separate in exact cents', () => {
  const rows = chart.monthlyTotals([
    {date: '2026-01-01', type: 'income', amount: 100001},
    {date: '2026-01-02', type: 'expense', amount: 1999},
    {date: '2026-02-01', type: 'expense', amount: 2501},
    {date: '2025-01-01', type: 'expense', amount: 9000},
  ], 2026);
  assert.equal(rows.length, 12);
  assert.deepEqual([rows[0].income, rows[0].expense, rows[0].count], [100001, 1999, 2]);
  assert.deepEqual([rows[1].income, rows[1].expense, rows[1].count], [0, 2501, 1]);
  assert.equal(rows[11].count, 0);
});

test('overview chart exposes twelve selectable months and exact values', () => {
  const html = chart.render([{date: '2026-10-05', type: 'expense', amount: 13539}],
    '2026-10-31', cents => `CA$${(cents / 100).toFixed(2)}`, 'CAD');
  assert.equal((html.match(/data-compare-month=/g) || []).length, 12);
  assert.match(html, /October 2026: income CA\$0\.00, expenses CA\$135\.39/);
  assert.match(html, /aria-pressed="true"/);
  assert.match(html, /View exact amounts for all 12 months/);
});
