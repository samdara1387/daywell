const test = require('node:test');
const assert = require('node:assert/strict');
const statements = require('../public/statement-model.js');

test('statement preview selects purchases and excludes payments and existing expenses', () => {
  const lines = [
    'Statement date Oct 31, 2026',
    'Currency CAD',
    'Oct 05 Grocery Store 12.34',
    'Oct 06 Payment received 20.00',
    'Oct 07 Coffee Shop 5.67',
  ];
  const history = [{date:'2026-10-05', type:'expense', amount:1234, note:'Grocery Store'}];
  const preview = statements.pdfAutoPlan(lines, 'CAD', history);
  assert.equal(preview.end, '2026-10-31');
  assert.equal(preview.rows.length, 3);
  assert.deepEqual(preview.selected.map(row => [row.date, row.note, row.amount, row.category]), [
    ['2026-10-07', 'Coffee Shop', 567, 'Dining out'],
  ]);
  assert.equal(preview.rows[0].duplicate, true);
  assert.equal(preview.rows[0].selected, false);
  assert.match(preview.rows[1].reason, /Card payment/);
});

test('a different statement currency blocks automatic selection', () => {
  const preview = statements.pdfAutoPlan([
    'Statement date Oct 31, 2026', 'Currency USD', 'Oct 05 Grocery Store 12.34',
  ], 'CAD');
  assert.equal(preview.currencyMismatch, true);
  assert.equal(preview.rows.length, 1);
  assert.deepEqual(preview.selected, []);
});

test('non-statement documents and yearless rows without a statement date stay out', () => {
  const resume = statements.pdfAutoPlan([
    'Education', 'Technical Skills', 'Experience', 'Projects',
    'Oct 05 Grocery Store 12.34',
  ], 'CAD');
  assert.equal(resume.documentType, 'resume');
  assert.deepEqual(resume.selected, []);
  const undated = statements.pdfAutoPlan(['Oct 05 Grocery Store 12.34'], 'CAD');
  assert.equal(undated.rows.length, 1);
  assert.deepEqual(undated.selected, []);
});

test('CSV reader preserves quoted merchant names and exact cents', () => {
  const rows = statements.csv('Date,Description,Amount\n2026-10-05,"Coffee, Bakery",12.34\n');
  assert.deepEqual(rows[1], ['2026-10-05', 'Coffee, Bakery', '12.34']);
  assert.equal(statements.amount(rows[1][2]), 1234);
  assert.equal(statements.parseDate('2026-02-30'), '');
});
