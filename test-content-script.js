// Test script to run in NotebookLM console to verify content script
// Copy and paste this entire script into the browser console on NotebookLM

console.log('=== NotebookLM Content Script Test ===');

// Test 1: Check if content script is loaded
const isLoaded = window.notebookLMExtensionLoaded || 
                 document.documentElement.getAttribute('data-notebooklm-extension') === 'loaded';

console.log('1. Content script loaded:', isLoaded);

// Test 2: Check if we can find extension ID
let extensionId = null;
try {
  // Try to get extension ID from manifest
  const manifest = chrome.runtime.getManifest();
  if (manifest) {
    extensionId = chrome.runtime.id;
    console.log('2. Extension ID found:', extensionId);
  }
} catch (e) {
  console.log('2. Extension ID not accessible from content script (this is normal)');
}

// Test 3: Look for notebook elements
const notebookSelectors = [
  '[role="listitem"]',
  '.notebook-item', 
  '[data-notebook-id]',
  'article',
  '[aria-label*="notebook"]'
];

let foundElements = 0;
notebookSelectors.forEach(selector => {
  const elements = document.querySelectorAll(selector);
  if (elements.length > 0) {
    console.log(`3. Found ${elements.length} elements for selector: ${selector}`);
    foundElements += elements.length;
    
    // Show first few elements
    Array.from(elements).slice(0, 3).forEach((el, i) => {
      console.log(`   Element ${i}:`, el.textContent?.trim().substring(0, 50), el);
    });
  }
});

if (foundElements === 0) {
  console.log('3. No potential notebook elements found');
}

// Test 4: Look for "Create new" button
const createSelectors = [
  'button:has-text("Create new")',
  '[aria-label*="Create new"]', 
  'button:has-text("+ Create new")',
  'button',
  '[role="button"]'
];

let createButtons = [];
document.querySelectorAll('button, [role="button"]').forEach(btn => {
  const text = btn.textContent?.trim().toLowerCase();
  if (text && (text.includes('create') || text.includes('new') || text === '+')) {
    createButtons.push(btn);
  }
});

console.log(`4. Found ${createButtons.length} potential "Create" buttons:`);
createButtons.slice(0, 5).forEach((btn, i) => {
  console.log(`   Button ${i}: "${btn.textContent?.trim()}"`, btn);
});

// Test 5: Try to simulate message sending
console.log('5. Testing message simulation...');

// Mock the content script functions for testing
const testGetNotebooks = () => {
  const notebooks = [];
  
  notebookSelectors.forEach(selector => {
    const elements = document.querySelectorAll(selector);
    elements.forEach((el, index) => {
      const title = el.textContent?.trim();
      if (title && title.length > 0 && title.length < 100) {
        const id = el.getAttribute('data-id') || 
                  el.getAttribute('data-notebook-id') || 
                  el.getAttribute('id') || 
                  `notebook-${index}`;
        notebooks.push({ id, title });
      }
    });
  });
  
  return notebooks;
};

const mockNotebooks = testGetNotebooks();
console.log('5. Mock notebook extraction result:', mockNotebooks);

// Test 6: Check current URL
console.log('6. Current URL:', window.location.href);
console.log('6. Is NotebookLM:', window.location.hostname === 'notebooklm.google.com');

// Summary
console.log('\n=== SUMMARY ===');
console.log('Content script loaded:', isLoaded);
console.log('Potential notebook elements:', foundElements);
console.log('Create buttons found:', createButtons.length);
console.log('Mock notebooks extracted:', mockNotebooks.length);

if (!isLoaded) {
  console.log('\n❌ ISSUE: Content script not loaded');
  console.log('Solutions:');
  console.log('1. Reload the extension in chrome://extensions/');
  console.log('2. Refresh this NotebookLM tab');
  console.log('3. Check for JavaScript errors in console');
} else {
  console.log('\n✅ Content script appears to be loaded correctly');
}

console.log('=== END TEST ===');

// Export results for easy access
window.extensionTest = {
  isLoaded,
  foundElements,
  createButtons: createButtons.length,
  notebooks: mockNotebooks
};