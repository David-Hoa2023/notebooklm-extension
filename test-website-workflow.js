// Test script for Website button workflow in NotebookLM
// Run this in the browser console on a NotebookLM notebook page

console.log('=== NotebookLM Website Workflow Test ===');

// Test functions (these mirror the content script functions)
function findWebsiteButton(root = document) {
  const buttons = root.querySelectorAll('button, [role="button"]');
  for (const btn of buttons) {
    const text = (btn.textContent || '').trim().toLowerCase();
    const aria = (btn.getAttribute('aria-label') || '').trim().toLowerCase();
    
    if (text === 'website' || aria.includes('website')) {
      return btn;
    }
  }
  return null;
}

function findAddSourcesButton(root = document) {
  const buttons = root.querySelectorAll('button, [role="button"]');
  for (const btn of buttons) {
    const text = (btn.textContent || '').trim().toLowerCase();
    const aria = (btn.getAttribute('aria-label') || '').trim().toLowerCase();
    
    if (text.includes('add') && (text.includes('source') || text.includes('sources'))) {
      return btn;
    }
  }
  return null;
}

function findTextareaOrInput(root = document) {
  const elements = root.querySelectorAll('textarea, input[type="text"], input[type="url"]');
  return Array.from(elements).filter(el => {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  });
}

function findSubmitButtons(root = document) {
  const buttons = root.querySelectorAll('button, [role="button"]');
  const submitPatterns = [/^add$/i, /^submit$/i, /^continue$/i, /^next$/i, /^done$/i, /^save$/i];
  
  return Array.from(buttons).filter(btn => {
    const text = (btn.textContent || '').trim();
    const rect = btn.getBoundingClientRect();
    const isVisible = rect.width > 0 && rect.height > 0;
    
    if (!isVisible) return false;
    
    return submitPatterns.some(pattern => pattern.test(text)) ||
           btn.className.includes('primary') ||
           btn.type === 'submit';
  });
}

// Start testing
console.log('1. Looking for "Add sources" button...');
const addSourcesBtn = findAddSourcesButton();
if (addSourcesBtn) {
  console.log('✅ Found "Add sources" button:', addSourcesBtn.textContent.trim(), addSourcesBtn);
} else {
  console.log('❌ No "Add sources" button found');
}

console.log('\n2. Looking for "Website" button...');
const websiteBtn = findWebsiteButton();
if (websiteBtn) {
  console.log('✅ Found "Website" button:', websiteBtn.textContent.trim(), websiteBtn);
} else {
  console.log('❌ No "Website" button found');
}

console.log('\n3. Looking for textarea/input fields...');
const inputs = findTextareaOrInput();
console.log(`Found ${inputs.length} input/textarea elements:`);
inputs.forEach((input, i) => {
  console.log(`  ${i}: ${input.tagName} - placeholder: "${input.placeholder}" - visible: ${input.offsetParent !== null}`);
});

console.log('\n4. Looking for submit buttons...');
const submitBtns = findSubmitButtons();
console.log(`Found ${submitBtns.length} potential submit buttons:`);
submitBtns.forEach((btn, i) => {
  console.log(`  ${i}: "${btn.textContent.trim()}" - classes: ${btn.className}`);
});

// Interactive test
console.log('\n=== INTERACTIVE WORKFLOW TEST ===');
console.log('You can now test the workflow manually:');

if (websiteBtn) {
  console.log('\nTo test clicking Website button:');
  console.log('websiteBtn.click()');
  
  window.testWebsiteClick = () => {
    console.log('Clicking Website button...');
    websiteBtn.click();
    
    setTimeout(() => {
      console.log('Checking for inputs after Website click...');
      const newInputs = findTextareaOrInput();
      console.log(`Found ${newInputs.length} inputs after clicking Website:`, newInputs);
      
      if (newInputs.length > 0) {
        const textarea = newInputs.find(el => el.tagName.toLowerCase() === 'textarea') || newInputs[0];
        console.log('Target input for URLs:', textarea);
        
        // Test inserting sample URLs
        window.testInsertUrls = () => {
          const sampleUrls = [
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/page3'
          ].join('\n');
          
          textarea.focus();
          textarea.value = sampleUrls;
          textarea.dispatchEvent(new Event('input', { bubbles: true }));
          textarea.dispatchEvent(new Event('change', { bubbles: true }));
          
          console.log('✅ Test URLs inserted! Check the textarea.');
          
          // Look for submit button
          const submitBtns = findSubmitButtons();
          if (submitBtns.length > 0) {
            console.log('Found submit button(s). To submit, run: submitBtns[0].click()');
            window.testSubmit = () => submitBtns[0].click();
          }
        };
        
        console.log('\nTo test inserting URLs: testInsertUrls()');
      }
    }, 1000);
  };
  
  console.log('\nTo start the test: testWebsiteClick()');
} else {
  console.log('⚠️ Cannot test workflow - Website button not found');
  console.log('Make sure you are on a NotebookLM notebook page with sources section visible');
}

// Summary
console.log('\n=== SUMMARY ===');
console.log('Add sources button:', addSourcesBtn ? '✅ Found' : '❌ Missing');
console.log('Website button:', websiteBtn ? '✅ Found' : '❌ Missing');
console.log('Input fields:', inputs.length > 0 ? `✅ Found ${inputs.length}` : '❌ None found');
console.log('Submit buttons:', submitBtns.length > 0 ? `✅ Found ${submitBtns.length}` : '❌ None found');

// Export for easy access
window.notebookTest = {
  addSourcesBtn,
  websiteBtn,
  inputs,
  submitBtns,
  testWebsiteClick: window.testWebsiteClick
};

console.log('\n=== TEST COMPLETE ===');
console.log('Results saved to window.notebookTest');