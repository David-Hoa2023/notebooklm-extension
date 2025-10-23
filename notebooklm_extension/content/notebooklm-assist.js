// src/content/notebooklm-assist.js
// Minimal, opt‑in assist: tries to focus the "Add sources" field in NotebookLM.
// No auto-paste. No data exfiltration. Best-effort only.

(() => {
  'use strict';
  const LOG = false;
  const log = (...a) => { if (LOG) console.log('[NotebookLM Assist]', ...a); };

  chrome.storage.local.get('settings').then(({ settings }) => {
    if (!settings?.assistEnabled) {
      log('assist disabled');
      return;
    }

    const MAX_MS = 15000;
    const INTERVAL = 750;
    const start = Date.now();
    let clickedOnce = false;

    const timer = setInterval(() => {
      if (Date.now() - start > MAX_MS) {
        clearInterval(timer);
        return;
      }
      if (document.visibilityState === 'hidden') return;
      if (focusAddSources()) {
        clearInterval(timer);
      }
    }, INTERVAL);

    // Allow explicit re-trigger from popup after opening the tab.
    chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
      if (msg?.type === 'ASSIST_FOCUS') {
        const ok = focusAddSources();
        sendResponse?.({ ok });
      }
    });

    function focusAddSources() {
      // 1) If the field is already present, just focus it.
      const input = findAddSourcesInput();
      if (input) {
        input.focus({ preventScroll: false });
        placeCaretEnd(input);
        log('focused existing input');
        return true;
      }

      // 2) Otherwise, try to open the Add sources UI once, then focus.
      if (!clickedOnce) {
        const btn = findAddSourcesButton();
        if (btn) {
          clickedOnce = true;
          btn.click(); // Open the dialog/panel; user opted in to allow this small assist.
          log('clicked Add sources button');
          setTimeout(() => {
            const i2 = findAddSourcesInput();
            if (i2) {
              i2.focus({ preventScroll: false });
              placeCaretEnd(i2);
              log('focused input after opening panel');
            }
          }, 500);
        }
      }
      return false;
    }

    function findAddSourcesInput(root = document) {
      // Common cases: input/textarea/contenteditable with meaningful labels/placeholders.
      const selectors = [
        'input[placeholder*="source" i]',
        'input[placeholder*="link" i]',
        'input[aria-label*="source" i]',
        'input[aria-label*="link" i]',
        'textarea[placeholder*="source" i]',
        'textarea[placeholder*="link" i]',
        'textarea[aria-label*="source" i]',
        'textarea[aria-label*="link" i]',
        '[contenteditable="true"][aria-label*="source" i]',
        '[contenteditable="true"][data-placeholder*="source" i]'
      ];
      for (const sel of selectors) {
        const el = root.querySelector(sel);
        if (el && isVisible(el)) return el;
      }
      // Material components with open shadow roots (best-effort).
      const hosts = root.querySelectorAll?.('md-outlined-text-field, md-filled-text-field, mdc-text-field');
      for (const host of hosts) {
        const sr = host.shadowRoot;
        if (!sr) continue;
        const el = sr.querySelector('input, textarea');
        if (el && isVisible(host)) return el;
      }
      // Search inside dialogs
      const dialogs = root.querySelectorAll?.('[role="dialog"], dialog');
      for (const d of dialogs) {
        const found = findAddSourcesInput(d);
        if (found) return found;
      }
      return null;
    }

    function findAddSourcesButton(root = document) {
      const re = /add\s+sources?/i;
      const btns = root.querySelectorAll?.('button, [role="button"]');
      for (const b of btns) {
        const text = (b.textContent || '').trim();
        const aria = (b.getAttribute('aria-label') || '').trim();
        if (re.test(text) || re.test(aria)) return b;
      }
      // Heuristic: a "+" near a "Sources" heading
      const headings = root.querySelectorAll?.('h1, h2, h3, [role="heading"]');
      for (const h of headings) {
        if (/sources/i.test(h.textContent || '')) {
          const maybe = h.closest('*')?.querySelector?.('button, [role="button"]');
          if (maybe) return maybe;
        }
      }
      return null;
    }

    function isVisible(el) {
      const rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden';
    }

    function placeCaretEnd(el) {
      try {
        if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
          const v = el.value;
          el.value = ''; el.value = v; // move caret to end
        } else if (el.isContentEditable) {
          const range = document.createRange();
          range.selectNodeContents(el);
          range.collapse(false);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }
      } catch {}
    }
  });
})();
