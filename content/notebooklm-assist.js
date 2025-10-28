// src/content/notebooklm-assist.js
// Enhanced NotebookLM integration: handles notebook selection, creation, and programmatic text insertion.
// Supports both new notebook creation and adding to existing notebooks.

(() => {
  'use strict';
  const LOG = true; // Enable logging for debugging
  const log = (...a) => { if (LOG) console.log('[NotebookLM Assist]', ...a); };
  
  // Prevent duplicate script loading
  if (window.notebookLMExtensionLoaded) {
    log('Content script already loaded, skipping...');
    return;
  }
  
  // Mark that the content script has loaded
  window.notebookLMExtensionLoaded = true;
  document.documentElement.setAttribute('data-notebooklm-extension', 'loaded');
  
  log('Content script loaded and initialized at:', new Date().toISOString());
  
  // Global state
  const state = {
    settings: { assistEnabled: false },
    clickedOnce: false
  };

  // Message listener should always be registered, not just when assistEnabled
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    log('Received message:', msg?.type, 'from:', sender?.tab?.id || 'popup');
    
    try {
      if (msg?.type === 'ASSIST_FOCUS') {
        const ok = focusAddSources();
        sendResponse?.({ ok });
        return false; // Synchronous response
      } else if (msg?.type === 'INSERT_CONTENT') {
        log('Starting content insertion...');
        handleContentInsertion(msg.content, msg.notebookId, msg.createNew).then(result => {
          log('Content insertion completed:', result);
          sendResponse(result);
        }).catch(error => {
          log('Content insertion error:', error);
          sendResponse({ ok: false, error: error.message });
        });
        return true; // Keep channel open for async response
      } else if (msg?.type === 'GET_NOTEBOOKS') {
        try {
          const notebooks = getNotebooksList();
          log('Found notebooks:', notebooks.length);
          sendResponse({ ok: true, notebooks });
        } catch (error) {
          log('Error getting notebooks:', error);
          sendResponse({ ok: false, error: error.message, notebooks: [] });
        }
        return false; // Synchronous response
      } else if (msg?.type === 'SELECT_NOTEBOOK') {
        try {
          const result = selectNotebook(msg.notebookId);
          sendResponse(result);
        } catch (error) {
          sendResponse({ ok: false, error: error.message });
        }
        return false; // Synchronous response
      } else if (msg?.type === 'CREATE_NOTEBOOK') {
        log('Creating new notebook...');
        createNewNotebook().then(result => {
          log('Notebook creation completed:', result);
          sendResponse(result);
        }).catch(error => {
          log('Notebook creation error:', error);
          sendResponse({ ok: false, error: error.message });
        });
        return true; // Keep channel open for async response
      } else {
        log('Unknown message type:', msg?.type);
        sendResponse({ ok: false, error: 'Unknown message type' });
        return false;
      }
    } catch (error) {
      log('Error handling message:', error);
      sendResponse({ ok: false, error: error.message });
      return false;
    }
  });
  
  // Load settings and potentially start auto-assist
  chrome.storage.local.get('settings').then(({ settings }) => {
    if (settings) {
      Object.assign(state.settings, settings);
    }
    
    if (state.settings.assistEnabled) {
      log('Auto-assist enabled, starting timer');
      startAutoAssist();
    } else {
      log('Auto-assist disabled');
    }
  });
  
  function startAutoAssist() {
    const MAX_MS = 15000;
    const INTERVAL = 750;
    const start = Date.now();

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
  }

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
    if (!state.clickedOnce) {
      const btn = findAddSourcesButton();
      if (btn) {
        state.clickedOnce = true;
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
    log('Looking for URL input field...');
    
    // Priority 1: Look for the exact "Paste URLs" placeholder first (including with asterisk)
    const pasteUrlsSelectors = [
      'textarea[placeholder*="Paste URLs*"]',
      'textarea[placeholder*="Paste URLs" i]',
      'textarea[placeholder*="paste urls" i]',
      'input[placeholder*="Paste URLs*"]',
      'input[placeholder*="Paste URLs" i]',
      'input[placeholder*="paste urls" i]'
    ];
    
    for (const sel of pasteUrlsSelectors) {
      const elements = root.querySelectorAll(sel);
      for (const el of elements) {
        if (el && isVisible(el)) {
          log('Found "Paste URLs" textarea:', el.placeholder);
          return el;
        }
      }
    }
    
    // Priority 2: Look for other URL-related placeholders
    const urlSelectors = [
      // Website-specific selectors
      'textarea[placeholder*="website" i]',
      'textarea[placeholder*="url" i]',
      'textarea[placeholder*="link" i]',
      'input[placeholder*="website" i]',
      'input[placeholder*="url" i]',
      'input[placeholder*="link" i]',
      // Source-specific selectors
      'textarea[placeholder*="source" i]',
      'input[placeholder*="source" i]',
      'textarea[aria-label*="source" i]',
      'input[aria-label*="source" i]',
      'textarea[aria-label*="link" i]',
      'input[aria-label*="link" i]',
      'textarea[aria-label*="website" i]',
      'input[aria-label*="website" i]',
      '[contenteditable="true"][aria-label*="source" i]',
      '[contenteditable="true"][aria-label*="website" i]',
      '[contenteditable="true"][data-placeholder*="source" i]'
    ];
    
    for (const sel of urlSelectors) {
      const elements = root.querySelectorAll(sel);
      for (const el of elements) {
        if (el && isVisible(el)) {
          const placeholder = (el.placeholder || '').toLowerCase();
          const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
          
          log('Found URL-related input:', el.tagName, 'placeholder:', placeholder);
          
          // Prioritize elements that are likely for website input
          if (placeholder.includes('website') || placeholder.includes('url') || 
              ariaLabel.includes('website') || ariaLabel.includes('url')) {
            return el;
          }
        }
      }
    }
    
    // Priority 3: Look for large textareas (likely for URL pasting)
    log('Looking for large textareas (likely for URL input)...');
    const textareas = root.querySelectorAll('textarea');
    for (const textarea of textareas) {
      if (isVisible(textarea)) {
        const rect = textarea.getBoundingClientRect();
        const placeholder = (textarea.placeholder || '').toLowerCase();
        
        log('Found textarea:', 'placeholder:', placeholder, 'size:', Math.round(rect.width), 'x', Math.round(rect.height));
        
        // If it's a reasonably large textarea (likely for URL pasting)
        if (rect.height > 100 && rect.width > 300) {
          log('Found large textarea, using as URL input field');
          return textarea;
        }
      }
    }
    
    // Priority 4: Look for any visible textarea/input after Website button is clicked
    log('Looking for any visible textarea/input as fallback...');
    const genericSelectors = [
      'textarea:not([style*="display: none"]):not([hidden])',
      'input[type="text"]:not([style*="display: none"]):not([hidden])',
      'input[type="url"]:not([style*="display: none"]):not([hidden])'
    ];
    
    for (const sel of genericSelectors) {
      const elements = root.querySelectorAll(sel);
      for (const el of elements) {
        if (el && isVisible(el)) {
          const placeholder = (el.placeholder || '').toLowerCase();
          log('Found generic input:', el.tagName, 'placeholder:', placeholder);
          
          // Return the first visible textarea (most likely for URL input)
          if (el.tagName.toLowerCase() === 'textarea') {
            return el;
          }
        }
      }
    }
    
    // Priority 5: Return any visible input as absolute fallback
    for (const sel of genericSelectors) {
      const elements = root.querySelectorAll(sel);
      for (const el of elements) {
        if (el && isVisible(el)) {
          const placeholder = (el.placeholder || '').toLowerCase();
          log('Using fallback input:', el.tagName, 'placeholder:', placeholder);
          
          if (el.tagName.toLowerCase() === 'input' && 
              ['text', 'url'].includes(el.type)) {
            return el;
          }
        }
      }
    }
    
    // Material components with open shadow roots (best-effort).
    const hosts = root.querySelectorAll?.('md-outlined-text-field, md-filled-text-field, mdc-text-field');
    for (const host of hosts) {
      const sr = host.shadowRoot;
      if (!sr) continue;
      const el = sr.querySelector('input, textarea');
      if (el && isVisible(host)) return el;
    }
    
    // Search inside dialogs and modals
    const containers = root.querySelectorAll?.('[role="dialog"], dialog, .modal, [aria-modal="true"]');
    for (const container of containers) {
      const found = findAddSourcesInput(container);
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

  function findWebsiteButton(root = document) {
    log('Looking for Website button...');
    
    // First, try to find all possible clickable elements
    const allButtons = root.querySelectorAll('button, [role="button"], [onclick], [style*="cursor: pointer"], [class*="button"]');
    log('Found', allButtons.length, 'total clickable elements');
    
    // Also look at ALL elements that contain "website" text
    const allElements = root.querySelectorAll('*');
    const websiteElements = [];
    
    allElements.forEach(el => {
      const text = (el.textContent || '').trim().toLowerCase();
      if (text === 'website' && isVisible(el)) {
        websiteElements.push(el);
      }
    });
    
    log('Found', websiteElements.length, 'elements with "website" text');
    
    // Look for "Website" button with different approaches
    const approaches = [
      // Approach 1: Exact text match (case insensitive)
      () => {
        for (const btn of allButtons) {
          const text = (btn.textContent || '').trim();
          if (text.toLowerCase() === 'website' && isVisible(btn)) {
            log('Found Website button via exact text match:', text);
            return btn;
          }
        }
        return null;
      },
      
      // Approach 2: Text includes "website"
      () => {
        for (const btn of allButtons) {
          const text = (btn.textContent || '').trim().toLowerCase();
          if (text.includes('website') && isVisible(btn)) {
            log('Found Website button via text includes:', text);
            return btn;
          }
        }
        return null;
      },
      
      // Approach 3: Check aria-label
      () => {
        for (const btn of allButtons) {
          const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
          if (aria.includes('website') && isVisible(btn)) {
            log('Found Website button via aria-label:', aria);
            return btn;
          }
        }
        return null;
      },
      
      // Approach 4: Look for buttons with website icons (SVG or specific classes)
      () => {
        for (const btn of allButtons) {
          if (!isVisible(btn)) continue;
          
          // Check if button has an icon and website-related content
          const hasIcon = btn.querySelector('svg, [class*="icon"], [class*="material"]');
          const text = (btn.textContent || '').trim().toLowerCase();
          
          if (hasIcon && text === 'website') {
            log('Found Website button via icon + text:', text);
            return btn;
          }
        }
        return null;
      },
      
      // Approach 5: Look for buttons in specific containers or with specific attributes
      () => {
        const selectors = [
          'button[data-testid*="website" i]',
          'button[title*="website" i]',
          '[role="button"][data-testid*="website" i]',
          '[role="button"][title*="website" i]'
        ];
        
        for (const selector of selectors) {
          try {
            const element = root.querySelector(selector);
            if (element && isVisible(element)) {
              log('Found Website button via selector:', selector);
              return element;
            }
          } catch (e) {
            // Continue if selector fails
          }
        }
        return null;
      },
      
      // Approach 6: Check any element that has "website" text and is clickable
      () => {
        for (const el of websiteElements) {
          // Check if this element is clickable or inside a clickable element
          const clickableParent = el.closest('button, [role="button"], [onclick]') || 
                                 (el.style.cursor === 'pointer' || getComputedStyle(el).cursor === 'pointer' ? el : null);
          
          if (clickableParent && isVisible(clickableParent)) {
            log('Found Website element with clickable parent:', el.textContent?.trim());
            return clickableParent;
          }
          
          // Check if the element itself seems clickable
          if (el.tagName.toLowerCase() === 'button' || 
              el.getAttribute('role') === 'button' ||
              el.onclick ||
              el.style.cursor === 'pointer' ||
              getComputedStyle(el).cursor === 'pointer') {
            log('Found clickable Website element:', el.textContent?.trim());
            return el;
          }
        }
        return null;
      },
      
      // Approach 7: Debug approach - look for any button that might be the website button
      () => {
        log('Debug: Listing all visible buttons with their text:');
        for (let i = 0; i < Math.min(allButtons.length, 20); i++) {
          const btn = allButtons[i];
          if (isVisible(btn)) {
            const text = (btn.textContent || '').trim();
            const aria = btn.getAttribute('aria-label') || '';
            const classes = btn.className || '';
            log(`Button ${i}: "${text}" | aria: "${aria}" | classes: "${classes}"`);
            
            // If we find a button that looks like it could be website-related
            if (text.toLowerCase().includes('web') || 
                aria.toLowerCase().includes('web') ||
                classes.toLowerCase().includes('web')) {
              log('Potential Website button found:', text);
              return btn;
            }
          }
        }
        return null;
      },
      
      // Approach 8: Try CSS selector approaches
      () => {
        const cssSelectors = [
          'button:contains("Website")',
          '[data-testid*="website"]',
          '[aria-describedby*="website"]',
          '[title*="website"]',
          'button[class*="website"]',
          '[role="button"][class*="website"]'
        ];
        
        for (const selector of cssSelectors) {
          try {
            const elements = root.querySelectorAll(selector);
            for (const el of elements) {
              if (isVisible(el)) {
                log('Found Website button via CSS selector:', selector);
                return el;
              }
            }
          } catch (e) {
            // Some selectors might not be supported
          }
        }
        return null;
      }
    ];
    
    // Try each approach
    for (let i = 0; i < approaches.length; i++) {
      try {
        const button = approaches[i]();
        if (button) {
          log(`Website button found using approach ${i + 1}`);
          return button;
        }
      } catch (e) {
        log(`Approach ${i + 1} failed:`, e.message);
      }
    }
    
    log('No Website button found after trying all approaches');
    return null;
  }

  function isVisible(el) {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  }

  function debugAvailableInputs() {
    log('=== DEBUG: Available inputs after Website button click ===');
    
    // Find all textareas
    const textareas = document.querySelectorAll('textarea');
    log(`Found ${textareas.length} textareas on page:`);
    textareas.forEach((ta, i) => {
      const visible = isVisible(ta);
      const placeholder = ta.placeholder || 'no placeholder';
      const value = ta.value || 'empty';
      const rect = ta.getBoundingClientRect();
      const size = `${Math.round(rect.width)}x${Math.round(rect.height)}`;
      log(`  Textarea ${i}: visible=${visible}, size=${size}, placeholder="${placeholder}", value="${value.substring(0, 50)}"`);
      
      // Highlight large textareas that are likely for URL input
      if (visible && rect.height > 100 && rect.width > 300) {
        log(`    *** LIKELY URL TEXTAREA *** Size: ${size}, placeholder: "${placeholder}"`);
      }
    });
    
    // Find all text inputs
    const inputs = document.querySelectorAll('input[type="text"], input[type="url"]');
    log(`Found ${inputs.length} text/url inputs on page:`);
    inputs.forEach((inp, i) => {
      const visible = isVisible(inp);
      const placeholder = inp.placeholder || 'no placeholder';
      const value = inp.value || 'empty';
      log(`  Input ${i}: visible=${visible}, placeholder="${placeholder}", value="${value.substring(0, 50)}"`);
    });
    
    // Look specifically for "Paste URLs" placeholder (including with asterisk)
    const pasteUrlElements = document.querySelectorAll('[placeholder*="Paste URLs"], [placeholder*="paste urls" i]');
    log(`Found ${pasteUrlElements.length} elements with "Paste URLs" placeholder:`);
    pasteUrlElements.forEach((el, i) => {
      const visible = isVisible(el);
      const tagName = el.tagName;
      const placeholder = el.placeholder;
      log(`  Paste URLs ${i}: ${tagName}, visible=${visible}, placeholder="${placeholder}"`);
    });
    
    log('=== END DEBUG ===');
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
    
  // Enhanced notebook management functions
  async function handleContentInsertion(content, notebookId, createNew) {
    try {
      log('Starting content insertion...', { notebookId, createNew, contentLength: content.length });
      
      // If creating new notebook
      if (createNew) {
        const createResult = await createNewNotebook();
        if (!createResult.ok) return createResult;
        notebookId = createResult.notebookId;
        log('Created new notebook:', notebookId);
        
        // Wait for new notebook to fully load
        log('Waiting for new notebook interface to load...');
        await new Promise(resolve => setTimeout(resolve, 2000));
      } else if (notebookId && notebookId !== 'new') {
        // Select existing notebook
        const selectResult = selectNotebook(notebookId);
        if (!selectResult.ok) return selectResult;
        log('Selected existing notebook:', notebookId);
        
        // Wait for existing notebook to load
        log('Waiting for existing notebook interface to load...');
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      
      // Wait for the source buttons to be available (Website, Link, etc.)
      log('Waiting for source selection interface to be ready...');
      await waitForSourceInterface();
      
      // MANDATORY STEP: Always look for and click the Website button first
      log('Looking for Website button to click...');
      const websiteBtn = findWebsiteButton();
      
      if (websiteBtn) {
        log('Found Website button, clicking it first...');
        
        // Try multiple clicking methods to ensure it works
        try {
          // Method 1: Simple click
          websiteBtn.click();
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // Method 2: Dispatch click event
          websiteBtn.dispatchEvent(new Event('click', { bubbles: true, cancelable: true }));
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // Method 3: MouseEvent
          const mouseEvent = new MouseEvent('click', {
            view: window,
            bubbles: true,
            cancelable: true,
            clientX: websiteBtn.getBoundingClientRect().left + 10,
            clientY: websiteBtn.getBoundingClientRect().top + 10
          });
          websiteBtn.dispatchEvent(mouseEvent);
          
          log('Website button clicked successfully');
        } catch (clickError) {
          log('Error clicking Website button:', clickError);
        }
        
        // Wait for the textarea to appear after clicking Website button
        log('Waiting for textarea to appear after Website button click...');
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        // Debug: List all textareas and inputs after clicking Website button
        debugAvailableInputs();
        
      } else {
        log('Website button not found, trying Add sources button...');
        
        // Fallback: Try to find and click "Add sources" button
        const addSourcesBtn = findAddSourcesButton();
        if (addSourcesBtn) {
          log('Found Add sources button, clicking...');
          addSourcesBtn.click();
          await new Promise(resolve => setTimeout(resolve, 2000));
        } else {
          log('No Add sources button found either');
        }
      }
      
      // Now look for the input field with smart waiting
      log('Looking for input field after clicking buttons...');
      let input = await waitForUrlInputField();
      
      if (!input) {
        log('Still no input found, waiting and trying again...');
        // Step 4: Wait a bit longer and try to find any textarea/input
        await new Promise(resolve => setTimeout(resolve, 2000));
        input = findAddSourcesInput();
      }
      
      if (input) {
        log('Found input field, inserting content...', input.tagName, input.placeholder);
        
        // Enhanced insertion with multiple methods
        if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
          // Method 1: Focus and clear
          input.focus();
          await new Promise(resolve => setTimeout(resolve, 100));
          
          // Method 2: Select all and replace
          input.select();
          input.value = '';
          
          // Method 3: Insert content with typing simulation
          input.value = content;
          
          // Method 4: Trigger comprehensive events
          const events = [
            new Event('focus', { bubbles: true }),
            new Event('input', { bubbles: true, cancelable: true }),
            new Event('change', { bubbles: true, cancelable: true }),
            new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }),
            new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }),
            new Event('blur', { bubbles: true })
          ];
          
          for (const event of events) {
            input.dispatchEvent(event);
            await new Promise(resolve => setTimeout(resolve, 50));
          }
          
          log('Content inserted successfully with enhanced events');
          log('Final value in input:', input.value.substring(0, 100) + '...');
        } else if (input.isContentEditable) {
          input.focus();
          await new Promise(resolve => setTimeout(resolve, 100));
          
          // Clear and insert for contenteditable
          input.textContent = '';
          input.textContent = content;
          
          // Trigger events for contenteditable
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          
          log('Content inserted into contenteditable element');
        }
        
        // Always look for and click the Insert button (not just when assistEnabled)
        log('Looking for Insert button to complete the process...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const submitBtn = findSubmitButton();
        if (submitBtn) {
          log('Found Insert button, clicking to complete the process...');
          try {
            // Multiple click methods for reliability
            submitBtn.click();
            await new Promise(resolve => setTimeout(resolve, 200));
            
            // Dispatch click event as backup
            submitBtn.dispatchEvent(new Event('click', { bubbles: true, cancelable: true }));
            await new Promise(resolve => setTimeout(resolve, 200));
            
            // MouseEvent as final backup
            const mouseEvent = new MouseEvent('click', {
              view: window,
              bubbles: true,
              cancelable: true,
              clientX: submitBtn.getBoundingClientRect().left + 10,
              clientY: submitBtn.getBoundingClientRect().top + 10
            });
            submitBtn.dispatchEvent(mouseEvent);
            
            log('Insert button clicked successfully!');
          } catch (clickError) {
            log('Error clicking Insert button:', clickError);
          }
        } else {
          log('Insert button not found - URLs inserted but not submitted');
        }
        
        return { ok: true, notebookId };
      }
      
      log('Could not find input field after all attempts');
      return { ok: false, error: 'Could not find input field for website URLs' };
    } catch (e) {
      log('Error in handleContentInsertion:', e);
      return { ok: false, error: e.message };
    }
  }
    
  function getNotebooksList() {
    const notebooks = [];
    
    // Try to find notebook elements in the sidebar or main area
    // Common patterns for notebook lists in web apps
    const selectors = [
      '[role="listitem"][aria-label*="notebook" i]',
      '[data-testid*="notebook" i]',
      '.notebook-item',
      '[class*="notebook-list" i] > *',
      '[aria-label*="notebook" i]'
    ];
    
    for (const selector of selectors) {
      const elements = document.querySelectorAll(selector);
      if (elements.length > 0) {
        elements.forEach((el, index) => {
          const title = el.textContent?.trim() || `Notebook ${index + 1}`;
          const id = el.getAttribute('data-id') || 
                    el.getAttribute('data-notebook-id') || 
                    el.getAttribute('id') || 
                    `notebook-${index}`;
          notebooks.push({ id, title });
        });
        break;
      }
    }
    
    return notebooks;
  }
    
  function selectNotebook(notebookId) {
    try {
      // Find the notebook element
      const notebookEl = document.querySelector(
        `[data-id="${notebookId}"], [data-notebook-id="${notebookId}"], #${notebookId}`
      );
      
      if (notebookEl) {
        notebookEl.click();
        return { ok: true };
      }
      
      // Try finding by text content if ID didn't work
      const notebooks = document.querySelectorAll('[role="listitem"], .notebook-item');
      for (const nb of notebooks) {
        if (nb.textContent?.includes(notebookId)) {
          nb.click();
          return { ok: true };
        }
      }
      
      return { ok: false, error: 'Notebook not found' };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }
    
  async function createNewNotebook() {
    try {
      log('Looking for New Notebook button...');
      
      // Find and click the "New Notebook" or "+" button
      const newNotebookBtn = findNewNotebookButton();
      if (!newNotebookBtn) {
        return { ok: false, error: 'Could not find New Notebook button' };
      }
      
      log('Found New Notebook button, clicking...');
      newNotebookBtn.click();
      
      // Wait for the notebook creation process to start
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Wait for page navigation/loading to complete
      log('Waiting for notebook creation to complete...');
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      // Wait for the notebook interface to be ready
      // This is important as the new notebook page needs time to load
      let attempts = 0;
      const maxAttempts = 10;
      
      while (attempts < maxAttempts) {
        // Check if we're now on a notebook page (URL change)
        if (window.location.href.includes('notebook/')) {
          log('Detected navigation to notebook page');
          break;
        }
        
        // Or check if notebook content is visible
        const notebookContent = document.querySelector('[role="main"], .notebook-content, main');
        if (notebookContent) {
          log('Detected notebook content loaded');
          break;
        }
        
        attempts++;
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      
      // Additional wait for UI elements to render
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Try to get the ID of the newly created notebook
      // Usually it's in the URL or from selected elements
      let notebookId = 'new-notebook';
      
      // Try to extract from URL first
      const urlMatch = window.location.href.match(/notebook\/([a-f0-9-]+)/);
      if (urlMatch) {
        notebookId = urlMatch[1];
        log('Extracted notebook ID from URL:', notebookId);
      } else {
        // Fallback to looking for selected notebook elements
        const selectedNotebook = document.querySelector(
          '[aria-selected="true"][role="listitem"], .notebook-item.selected, .notebook-item:first-child'
        );
        
        if (selectedNotebook) {
          const id = selectedNotebook.getAttribute('data-id') || 
                    selectedNotebook.getAttribute('data-notebook-id') || 
                    selectedNotebook.getAttribute('id');
          if (id) {
            notebookId = id;
            log('Extracted notebook ID from selected element:', notebookId);
          }
        }
      }
      
      log('Notebook creation completed, ID:', notebookId);
      return { ok: true, notebookId };
    } catch (e) {
      log('Error in createNewNotebook:', e);
      return { ok: false, error: e.message };
    }
  }
    
  function findNewNotebookButton() {
    const patterns = [
      /new\s+notebook/i,
      /create\s+notebook/i,
      /add\s+notebook/i,
      /^\+$/,
      /^new$/i
    ];
    
    const buttons = document.querySelectorAll('button, [role="button"]');
    for (const btn of buttons) {
      const text = btn.textContent?.trim() || '';
      const aria = btn.getAttribute('aria-label') || '';
      
      for (const pattern of patterns) {
        if (pattern.test(text) || pattern.test(aria)) {
          return btn;
        }
      }
    }
    
    return null;
  }
    
  function findSubmitButton() {
    // Look for submit/add/insert buttons near the input field
    log('Looking for Insert/Submit button...');
    
    // Priority 1: Look specifically for "Insert" button (exact match)
    const insertButtons = document.querySelectorAll('button, [role="button"]');
    for (const btn of insertButtons) {
      const text = (btn.textContent || '').trim().toLowerCase();
      if (text === 'insert' && isVisible(btn)) {
        log('Found "Insert" button:', btn.textContent.trim());
        return btn;
      }
    }
    
    // Priority 2: Look for other submit patterns
    const patterns = [
      /^add$/i,
      /^submit$/i,
      /^continue$/i,
      /^next$/i,
      /^done$/i,
      /^save$/i,
      /add\s+sources?/i,
      /insert\s+sources?/i,
      /create\s+sources?/i
    ];
    
    const buttons = document.querySelectorAll('button, [role="button"]');
    const visibleButtons = Array.from(buttons).filter(btn => isVisible(btn));
    
    log(`Found ${visibleButtons.length} visible buttons, checking for submit patterns...`);
    
    for (const btn of visibleButtons) {
      const text = btn.textContent?.trim() || '';
      const aria = btn.getAttribute('aria-label') || '';
      const classes = btn.className || '';
      
      log(`Checking button: "${text}" | aria: "${aria}" | classes: "${classes}"`);
      
      for (const pattern of patterns) {
        if (pattern.test(text) || pattern.test(aria)) {
          log(`Found submit button via pattern match: "${text}"`);
          return btn;
        }
      }
      
      // Also look for primary/action buttons (often blue or highlighted)
      const isPrimary = classes.includes('primary') || 
                       classes.includes('action') || 
                       classes.includes('submit') ||
                       btn.type === 'submit';
      
      if (isPrimary && text.length > 0 && text.length < 20) {
        log(`Found primary button: "${text}"`);
        return btn;
      }
    }
    
    log('No submit button found');
    return null;
  }
    
  async function waitForElement(selector, timeout = 5000) {
    const start = Date.now();
    
    return new Promise((resolve, reject) => {
      const timer = setInterval(() => {
        const element = document.querySelector(selector);
        if (element) {
          clearInterval(timer);
          resolve(element);
        } else if (Date.now() - start > timeout) {
          clearInterval(timer);
          reject(new Error('Element not found within timeout'));
        }
      }, 100);
    });
  }

  async function waitForSourceInterface(timeout = 15000) {
    const start = Date.now();
    log('Waiting for source interface elements to be available...');
    
    return new Promise((resolve) => {
      const checkInterval = setInterval(() => {
        // Look for any source-related buttons or interface elements
        const sourceIndicators = [
          // Look for Website button
          () => findWebsiteButton(),
          // Look for other source type buttons
          () => document.querySelector('button:has-text("Link"), [role="button"]:has-text("Link")'),
          // Look for add sources button
          () => findAddSourcesButton(),
          // Look for any source-related interface
          () => document.querySelector('[aria-label*="source" i], [data-testid*="source" i]'),
          // Look for main content area that indicates notebook is ready
          () => document.querySelector('[role="main"], .notebook-content, main')
        ];
        
        const foundElements = sourceIndicators.filter(check => {
          try {
            return check();
          } catch (e) {
            return false;
          }
        });
        
        if (foundElements.length > 0 || Date.now() - start > timeout) {
          clearInterval(checkInterval);
          if (foundElements.length > 0) {
            log('Source interface detected, proceeding...');
          } else {
            log('Timeout waiting for source interface, proceeding anyway...');
          }
          resolve();
        }
      }, 500);
    });
  }

  async function waitForUrlInputField(timeout = 10000) {
    const start = Date.now();
    log('Waiting for URL input field to appear...');
    
    return new Promise((resolve) => {
      const checkInterval = setInterval(() => {
        // Try to find the input field
        const input = findAddSourcesInput();
        
        if (input) {
          clearInterval(checkInterval);
          log('URL input field found!');
          resolve(input);
          return;
        }
        
        // Check timeout
        if (Date.now() - start > timeout) {
          clearInterval(checkInterval);
          log('Timeout waiting for URL input field');
          resolve(null);
        }
      }, 200); // Check every 200ms for faster detection
    });
  }
})();