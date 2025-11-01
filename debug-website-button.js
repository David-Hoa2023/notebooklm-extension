// Debug script specifically for finding the Website button
// Run this in the NotebookLM console when you can see the Website button

console.log('=== Website Button Debug Script ===');

function isVisible(el) {
  const rect = el.getBoundingClientRect();
  const computed = getComputedStyle(el);
  return rect.width > 0 && 
         rect.height > 0 && 
         computed.visibility !== 'hidden' && 
         computed.display !== 'none' &&
         computed.opacity !== '0';
}

// Find all buttons on the page
const allButtons = document.querySelectorAll('button, [role="button"]');
console.log(`Found ${allButtons.length} total buttons`);

// Filter to visible buttons only
const visibleButtons = Array.from(allButtons).filter(isVisible);
console.log(`Found ${visibleButtons.length} visible buttons`);

// Look specifically for Website button
console.log('\n=== Searching for Website button ===');

let websiteButton = null;
let foundMethod = 'none';

// Method 1: Exact text match
for (const btn of visibleButtons) {
  const text = (btn.textContent || '').trim();
  if (text.toLowerCase() === 'website') {
    websiteButton = btn;
    foundMethod = 'exact text match';
    break;
  }
}

// Method 2: Text includes website
if (!websiteButton) {
  for (const btn of visibleButtons) {
    const text = (btn.textContent || '').trim().toLowerCase();
    if (text.includes('website')) {
      websiteButton = btn;
      foundMethod = 'text includes website';
      break;
    }
  }
}

// Method 3: Check aria-label
if (!websiteButton) {
  for (const btn of visibleButtons) {
    const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
    if (aria.includes('website')) {
      websiteButton = btn;
      foundMethod = 'aria-label includes website';
      break;
    }
  }
}

if (websiteButton) {
  console.log('✅ Website button found!');
  console.log('Method:', foundMethod);
  console.log('Button element:', websiteButton);
  console.log('Text content:', `"${websiteButton.textContent?.trim()}"`);
  console.log('Aria label:', `"${websiteButton.getAttribute('aria-label') || 'none'}"`);
  console.log('Classes:', websiteButton.className);
  console.log('ID:', websiteButton.id || 'none');
  console.log('Data attributes:', Array.from(websiteButton.attributes).filter(attr => attr.name.startsWith('data-')));
  
  // Test clicking the button
  window.testWebsiteClick = () => {
    console.log('Clicking Website button...');
    websiteButton.click();
    console.log('Button clicked!');
    
    // Wait and check for textarea
    setTimeout(() => {
      const textareas = document.querySelectorAll('textarea');
      const visibleTextareas = Array.from(textareas).filter(isVisible);
      console.log(`Found ${visibleTextareas.length} visible textareas after clicking Website button`);
      
      if (visibleTextareas.length > 0) {
        console.log('✅ Textarea appeared after clicking Website button');
        visibleTextareas.forEach((ta, i) => {
          console.log(`Textarea ${i}:`, ta.placeholder || 'no placeholder', ta);
        });
        
        // Test inserting content
        window.testInsert = () => {
          const textarea = visibleTextareas[0];
          const testUrls = [
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/page3'
          ].join('\n');
          
          textarea.focus();
          textarea.value = testUrls;
          textarea.dispatchEvent(new Event('input', { bubbles: true }));
          textarea.dispatchEvent(new Event('change', { bubbles: true }));
          
          console.log('✅ Test URLs inserted into textarea');
        };
        
        console.log('To test inserting URLs: testInsert()');
      } else {
        console.log('❌ No textarea appeared after clicking Website button');
      }
    }, 1500);
  };
  
  console.log('\n🧪 To test clicking the Website button: testWebsiteClick()');
} else {
  console.log('❌ Website button not found');
  
  // Debug: Show all buttons with their text
  console.log('\n=== All visible buttons ===');
  visibleButtons.forEach((btn, i) => {
    const text = (btn.textContent || '').trim();
    const aria = btn.getAttribute('aria-label') || '';
    const classes = btn.className || '';
    const rect = btn.getBoundingClientRect();
    
    console.log(`Button ${i}:`);
    console.log(`  Text: "${text}"`);
    console.log(`  Aria: "${aria}"`);
    console.log(`  Classes: "${classes}"`);
    console.log(`  Position: ${Math.round(rect.left)}, ${Math.round(rect.top)}`);
    console.log(`  Size: ${Math.round(rect.width)} x ${Math.round(rect.height)}`);
    console.log(`  Element:`, btn);
    console.log('---');
  });
  
  // Look for buttons that might be the Website button
  console.log('\n=== Potential Website buttons ===');
  const potentialButtons = visibleButtons.filter(btn => {
    const text = (btn.textContent || '').trim().toLowerCase();
    const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
    const classes = btn.className.toLowerCase();
    
    return text.includes('web') || 
           aria.includes('web') || 
           classes.includes('web') ||
           text.includes('site') ||
           aria.includes('site');
  });
  
  console.log(`Found ${potentialButtons.length} potential Website buttons:`);
  potentialButtons.forEach((btn, i) => {
    console.log(`  ${i}: "${btn.textContent?.trim()}" (${btn.className})`, btn);
  });
}

// Check if we're on the right page
console.log('\n=== Page Info ===');
console.log('URL:', window.location.href);
console.log('Title:', document.title);
console.log('Is notebook page:', window.location.href.includes('notebook/'));

// Look for source-related UI elements
const sourceElements = document.querySelectorAll('[aria-label*="source" i], [data-testid*="source" i], [class*="source" i]');
console.log(`Found ${sourceElements.length} source-related elements on page`);

console.log('\n=== End Debug ===');

// Export for easy access
window.debugInfo = {
  allButtons: allButtons.length,
  visibleButtons: visibleButtons.length,
  websiteButton,
  foundMethod,
  potentialButtons: potentialButtons || []
};