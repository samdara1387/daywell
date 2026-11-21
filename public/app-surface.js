'use strict';

// Keep the browser's long right-click menu off app panels and charts.
// Text fields retain their native menu for paste, spelling, and accessibility.
document.addEventListener('contextmenu', event => {
  const target = event.target;
  if (target instanceof Element && target.closest(
    'input, textarea, select, [role="textbox"], [contenteditable]:not([contenteditable="false"])'
  )) return;
  event.preventDefault();
});
