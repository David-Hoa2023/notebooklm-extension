// Debug script to test if content script is working
// Run this in the browser console on NotebookLM page

console.log('=== NotebookLM Content Script Debug ===');

// Test if the content script is loaded
const isContentScriptLoaded = () => {
  // Check if content script has added any global variables or modified the page
  return document.querySelector('[data-extension-injected]') || 
         window.notebookLMExtensionLoaded ||
         false;
};

// Test messaging
const testMessaging = async () => {
  try {
    console.log('Testing message to content script...');
    
    // Send a test message to the content script
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: 'GET_NOTEBOOKS' }, (response) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve(response);
        }
      });
    });
    
    console.log('Content script response:', response);
    return response;
  } catch (error) {
    console.error('Message error:', error);
    return null;
  }
};

// Check if we're on NotebookLM
const isNotebookLM = window.location.hostname === 'notebooklm.google.com';
console.log('On NotebookLM:', isNotebookLM);

if (isNotebookLM) {
  console.log('Content script loaded:', isContentScriptLoaded());
  
  // Try to find notebook elements
  const possibleNotebooks = document.querySelectorAll([
    '[role="listitem"]',
    '.notebook-item',
    '[data-notebook-id]',
    'article',
    '[aria-label*="notebook"]'
  ].join(', '));
  
  console.log('Possible notebook elements found:', possibleNotebooks.length);
  possibleNotebooks.forEach((el, i) => {
    console.log(`Notebook ${i}:`, el.textContent?.trim(), el);
  });
  
  // Try to find "Create new" button
  const createButtons = document.querySelectorAll([
    'button:has-text("Create new")',
    '[aria-label*="Create new"]',
    'button:has-text("+ Create new")',
    'button',
    '[role="button"]'
  ].join(', '));
  
  console.log('Possible create buttons found:', createButtons.length);
  createButtons.forEach((btn, i) => {
    const text = btn.textContent?.trim();
    if (text && (text.includes('Create') || text.includes('New') || text.includes('+'))) {
      console.log(`Create button ${i}:`, text, btn);
    }
  });
  
  // Test the messaging if this is run from popup/service worker context
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    testMessaging();
  }
} else {
  console.log('Not on NotebookLM. Navigate to https://notebooklm.google.com first.');
}

console.log('=== Debug Complete ===');