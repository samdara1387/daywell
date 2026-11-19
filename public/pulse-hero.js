'use strict';

// The first screen's hero uses Money Theory's saved transactions, without changing records.
// This browser code draws and connects the chart; the Python server still owns the data.
const DaywellPulse = (() => {
  const model = typeof module !== 'undefined' ? require('./monthly-compare.js') : DaywellMonthChart;
  const shortNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const longNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  let displayYear = null;
  let lastSelectedYear = null;

  // Browsing years changes only the hero until a month or report is selected.
  function yearFor(selectedDate) {
    const year = Number(selectedDate.slice(0, 4));
    if (displayYear === null || lastSelectedYear !== year) displayYear = year;
    lastSelectedYear = year;
    return displayYear;
  }

  // Compare recorded expenses with the preceding month; avoid a false percentage when prior data is missing.
  function comparison(transactions, row, formatMoney) {
    const previous = new Date(`${row.month}-01T12:00:00`);
    previous.setMonth(previous.getMonth() - 1);
    const key = `${previous.getFullYear()}-${String(previous.getMonth() + 1).padStart(2, '0')}`;
    const prior = transactions.filter(item => item.type === 'expense' && item.date?.startsWith(key));
    const priorExpense = prior.reduce((sum, item) => sum + item.amount, 0);
    if (!prior.length) return {short: 'No prior data', detail: `No expenses recorded in ${longNames[previous.getMonth()]}.`};
    if (!row.count) return {short: 'No entries yet', detail: `No entries recorded in ${longNames[Number(row.month.slice(5)) - 1]}.`};
    const difference = row.expense - priorExpense;
    const percent = priorExpense ? Math.round(Math.abs(difference) / priorExpense * 100) : null;
    if (difference === 0) return {short: 'No change', detail: `The two months have the same recorded spending.`};
    return {
      short: `${difference < 0 ? '↓' : '↑'} ${percent === null ? formatMoney(Math.abs(difference)) : percent + '%'}`,
      detail: `${formatMoney(Math.abs(difference))} ${difference < 0 ? 'less' : 'more'} recorded spending than ${longNames[previous.getMonth()]}.`,
    };
  }

  // Create the chart, the selected-month facts, and links to related Money Theory tools.
  function render(transactions, selectedDate, formatMoney, currency) {
    const year = yearFor(selectedDate);
    const rows = model.monthlyTotals(transactions, year);
    const maximum = Math.max(1, ...rows.flatMap(row => [row.income, row.expense]));
    const selectedYear = Number(selectedDate.slice(0, 4));
    const activeIndex = year === selectedYear
      ? Number(selectedDate.slice(5, 7)) - 1
      : Math.max(0, rows.findLastIndex(row => row.count));
    const active = rows[activeIndex];
    const insight = comparison(transactions, active, formatMoney);
    const hasYearRecords = rows.some(row => row.count);
    const yearIncome = rows.reduce((sum, row) => sum + row.income, 0);
    const yearExpense = rows.reduce((sum, row) => sum + row.expense, 0);

    return `<section class="card pulse-hero" id="pulse-hero" data-active-month="${active.month}" data-year="${year}" aria-labelledby="pulse-title">
      <div class="pulse-chart-side">
        <div class="pulse-heading"><div><span class="eyebrow">THE YEAR IN VIEW</span><h2 id="pulse-title">Your money has <em>a rhythm.</em></h2>
          <p>Income and expenses from your records. Choose a month to see its story.</p></div>
          <div class="pulse-year" aria-label="Comparison year"><button type="button" data-pulse-year="-1" aria-label="Previous comparison year">‹</button><strong aria-live="polite">${year}</strong><button type="button" data-pulse-year="1" aria-label="Next comparison year">›</button></div></div>
        <div class="pulse-legend"><span><i class="income"></i>Income</span><span><i class="expense"></i>Expenses</span><small>${currency} · recorded amounts</small></div>
        <div class="pulse-scroll" role="region" aria-label="Income and expenses by month" tabindex="0"><div class="pulse-plot">
          ${rows.map((row, index) => `<button type="button" class="pulse-month ${index === activeIndex ? 'active' : ''} ${row.count ? '' : 'empty'}" data-pulse-month="${row.month}" aria-label="${longNames[index]} ${year}: ${formatMoney(row.income)} income, ${formatMoney(row.expense)} expenses${row.count ? '' : ', no entries recorded'}" aria-pressed="${index === activeIndex}" title="${longNames[index]} · income ${formatMoney(row.income)} · expenses ${formatMoney(row.expense)}"><span class="pulse-bars"><i class="income" style="--height:${row.income ? Math.max(2, row.income / maximum * 100) : 0}%"></i><i class="expense" style="--height:${row.expense ? Math.max(2, row.expense / maximum * 100) : 0}%"></i></span><span class="pulse-month-label">${shortNames[index]}</span></button>`).join('')}
        </div></div>
        <div class="pulse-chart-foot"><span>${hasYearRecords ? `${formatMoney(yearIncome)} income · ${formatMoney(yearExpense)} expenses in ${year}` : `No entries recorded in ${year}. Add one to start your picture.`}</span><button type="button" data-pulse-year-report>View ${year} report ↗</button></div>
        <details class="pulse-exact"><summary>View exact amounts for all 12 months</summary><div class="table-wrap"><table><thead><tr><th>MONTH</th><th>INCOME</th><th>EXPENSES</th><th>NET</th></tr></thead><tbody>${rows.map((row, index) => `<tr><th scope="row">${longNames[index]}</th><td>${formatMoney(row.income)}</td><td>${formatMoney(row.expense)}</td><td>${formatMoney(row.income - row.expense)}</td></tr>`).join('')}</tbody></table></div></details>
      </div>
      <div class="pulse-inspector"><span class="eyebrow">SELECTED MONTH · ${longNames[activeIndex].toUpperCase()} ${year}</span><strong class="pulse-big">${formatMoney(active.expense)}</strong><p>recorded spending this month${active.count ? ` · ${active.count} ${active.count === 1 ? 'entry' : 'entries'}` : ' · no entries yet'}</p>
        <button type="button" class="pulse-fact" data-pulse-filter="income"><span><i class="income"></i>Income <small>See income entries ↗</small></span><strong>${formatMoney(active.income)}</strong></button>
        <button type="button" class="pulse-fact" data-pulse-filter="expense"><span><i class="expense"></i>Expenses <small>See purchases ↗</small></span><strong>${formatMoney(active.expense)}</strong></button>
        <button type="button" class="pulse-fact pulse-change" data-pulse-comparison><span>Compared with previous month <small>${insight.detail}</small></span><strong>${insight.short}</strong></button>
        <button type="button" class="pulse-main-action" data-pulse-filter="all">See ${longNames[activeIndex]} transactions ↗</button>
        <div class="pulse-quick-actions"><button type="button" data-import>↑ Import statement</button><button type="button" data-action="transaction">+ Add expense</button></div>
        <small class="pulse-disclaimer">Recorded cash flow, not a verified bank balance. Months may have incomplete records.</small>
      </div>
    </section>`;
  }

  // Connect each visual control to a real page or an updated shared month.
  function bind(actions) {
    const root = document.getElementById('pulse-hero');
    if (!root) return;
    // On narrow screens, start with the selected month visible inside the chart.
    // Setting this container's scrollLeft does not move the whole page sideways.
    const scroll = root.querySelector('.pulse-scroll');
    const active = root.querySelector('.pulse-month.active');
    if (scroll && active && scroll.scrollWidth > scroll.clientWidth) {
      scroll.scrollLeft = Math.max(0, active.offsetLeft - scroll.clientWidth / 2 + active.clientWidth / 2);
    }
    root.addEventListener('click', event => {
      const month = event.target.closest('[data-pulse-month]');
      if (month) return actions.month(month.dataset.pulseMonth);
      const year = event.target.closest('[data-pulse-year]');
      if (year) {
        displayYear = Math.max(1900, Math.min(9998, displayYear + Number(year.dataset.pulseYear)));
        return actions.rerender();
      }
      const filter = event.target.closest('[data-pulse-filter]');
      if (filter) return actions.filter(root.dataset.activeMonth, filter.dataset.pulseFilter);
      if (event.target.closest('[data-pulse-comparison]')) return actions.comparison(root.dataset.activeMonth);
      if (event.target.closest('[data-pulse-year-report]')) return actions.yearReport(root.dataset.year);
    });
  }

  return {render, bind, comparison};
})();

// Export pure rendering logic for regression checks without a browser.
if (typeof module !== 'undefined') module.exports = DaywellPulse;
