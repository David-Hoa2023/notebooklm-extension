// src/sw.js
import { iterateSitemapUrls } from './lib/sitemap.js';
import { classifyUrlsByTopic } from './lib/llmFilter.js';
import { crawlWebsite } from './lib/crawler.js';

// Global crawl controller to enable stopping
let crawlController = null;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log('Service worker received message:', msg?.type, 'from tab:', sender?.tab?.id);
  
  if (msg?.type === 'FETCH_NOTEBOOKS') {
    // Fetch notebooks from NotebookLM
    (async () => {
      try {
        console.log('Fetching notebooks from NotebookLM...');
        
        // Query the NotebookLM tab
        const tabs = await chrome.tabs.query({ url: 'https://notebooklm.google.com/*' });
        console.log('Found NotebookLM tabs:', tabs.length);
        
        if (tabs.length > 0) {
          const tabId = tabs[0].id;
          console.log('Using tab ID:', tabId);
          
          // Check if content script is responsive
          let response = null;
          let attempts = 0;
          const maxAttempts = 3;
          
          while (attempts < maxAttempts && !response) {
            attempts++;
            console.log(`Attempt ${attempts} to contact content script...`);
            
            try {
              // Add timeout to sendMessage
              response = await Promise.race([
                chrome.tabs.sendMessage(tabId, { type: 'GET_NOTEBOOKS' }),
                new Promise((_, reject) => 
                  setTimeout(() => reject(new Error('Message timeout')), 5000)
                )
              ]);
              
              if (response) {
                console.log('Content script responded:', response);
                sendResponse(response);
                return;
              }
            } catch (e) {
              console.warn(`Attempt ${attempts} failed:`, e.message);
              
              if (attempts === 1) {
                // First failure - try injecting content script
                try {
                  console.log('Injecting content script...');
                  await chrome.scripting.executeScript({
                    target: { tabId: tabId },
                    files: ['content/notebooklm-assist.js']
                  });
                  
                  // Wait for injection
                  await new Promise(resolve => setTimeout(resolve, 2000));
                  console.log('Content script injected, retrying...');
                } catch (injectionError) {
                  console.error('Failed to inject content script:', injectionError);
                }
              } else if (attempts === 2) {
                // Second failure - try reloading tab
                try {
                  console.log('Reloading NotebookLM tab...');
                  await chrome.tabs.reload(tabId);
                  await new Promise(resolve => setTimeout(resolve, 4000));
                  console.log('Tab reloaded, retrying...');
                } catch (reloadError) {
                  console.error('Failed to reload tab:', reloadError);
                }
              }
            }
          }
          
          // All attempts failed
          console.error('All attempts to contact content script failed');
          sendResponse({ 
            ok: false, 
            error: 'Content script not responding. Please refresh the NotebookLM page.', 
            notebooks: [] 
          });
        } else {
          // No NotebookLM tab open
          console.log('No NotebookLM tab open');
          sendResponse({ ok: true, notebooks: [], message: 'No NotebookLM tab open. Please open NotebookLM first.' });
        }
      } catch (e) {
        console.error('Error in FETCH_NOTEBOOKS:', e);
        sendResponse({ ok: false, error: e.message, notebooks: [] });
      }
    })();
    return true; // Keep channel open
  }
  
  if (msg?.type === 'INSERT_TO_NOTEBOOKLM') {
    // Insert content into NotebookLM
    (async () => {
      try {
        console.log('Starting NotebookLM insertion...');
        const { urls, notebookId, createNew, assistEnabled } = msg;
        const content = urls.join('\n');
        
        // Check if NotebookLM is already open
        let tabs = await chrome.tabs.query({ url: 'https://notebooklm.google.com/*' });
        let tab;
        
        if (tabs.length > 0) {
          tab = tabs[0];
          console.log('Using existing NotebookLM tab:', tab.id);
          // Bring the existing tab to focus
          await chrome.tabs.update(tab.id, { active: true });
          // Brief wait for tab to become active
          await new Promise(resolve => setTimeout(resolve, 500));
        } else {
          console.log('Opening new NotebookLM tab...');
          // Open NotebookLM
          tab = await chrome.tabs.create({ url: 'https://notebooklm.google.com/' });
          
          // Wait for tab to load completely
          await new Promise(resolve => {
            const listener = (tabId, info) => {
              if (tabId === tab.id && info.status === 'complete') {
                chrome.tabs.onUpdated.removeListener(listener);
                console.log('NotebookLM tab loaded');
                resolve();
              }
            };
            chrome.tabs.onUpdated.addListener(listener);
            
            // Fallback timeout
            setTimeout(() => {
              chrome.tabs.onUpdated.removeListener(listener);
              console.log('Tab load timeout, proceeding anyway');
              resolve();
            }, 15000);
          });
          
          // Additional wait for dynamic content to load
          await new Promise(resolve => setTimeout(resolve, 4000));
        }
        
        // Ensure content script is loaded and responsive
        let contentScriptReady = false;
        let attempts = 0;
        const maxAttempts = 3;
        
        while (!contentScriptReady && attempts < maxAttempts) {
          attempts++;
          console.log(`Checking content script readiness (attempt ${attempts})...`);
          
          try {
            await Promise.race([
              chrome.tabs.sendMessage(tab.id, { type: 'GET_NOTEBOOKS' }),
              new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Ping timeout')), 3000)
              )
            ]);
            contentScriptReady = true;
            console.log('Content script is ready');
          } catch (e) {
            console.warn(`Content script ping failed (attempt ${attempts}):`, e.message);
            
            if (attempts === 1) {
              // Try injecting content script
              try {
                console.log('Injecting content script for insertion...');
                await chrome.scripting.executeScript({
                  target: { tabId: tab.id },
                  files: ['content/notebooklm-assist.js']
                });
                await new Promise(resolve => setTimeout(resolve, 2000));
              } catch (injectionError) {
                console.error('Failed to inject content script:', injectionError);
              }
            }
          }
        }
        
        if (!contentScriptReady) {
          throw new Error('Content script is not responding. Please refresh the NotebookLM page and try again.');
        }
        
        // Send content to content script for insertion
        console.log('Sending content to content script...');
        const response = await Promise.race([
          chrome.tabs.sendMessage(tab.id, {
            type: 'INSERT_CONTENT',
            content: content,
            notebookId: notebookId,
            createNew: createNew
          }),
          new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Insert timeout')), 30000)
          )
        ]);
        
        console.log('Content script response:', response);
        sendResponse(response || { ok: true });
      } catch (e) {
        console.error('Error in INSERT_TO_NOTEBOOKLM:', e);
        sendResponse({ ok: false, error: e.message });
      }
    })();
    return true; // Keep channel open
  }
  
  if (msg?.type === 'EXTRACT_SITEMAP') {
    const { baseUrl, maxDepth, maxUrls } = msg;
    const controller = new AbortController();

    (async () => {
      const urls = [];
      try {
        for await (const evt of iterateSitemapUrls(baseUrl, {
          maxDepth,
          maxUrls,
          signal: controller.signal,
          onProgress: (p) => chrome.runtime.sendMessage({ type: 'EXTRACT_PROGRESS', payload: p })
        })) {
          if (evt.type === 'url') urls.push(evt.url);
        }
        sendResponse({ ok: true, urls });
      } catch (e) {
        sendResponse({ ok: false, error: e instanceof Error ? e.message : String(e) });
      }
    })();

    return true; // keep channel open
  }

  if (msg?.type === 'CRAWL_WEBSITE') {
    const { startUrl, maxDepth, maxUrls, sameDomain } = msg;
    crawlController = new AbortController();

    (async () => {
      try {
        const urls = await crawlWebsite(startUrl, {
          maxDepth,
          maxUrls,
          sameDomain,
          signal: crawlController.signal,
          onProgress: (p) => chrome.runtime.sendMessage({ type: 'CRAWL_PROGRESS', payload: p })
        });
        sendResponse({ ok: true, urls });
      } catch (e) {
        if (e.name === 'AbortError') {
          sendResponse({ ok: true, urls: [], stopped: true });
        } else {
          sendResponse({ ok: false, error: e instanceof Error ? e.message : String(e) });
        }
      } finally {
        crawlController = null;
      }
    })();

    return true; // keep channel open
  }

  if (msg?.type === 'STOP_CRAWL') {
    if (crawlController) {
      crawlController.abort();
      crawlController = null;
      sendResponse({ ok: true });
    } else {
      sendResponse({ ok: false, error: 'No active crawl to stop' });
    }
    return true;
  }

  if (msg?.type === 'FILTER_URLS_BY_TOPIC') {
    const { topic, threshold, urls, settings } = msg;
    const controller = new AbortController();

    (async () => {
      try {
        // 1) Build items with shallow metadata for the first N URLs
        const metaLimit = Math.max(0, Number(settings?.metaLimit ?? 200));
        const items = await buildItems(urls, metaLimit, {
          concurrency: 4,
          signal: controller.signal,
          onProgress: (p) => chrome.runtime.sendMessage({ type: 'FILTER_PROGRESS', payload: p })
        });

        // 2) Classify in batches via LLM
        const { results, matches } = await classifyUrlsByTopic({
          topic,
          items,
          threshold,
          settings: {
            provider: settings?.provider || 'openai',
            endpoint: settings?.endpoint,
            apiKey: settings?.apiKey,
            model: settings?.model,
            batchSize: Math.max(1, Number(settings?.batchSize ?? 100)),
            concurrency: 2,
            timeoutMs: 20000
          },
          signal: controller.signal,
          onProgress: (p) => chrome.runtime.sendMessage({ type: 'FILTER_PROGRESS', payload: p })
        });

        sendResponse({ ok: true, results, matches });
      } catch (e) {
        sendResponse({ ok: false, error: e instanceof Error ? e.message : String(e) });
      }
    })();

    return true; // keep channel open
  }
});

/* ---------------- helpers: metadata enrichment ---------------- */

async function buildItems(urls, limit, { concurrency = 4, signal, onProgress }) {
  const items = /** @type {Array<{url:string,title?:string,description?:string,slug?:string}>} */([]);
  const total = urls.length;
  const toFetch = urls.slice(0, limit);
  const rest = urls.slice(limit);
  let completed = 0;

  // Include everything (with or without meta)
  for (const u of urls) {
    items.push({ url: u, slug: slugOf(u) });
  }

  onProgress?.({ stage: 'meta', message: `Fetching titles for ${toFetch.length}/${total} URL(s)…`, completed: 0, total: toFetch.length });

  await runLimited(toFetch, concurrency, async (u) => {
    try {
      const { title, description } = await fetchTitleAndDescription(u, signal);
      const it = items.find((x) => x.url === u);
      if (it) {
        it.title = title;
        it.description = description;
      }
    } catch {
      // ignore per-URL failures
    } finally {
      completed++;
      onProgress?.({ stage: 'meta', message: `Fetched ${completed}/${toFetch.length}`, completed, total: toFetch.length });
    }
  });

  // Remaining URLs keep URL+slug only (cheaper)
  for (const u of rest) {
    const it = items.find((x) => x.url === u);
    if (it) it.title = it.title || '';
  }

  return items;
}

function slugOf(u) {
  try {
    const url = new URL(u);
    const parts = url.pathname.split('/').filter(Boolean);
    return parts.slice(-2).join('/'); // last 1-2 segments
  } catch {
    return '';
  }
}

async function fetchTitleAndDescription(u, signal) {
  const res = await fetch(u, { method: 'GET', signal });
  const html = await res.text();
  return {
    title: extractTitle(html),
    description: extractMetaDescription(html)
  };
}

function extractTitle(html) {
  const m = html.match(/<title[^>]*>(.*?)<\/title>/is);
  return m ? sanitize(m[1]) : '';
}

function extractMetaDescription(html) {
  const m = html.match(/<meta[^>]+name=["']description["'][^>]*content=["']([^"']+)["']/i);
  return m ? sanitize(m[1]) : '';
}

function sanitize(s) {
  return s
    .replace(/\s+/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim()
    .slice(0, 300);
}

async function runLimited(items, limit, worker) {
  let i = 0;
  const runners = new Array(Math.min(limit, items.length)).fill(0).map(async () => {
    while (i < items.length) {
      const cur = i++;
      await worker(items[cur], cur);
    }
  });
  await Promise.all(runners);
}
