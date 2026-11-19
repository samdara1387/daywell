'use strict';

// This chart uses the same transaction records as the rest of Money Theory.
// Money stays in integer cents until the existing money() formatter displays it.
const DaywellMonthChart = (() => {
  const shortNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const longNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  let displayYear = null;
  let lastSelectedYear = null;

  // Group recorded income and expenses into twelve calendar months.
  function monthlyTotals(transactions, year) {
    const rows = Array.from({length: 12}, (_, index) => ({
      month: `${year}-${String(index + 1).padStart(2, '0')}`,
      income: 0,
      expense: 0,
      count: 0,
    }));
    for (const transaction of transactions) {
      if (!transaction.date?.startsWith(`${year}-`)) continue;
      const index = Number(transaction.date.slice(5, 7)) - 1;
      if (!Number.isInteger(index) || index < 0 || index > 11) continue;
      if (transaction.type !== 'income' && transaction.type !== 'expense') continue;
      rows[index][transaction.type] += transaction.amount;
      rows[index].count++;
    }
    return rows;
  }

  // Follow the shared month when the user changes to a different year elsewhere.
  function visibleYear(selectedDate) {
    const selectedYear = Number(selectedDate.slice(0, 4));
    if (displayYear === null || lastSelectedYear !== selectedYear) displayYear = selectedYear;
    lastSelectedYear = selectedYear;
    return displayYear;
  }

  // Build the accessible, paired-bar visual and a visible exact-value inspector.
  function render(transactions, selectedDate, formatMoney, currency) {
    const year = visibleYear(selectedDate);
    const rows = monthlyTotals(transactions, year);
    const maximum = Math.max(1, ...rows.flatMap(row => [row.income, row.expense]));
    const activeIndex = year === Number(selectedDate.slice(0, 4))
      ? Number(selectedDate.slice(5, 7)) - 1
      : Math.max(0, rows.findLastIndex(row => row.count > 0));
    const active = rows[activeIndex];
    const priorMonth = new Date(`${active.month}-01T12:00:00`);
    priorMonth.setMonth(priorMonth.getMonth() - 1);
    const priorKey = `${priorMonth.getFullYear()}-${String(priorMonth.getMonth() + 1).padStart(2, '0')}`;
    const priorExpense = transactions.filter(t => t.type === 'expense' && t.date?.startsWith(priorKey))
      .reduce((sum, t) => sum + t.amount, 0);
    const yearExpense = rows.reduce((sum, row) => sum + row.expense, 0);
    const yearIncome = rows.reduce((sum, row) => sum + row.income, 0);
    const noRecords = !rows.some(row => row.count);
    const change = active.expense - priorExpense;
    const changeText = !active.count && !priorExpense
      ? 'No entries recorded for this month or the month before.'
      : `${formatMoney(Math.abs(change))} ${change < 0 ? 'less' : change > 0 ? 'more' : 'difference'} in recorded spending than ${longNames[priorMonth.getMonth()]}.`;

    return `<section class="card month-compare" id="monthly-comparison" aria-labelledby="month-compare-title">
      <div class="month-compare-head">
        <div><span class="eyebrow">THE YEAR IN MOTION</span><h2 id="month-compare-title">How your months compare<span class="accent-dot">.</span></h2>
          <p>One income bar and one expense bar for each month. Select a month to explore it across Money Theory.</p></div>
        <div class="month-compare-controls"><button type="button" data-year-shift="-1" aria-label="Previous comparison year">‹</button>
          <strong aria-live="polite">${year}</strong><button type="button" data-year-shift="1" aria-label="Next comparison year">›</button></div>
      </div>
      <div class="month-compare-key" aria-label="Chart colors"><span><i class="income"></i>Income</span><span><i class="expense"></i>Expenses</span><small>Recorded amounts · ${currency}</small></div>
      <div class="month-compare-scroll" role="region" aria-label="Monthly comparison chart" tabindex="0">
        <div class="month-compare-plot" style="--chart-max:${maximum}">
          ${rows.map((row, index) => `<button type="button" class="month-pair ${index === activeIndex ? 'selected' : ''} ${row.count ? '' : 'no-entries'}" data-compare-month="${row.month}" aria-label="${longNames[index]} ${year}: income ${formatMoney(row.income)}, expenses ${formatMoney(row.expense)}${row.count ? '' : ', no entries recorded'}" aria-pressed="${index === activeIndex}" title="${longNames[index]}: income ${formatMoney(row.income)} · expenses ${formatMoney(row.expense)}">
            <span class="month-pair-bars"><i class="month-income" style="--bar-height:${row.income ? Math.max(2, row.income / maximum * 100) : 0}%"></i><i class="month-expense" style="--bar-height:${row.expense ? Math.max(2, row.expense / maximum * 100) : 0}%"></i></span>
            <span class="month-pair-label">${shortNames[index]}</span></button>`).join('')}
        </div>
      </div>
      <div class="month-compare-inspector">
        <div class="month-inspect-title"><span class="eyebrow">SELECTED MONTH</span><strong>${longNames[activeIndex]} ${year}</strong><small>${active.count ? `${active.count} recorded ${active.count === 1 ? 'entry' : 'entries'}` : 'No entries recorded'}</small></div>
        <div class="month-inspect-value"><span>Income</span><strong>${formatMoney(active.income)}</strong></div>
        <div class="month-inspect-value"><span>Expenses</span><strong>${formatMoney(active.expense)}</strong></div>
        <div class="month-inspect-value net"><span>Income − expenses</span><strong>${formatMoney(active.income - active.expense)}</strong></div>
      </div>
      <div class="month-compare-foot"><p>${changeText} ${noRecords ? 'Add income or expenses to start the comparison.' : `Across ${year}: ${formatMoney(yearIncome)} income and ${formatMoney(yearExpense)} expenses.`} These are recorded entries, not a bank balance.</p>
        <a class="text-button" href="#money">Open transactions ↗</a></div>
      <details class="month-compare-table"><summary>View exact amounts for all 12 months</summary><div class="table-wrap"><table><thead><tr><th>MONTH</th><th>INCOME</th><th>EXPENSES</th><th>NET</th></tr></thead><tbody>
        ${rows.map((row, index) => `<tr><th scope="row">${longNames[index]}</th><td>${formatMoney(row.income)}</td><td>${formatMoney(row.expense)}</td><td>${formatMoney(row.income - row.expense)}</td></tr>`).join('')}
      </tbody></table></div></details>
    </section>`;
  }

  // Button events update the shared month or browse years without changing records.
  function bind(onMonthSelected, onRerender) {
    const root = document.getElementById('monthly-comparison');
    if (!root) return;
    root.addEventListener('click', event => {
      const month = event.target.closest('[data-compare-month]');
      if (month) {
        onMonthSelected(month.dataset.compareMonth);
        return;
      }
      const year = event.target.closest('[data-year-shift]');
      if (year) {
        displayYear = Math.max(1900, Math.min(9998, displayYear + Number(year.dataset.yearShift)));
        onRerender();
      }
    });
  }

  return {monthlyTotals, render, bind};
})();

// The pure totals function can also be checked by Node tests without a browser.
if (typeof module !== 'undefined') module.exports = DaywellMonthChart;
