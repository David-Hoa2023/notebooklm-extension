// Simple script to find the Website button
// Run this in NotebookLM console when you can see the Website button

console.clear();
console.log('🔍 Simple Website Button Finder');

function isVisible(el) {
  const rect = el.getBoundingClientRect();
  const computed = getComputedStyle(el);
  return rect.width > 0 && 
         rect.height > 0 && 
         computed.visibility !== 'hidden' && 
         computed.display !== 'none' &&
         computed.opacity !== '0';
}

// Get all elements that could be buttons
const allPossibleButtons = document.querySelectorAll('*');
const buttonCandidates = [];

// Look for anything that might be the Website button
allPossibleButtons.forEach(el => {
  const text = (el.textContent || '').trim().toLowerCase();
  const tag = el.tagName.toLowerCase();
  
  // If element contains "website" text and might be clickable
  if (text === 'website' || (text.includes('website') && text.length < 50)) {
    const isClickable = tag === 'button' || 
                       el.getAttribute('role') === 'button' ||
                       el.onclick !== null ||
                       el.style.cursor === 'pointer' ||
                       getComputedStyle(el).cursor === 'pointer';
    
    if (isVisible(el)) {
      buttonCandidates.push({
        element: el,
        tag: tag,
        text: text,
        classes: el.className,
        isClickable: isClickable,
        rect: el.getBoundingClientRect()
      });
    }
  }
});

console.log(`Found ${buttonCandidates.length} potential Website button candidates:`);

buttonCandidates.forEach((candidate, i) => {
  console.log(`\n--- Candidate ${i + 1} ---`);
  console.log('Element:', candidate.element);
  console.log('Tag:', candidate.tag);
  console.log('Text:', `"${candidate.text}"`);
  console.log('Classes:', candidate.classes);
  console.log('Is clickable:', candidate.isClickable);
  console.log('Position:', Math.round(candidate.rect.left), Math.round(candidate.rect.top));
  console.log('Size:', Math.round(candidate.rect.width), 'x', Math.round(candidate.rect.height));
  
  // Try to click this candidate
  window[`testClick${i}`] = () => {
    console.log(`Clicking candidate ${i + 1}...`);
    try {
      candidate.element.click();
      console.log('✅ Click successful');
      
      // Check for textarea after click
      setTimeout(() => {
        const textareas = Array.from(document.querySelectorAll('textarea')).filter(isVisible);
        console.log(`Found ${textareas.length} textareas after click`);
        if (textareas.length > 0) {
          console.log('✅ Textarea appeared!');
        }
      }, 1000);
    } catch (e) {
      console.log('❌ Click failed:', e.message);
    }
  };
  
  console.log(`To test: testClick${i}()`);
});

// Also look for all actual button elements regardless of text
console.log('\n🔍 All visible buttons on page:');
const allButtons = Array.from(document.querySelectorAll('button, [role="button"]')).filter(isVisible);

allButtons.forEach((btn, i) => {
  const text = (btn.textContent || '').trim();
  if (text.length > 0 && text.length < 30) {
    console.log(`Button ${i}: "${text}" | Classes: ${btn.className} | Tag: ${btn.tagName}`);
  }
});

// Look for elements with website-related attributes or classes
console.log('\n🔍 Elements with website-related attributes:');
const websiteElements = document.querySelectorAll('[class*="website" i], [data-testid*="website" i], [aria-label*="website" i], [id*="website" i]');

websiteElements.forEach((el, i) => {
  if (isVisible(el)) {
    console.log(`Website element ${i}:`, el.tagName, el.textContent?.trim(), el);
  }
});

console.log('\n💡 If you can see the Website button on screen:');
console.log('1. Right-click the Website button');
console.log('2. Select "Inspect Element"');
console.log('3. In the inspector, right-click the highlighted element');
console.log('4. Select "Copy" > "Copy JS path"');
console.log('5. Paste the path here to test: document.querySelector("PASTE_PATH_HERE").click()');

// Try to find by common website icon selectors
const iconSelectors = [
  'svg[data-testid*="web"]',
  'svg[aria-label*="web"]',
  '[class*="web-icon"]',
  '[class*="website-icon"]'
];

console.log('\n🔍 Looking for website icons:');
iconSelectors.forEach(selector => {
  const icons = document.querySelectorAll(selector);
  if (icons.length > 0) {
    console.log(`Found ${icons.length} elements for selector: ${selector}`);
    icons.forEach(icon => {
      const button = icon.closest('button, [role="button"]');
      if (button && isVisible(button)) {
        console.log('Icon parent button:', button, button.textContent?.trim());
      }
    });
  }
});

window.debugResult = { buttonCandidates, allButtons, websiteElements };