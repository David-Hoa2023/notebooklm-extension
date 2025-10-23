// scr/lib/crawler.js
// Web crawler for discovering URLs by following links on a website

/**
 * @typedef {Object} CrawlOptions
 * @property {AbortSignal} [signal]
 * @property {number} [maxDepth] - Maximum depth to crawl (default: 2)
 * @property {number} [maxUrls] - Maximum URLs to discover (default: 1000)
 * @property {boolean} [sameDomain] - Only crawl URLs from the same domain (default: true)
 * @property {(p: ProgressEvent) => void} [onProgress]
 */

/**
 * @typedef {{ type: 'progress', stage: string, discovered?: number, crawled?: number, message?: string }} ProgressEvent
 */

const DEFAULTS = {
  maxDepth: 2,
  maxUrls: 1000,
  sameDomain: true
}

export async function crawlWebsite(startUrl, opts = /** @type {CrawlOptions} */ ({})) {
  const { signal, onProgress } = opts
  const maxDepth = opts.maxDepth ?? DEFAULTS.maxDepth
  const maxUrls = opts.maxUrls ?? DEFAULTS.maxUrls
  const sameDomain = opts.sameDomain ?? DEFAULTS.sameDomain

  const baseUrl = new URL(startUrl)
  const discovered = new Set([startUrl])
  const crawled = new Set()
  const queue = [{ url: startUrl, depth: 0 }]
  const results = []

  onProgress?.({ type: 'progress', stage: 'start', message: `Starting crawl from ${baseUrl.origin}` })

  while (queue.length > 0 && results.length < maxUrls) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')

    const { url, depth } = queue.shift()

    // Skip if already crawled
    if (crawled.has(url)) continue

    // Skip if max depth reached
    if (depth > maxDepth) continue

    try {
      crawled.add(url)
      results.push(url)

      onProgress?.({
        type: 'progress',
        stage: 'crawling',
        discovered: discovered.size,
        crawled: crawled.size,
        message: `Crawled ${crawled.size} / Discovered ${discovered.size} URLs`
      })

      // Fetch the page
      const html = await fetchPage(url, signal)
      
      // Extract links
      const links = extractLinks(html, url)

      // Add new links to queue
      for (const link of links) {
        if (discovered.has(link)) continue
        
        // Check if same domain (if required)
        if (sameDomain) {
          try {
            const linkUrl = new URL(link)
            if (linkUrl.origin !== baseUrl.origin) continue
          } catch {
            continue
          }
        }

        discovered.add(link)
        queue.push({ url: link, depth: depth + 1 })

        // Stop discovering if we hit max URLs
        if (discovered.size >= maxUrls) break
      }

    } catch (err) {
      // Skip pages that fail to load
      continue
    }
  }

  onProgress?.({
    type: 'progress',
    stage: 'done',
    discovered: discovered.size,
    crawled: crawled.size,
    message: `Done. Discovered ${results.length} URLs`
  })

  return results
}

async function fetchPage(url, signal) {
  const res = await fetch(url, { 
    method: 'GET', 
    signal,
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; NotebookLM-Extension/1.0)'
    }
  })
  
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  
  const contentType = res.headers.get('content-type') || ''
  if (!contentType.includes('text/html')) {
    throw new Error('Not HTML')
  }
  
  return await res.text()
}

function extractLinks(html, baseUrl) {
  const links = new Set()
  
  // Extract href attributes from <a> tags
  const hrefRegex = /<a[^>]+href=["']([^"']+)["']/gi
  let match
  
  while ((match = hrefRegex.exec(html)) !== null) {
    try {
      const href = match[1]
      
      // Skip anchors, javascript, mailto, tel, etc.
      if (href.startsWith('#') || 
          href.startsWith('javascript:') || 
          href.startsWith('mailto:') || 
          href.startsWith('tel:')) {
        continue
      }
      
      // Convert to absolute URL
      const absoluteUrl = new URL(href, baseUrl).href
      
      // Remove hash fragments
      const cleanUrl = absoluteUrl.split('#')[0]
      
      links.add(cleanUrl)
    } catch {
      // Skip invalid URLs
    }
  }
  
  return Array.from(links)
}

