// src/sw.js
import { iterateSitemapUrls } from './lib/sitemap.js';
import { classifyUrlsByTopic } from './lib/llmFilter.js';
import { crawlWebsite } from './lib/crawler.js';

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
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
    const controller = new AbortController();

    (async () => {
      try {
        const urls = await crawlWebsite(startUrl, {
          maxDepth,
          maxUrls,
          sameDomain,
          signal: controller.signal,
          onProgress: (p) => chrome.runtime.sendMessage({ type: 'CRAWL_PROGRESS', payload: p })
        });
        sendResponse({ ok: true, urls });
      } catch (e) {
        sendResponse({ ok: false, error: e instanceof Error ? e.message : String(e) });
      }
    })();

    return true; // keep channel open
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
