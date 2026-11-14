'use strict';

// Keep a small history of Daywell screens and dates. This never leaves the app.
const DaywellAppHistory = (() => {
  const entries = [];
  let index = -1;
  let restoring = false;
  let restoreScreen = null;

  // A screen is identified by its page, chosen date, and day/month/year view.
  const key = item => `${item.page}|${item.selected}|${item.period}`;

  // Grey out arrows that have nowhere useful to go.
  function updateButtons() {
    if (typeof document === 'undefined') return;
    const back = document.getElementById('app-back');
    const forward = document.getElementById('app-forward');
    if (back) back.disabled = index <= 0;
    if (forward) forward.disabled = index >= entries.length - 1;
  }

  // Remember meaningful navigation while ignoring repeated renders of one screen.
  function record(page, selected, period) {
    const item = {page, selected, period};
    const value = key(item);
    if (restoring) {
      restoring = false;
      updateButtons();
      return;
    }
    if (index >= 0 && key(entries[index]) === value) return updateButtons();
    if (index > 0 && key(entries[index - 1]) === value) {
      index--;
      return updateButtons();
    }
    if (index + 1 < entries.length && key(entries[index + 1]) === value) {
      index++;
      return updateButtons();
    }
    entries.splice(index + 1);
    entries.push(item);
    if (entries.length > 80) entries.shift();
    index = entries.length - 1;
    updateButtons();
  }

  // Restore a screen from our own app history, never a browser page outside Daywell.
  function move(direction) {
    const next = index + direction;
    if (next < 0 || next >= entries.length || !restoreScreen) return false;
    index = next;
    restoring = true;
    restoreScreen({...entries[index]});
    updateButtons();
    return true;
  }

  // Connect the top-left buttons after the page loads.
  function bind(restore) {
    restoreScreen = restore;
    document.getElementById('app-back').onclick = () => move(-1);
    document.getElementById('app-forward').onclick = () => move(1);
    updateButtons();
  }

  return {record, move, bind, canBack: () => index > 0,
    canForward: () => index >= 0 && index < entries.length - 1};
})();

if (typeof module !== 'undefined') module.exports = DaywellAppHistory;
