// src/lib/sitemap.js
// Minimal, dependency-free sitemap extraction for MV3 service workers or pages.

// Public API:
//   - extractAllSitemapUrls(baseInput, opts): Promise<{ urls: string[], meta: Diagnostics }>
//   - iterateSitemapUrls(baseInput, opts): AsyncGenerator<ProgressEvent | UrlEvent>
//
// Typical usage (collect all):
//   const { urls } = await extractAllSitemapUrls('https://example.com', { maxDepth: 3, maxUrls: 20000 });
//
// Progressive usage (for streaming into UI):
//   for await (const evt of iterateSitemapUrls('https://example.com', { onProgress })) {
//     if (evt.type === 'url') { /* render row */ }
//   }

/**
 * @typedef {Object} ExtractOptions
 * @property {AbortSignal} [signal]
 * @property {number} [maxDepth]     // recursion depth for sitemap indexes
 * @property {number} [maxUrls]      // hard cap of collected URLs
 * @property {(p: ProgressEvent) => void} [onProgress]
 */

/**
 * @typedef {{ type: 'progress', stage: string, discovered?: number, fetched?: number, urls?: number, message?: string }} ProgressEvent
 * @typedef {{ type: 'url', url: string, lastmod?: string }} UrlEvent
 * @typedef {{ attempts: string[], robotsTried: boolean, sitemapCount: number, urlCount: number, errors: string[] }} Diagnostics
 */

const DEFAULTS = {
  maxDepth: 3,
  maxUrls: 20000
};

export async function extractAllSitemapUrls(baseInput, opts = /** @type {ExtractOptions} */ ({})) {
  const urls = [];
  const diagnostics = { attempts: [], robotsTried: false, sitemapCount: 0, urlCount: 0, errors: [] };

  for await (const evt of iterateSitemapUrls(baseInput, {
    ...opts,
    onProgress: (p) => {
      opts.onProgress?.(p);
      if (p.stage === 'attempt') diagnostics.attempts.push(p.message || '');
      if (p.stage === 'robots') diagnostics.robotsTried = true;
      if (p.stage === 'sitemap-found') diagnostics.sitemapCount = p.discovered ?? diagnostics.sitemapCount;
      if (p.stage === 'error' && p.message) diagnostics.errors.push(p.message);
      if (p.stage === 'urls') diagnostics.urlCount = p.urls ?? diagnostics.urlCount;
    }
  })) {
    if (evt.type === 'url') urls.push(evt.url);
  }

  return { urls, meta: diagnostics };
}

export async function* iterateSitemapUrls(baseInput, opts = /** @type {ExtractOptions} */ ({})) {
  const { signal, onProgress } = opts;
  const maxDepth = opts.maxDepth ?? DEFAULTS.maxDepth;
  const maxUrls = opts.maxUrls ?? DEFAULTS.maxUrls;

  const base = normalizeBase(baseInput);
  const attempts = guessSitemapUrls(base);
  onProgress?.({ type: 'progress', stage: 'attempt', message: `Trying common sitemap paths for ${base.origin}` });

  // Discover via robots.txt (in parallel with direct attempts)
  const robotsPromise = discoverFromRobots(base).catch(() => []);
  const directSet = new Set(attempts);
  const discovered = new Set(attempts);

  // Try direct endpoints; then merge in robots.txt findings.
  const queue = [];
  for (const u of directSet) queue.push({ url: u, depth: 0 });

  const robotUrls = await robotsPromise;
  if (robotUrls.length) {
    for (const u of robotUrls) {
      if (!discovered.has(u)) {
        discovered.add(u);
        queue.push({ url: u, depth: 0 });
      }
    }
    onProgress?.({ type: 'progress', stage: 'robots', message: `Found ${robotUrls.length} sitemap(s) via robots.txt` });
  }

  onProgress?.({ type: 'progress', stage: 'sitemap-found', discovered: queue.length });

  const visitedSitemaps = new Set();
  const yielded = new Set(); // URLs
  let totalUrls = 0;
  let successfulFetch = false;
  let lastError = null;

  while (queue.length) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    const { url, depth } = queue.shift();

    if (visitedSitemaps.has(url)) continue;
    visitedSitemaps.add(url);

    try {
      const xml = await fetchSitemapText(url, signal);
      const doc = parseXml(xml);
      successfulFetch = true;

      if (isSitemapIndex(doc)) {
        if (depth >= maxDepth) {
          onProgress?.({ type: 'progress', stage: 'skip', message: `Max depth reached at ${url}` });
          continue;
        }
        const subs = Array.from(doc.getElementsByTagNameNS('*', 'sitemap'));
        for (const sm of subs) {
          const loc = textOf(sm, 'loc');
          if (!loc) continue;
          const absolute = absolutize(loc, base);
          if (!visitedSitemaps.has(absolute) && !queue.some(q => q.url === absolute)) {
            queue.push({ url: absolute, depth: depth + 1 });
          }
        }
      } else {
        const urlNodes = Array.from(doc.getElementsByTagNameNS('*', 'url'));
        for (const node of urlNodes) {
          if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
          const loc = textOf(node, 'loc');
          if (!loc) continue;
          const absolute = absolutize(loc, base);
          if (!yielded.has(absolute)) {
            yielded.add(absolute);
            totalUrls++;
            /** @type {UrlEvent} */
            const evt = { type: 'url', url: absolute, lastmod: textOf(node, 'lastmod') || undefined };
            yield evt;
            if (totalUrls % 500 === 0) {
              onProgress?.({ type: 'progress', stage: 'urls', urls: totalUrls, message: `Discovered ${totalUrls} URL(s)` });
            }
            if (totalUrls >= maxUrls) {
              onProgress?.({ type: 'progress', stage: 'stop', urls: totalUrls, message: `Reached maxUrls=${maxUrls}` });
              return;
            }
          }
        }
      }
    } catch (err) {
      // Capture last error for reporting
      lastError = err;
      // Continue trying other URLs
      continue;
    }
  }

  if (!successfulFetch || totalUrls === 0) {
    let errorMsg = `No sitemap found at ${base.origin}.`;
    if (lastError) {
      const errText = lastError instanceof Error ? lastError.message : String(lastError);
      // Check for common CORS error
      if (errText.includes('CORS') || errText.includes('Failed to fetch') || errText.includes('NetworkError')) {
        errorMsg += ` CORS/Network error - try using the web crawler or manual URL input instead.`;
      } else {
        errorMsg += ` Error: ${errText}`;
      }
    } else {
      errorMsg += ` The site may not have a public sitemap.xml file.`;
    }
    onProgress?.({ type: 'progress', stage: 'error', message: errorMsg });
  } else {
    onProgress?.({ type: 'progress', stage: 'done', urls: totalUrls, message: `Done. ${totalUrls} URL(s)` });
  }
}

/* ----------------------------- helpers ------------------------------ */

function normalizeBase(input) {
  let str = String(input || '').trim();
  if (!/^https?:\/\//i.test(str)) str = 'https://' + str;
  const u = new URL(str);
  // Only keep origin; most sitemaps live at site root.
  return new URL(u.origin + '/');
}

function guessSitemapUrls(base) {
  const candidates = [
    new URL('/sitemap.xml', base).href,
    new URL('/sitemap_index.xml', base).href,
    new URL('/sitemap-index.xml', base).href,
    new URL('/wp-sitemap.xml', base).href,        // WordPress
    new URL('/sitemap1.xml', base).href,          // Common pattern
    new URL('/sitemap/', base).href,              // Directory
    new URL('/sitemap/sitemap.xml', base).href,   // Nested
    new URL('/sitemaps/sitemap.xml', base).href   // Alternative
  ];
  return Array.from(new Set(candidates));
}

async function discoverFromRobots(base) {
  const robotsUrl = new URL('/robots.txt', base).href;
  const res = await fetch(robotsUrl, { method: 'GET' });
  if (!res.ok) return [];
  const text = await res.text();
  const out = [];
  const lines = text.split('\n');
  for (const line of lines) {
    const m = line.match(/^\s*sitemap:\s*(.+)\s*$/i);
    if (m && m[1]) {
      try {
        out.push(new URL(m[1].trim(), base).href);
      } catch { /* ignore bad URLs */ }
    }
  }
  return out;
}

async function fetchSitemapText(url, signal) {
  const res = await fetch(url, { method: 'GET', signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const ct = (res.headers.get('content-type') || '').toLowerCase();
  const ce = (res.headers.get('content-encoding') || '').toLowerCase();
  const isGzPath = url.toLowerCase().endsWith('.gz');
  const isGzip = isGzPath || ct.includes('gzip') || ct.includes('x-gzip') || ce.includes('gzip');

  // If server sets Content-Encoding: gzip, the browser typically auto-decompresses.
  // We only manually decompress .gz payloads served as raw bytes.
  if (isGzPath && res.body && supportsDecompressionStream()) {
    return await decompressGzipToText(res.body);
  }

  // Fallback to normal text()
  return await res.text();
}

function supportsDecompressionStream() {
  return typeof DecompressionStream !== 'undefined';
}

async function decompressGzipToText(readableStream) {
  // Decompress raw .gz stream to text without buffering the whole file in memory twice.
  const ds = new DecompressionStream('gzip');
  const decompressed = readableStream.pipeThrough(ds);
  // Convert bytes → text
  // Use TextDecoderStream if available; otherwise go via Response helper.
  if (typeof TextDecoderStream !== 'undefined') {
    const textStream = decompressed.pipeThrough(new TextDecoderStream());
    return await new Response(textStream).text();
  }
  return await new Response(decompressed).text();
}

function parseXml(xmlText) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlText, 'application/xml');
  const err = doc.querySelector('parsererror');
  if (err) {
    throw new Error('Invalid XML');
  }
  return doc;
}

function isSitemapIndex(doc) {
  // If we find any <sitemap> nodes, treat as index.
  return doc.getElementsByTagNameNS('*', 'sitemap').length > 0;
}

function textOf(node, localName) {
  const n = node.getElementsByTagNameNS('*', localName)[0];
  return n ? (n.textContent || '').trim() : '';
}

function absolutize(candidate, base) {
  try {
    return new URL(candidate, base).href;
  } catch {
    return candidate;
  }
}
