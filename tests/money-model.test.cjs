const test = require('node:test');
const assert = require('node:assert/strict');
const model = require('../public/money-model.js');

test('monthly snapshot groups spending and respects the chosen day', () => {
  const state = {transactions: [
    {date:'2026-10-03', type:'income', amount:30000},
    {date:'2026-10-04', type:'expense', category:'Food', amount:5000},
    {date:'2026-10-05', type:'expense', category:'Travel', amount:4000},
    {date:'2026-10-05', type:'expense', category:'Bills', amount:3000},
    {date:'2026-10-05', type:'expense', category:'Health', amount:2000},
    {date:'2026-10-06', type:'expense', category:'Food', amount:9000},
    {date:'2026-09-30', type:'expense', category:'Food', amount:7000},
  ]};
  const result = model.snapshot(state, '2026-10-05');
  assert.equal(result.income, 30000);
  assert.equal(result.expense, 14000);
  assert.equal(result.net, 16000);
  assert.deepEqual(result.nodes.map(node => [node.name, node.amount]), [
    ['Food', 5000], ['Travel', 4000], ['Bills', 3000],
    ['Other spending', 2000], ['Net remainder', 16000],
  ]);
});

test('calendar shows each day in the selected month and its purchases', () => {
  const state = {transactions: [
    {date:'2024-02-29', type:'expense', amount:1200},
    {date:'2024-02-29', type:'income', amount:4000},
    {date:'2024-03-01', type:'expense', amount:900},
  ]};
  const result = model.calendar(state, '2024-02-29');
  assert.equal(result.days.length, 29);
  assert.deepEqual(result.days.at(-1), {
    date:'2024-02-29', expense:1200, income:4000, count:2, inScope:true,
  });
  assert.equal(result.total, 1200);
  assert.equal(result.biggest.date, '2024-02-29');
});

test('scenario calculates an attainable savings goal from a spending reduction', () => {
  const result = model.scenario(20000, 25, {saved:8000, target:12000});
  assert.equal(result.reduction, 5000);
  assert.equal(result.limit, 15000);
  assert.deepEqual(result.impact, {
    before:66, after:100, saved:13000, remaining:0, complete:true,
  });
  assert.throws(() => model.scenario(20000, 51, null), /Invalid scenario/);
});
