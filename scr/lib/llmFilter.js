// src/lib/llmFilter.js
// Classify URLs by topic with batched LLM calls. MV3-friendly (fetch-based).

/**
 * @typedef {{ url: string, title?: string, description?: string, slug?: string }} Item
 * @typedef {{ match: boolean, score: number }} Verdict
 * @typedef {{ provider: 'openai'|'generic', endpoint: string, apiKey?: string, model?: string, batchSize?: number, timeoutMs?: number, concurrency?: number }} Settings
 */

/**
 * Classify items by topic. Returns {results, matches}.
 * @param {{topic: string, items: Item[], threshold: number, settings: Settings, signal?: AbortSignal, onProgress?: (p:any)=>void}} args
 */
export async function classifyUrlsByTopic({ topic, items, threshold, settings, signal, onProgress }) {
  const batchSize = Math.max(1, settings.batchSize ?? 100);
  const concurrency = Math.max(1, Math.min(4, settings.concurrency ?? 2));
  const timeoutMs = settings.timeoutMs ?? 20000;

  const batches = [];
  for (let i = 0; i < items.length; i += batchSize) {
    batches.push(items.slice(i, i + batchSize));
  }

  const results = /** @type {Record<string, Verdict>} */ ({});
  let completed = 0;

  onProgress?.({ stage: "classify", message: `Classifying in ${batches.length} batch(es)…`, completed, total: batches.length });

  await runLimited(batches, concurrency, async (batch, idx) => {
    const verdicts = await classifyBatch(topic, batch, settings, timeoutMs, signal);
    for (const v of verdicts) {
      if (!v?.url) continue;
      results[v.url] = { match: !!v.match, score: Number(v.score ?? 0) || 0 };
    }
    completed++;
    onProgress?.({ stage: "classify", message: `Batch ${idx + 1}/${batches.length} done`, completed, total: batches.length });
  });

  const matches = Object.keys(results).filter((u) => results[u]?.match && results[u].score >= threshold);
  onProgress?.({ stage: "done", message: `Classified ${Object.keys(results).length} item(s).` });
  return { results, matches };
}

/* ---------------- internal ---------------- */

async function classifyBatch(topic, batch, settings, timeoutMs, signal) {
  if (settings.provider === "openai") {
    const payload = {
      model: settings.model || "gpt-4o-mini",
      temperature: 0,
      messages: [
        {
          role: "system",
          content:
            "You are a strict classifier. Respond with JSON ONLY, no prose. Return an array of {url, match, score}."
        },
        {
          role: "user",
          content: buildUserPrompt(topic, batch)
        }
      ]
    };
    const res = await fetchWithTimeout(settings.endpoint, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(settings.apiKey ? { authorization: `Bearer ${settings.apiKey}` } : {})
      },
      body: JSON.stringify(payload),
      signal
    }, timeoutMs);

    if (!res.ok) throw new Error(`LLM HTTP ${res.status}`);
    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content ?? "";
    return parseVerdicts(text, batch);
  }

  // Generic JSON endpoint should accept: { topic, items } and return [{url,match,score}]
  const res = await fetchWithTimeout(settings.endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(settings.apiKey ? { authorization: `Bearer ${settings.apiKey}` } : {})
    },
    body: JSON.stringify({ topic, items: batch }),
    signal
  }, timeoutMs);
  if (!res.ok) throw new Error(`LLM HTTP ${res.status}`);
  const j = await res.json();
  return Array.isArray(j) ? j : [];
}

function buildUserPrompt(topic, batch) {
  const head =
    `Classify URLs for topical relevance.\n` +
    `Topic: "${topic}".\n` +
    `Return ONLY a JSON array of objects: [{"url":"<exact>","match":true|false,"score":0..1}].\n` +
    `Use URL, title, description, and slug provided. Score higher if strongly related.\n` +
    `Ensure the "url" exactly matches one of the items below.\n\nItems:\n`;

  const lines = batch.map((it, i) => {
    const safe = (s) => (s || "").replace(/\s+/g, " ").slice(0, 300);
    return `${i + 1}) url: ${it.url}\n   title: ${safe(it.title)}\n   description: ${safe(it.description)}\n   slug: ${safe(it.slug)}\n`;
  });
  return head + lines.join("\n");
}

function parseVerdicts(text, fallbackBatch) {
  // Try to find a JSON array in the text
  const arr = safeParseArray(text);
  if (arr) return arr;
  // Fallback: mark all as non-match
  return fallbackBatch.map((it) => ({ url: it.url, match: false, score: 0 }));
}

function safeParseArray(text) {
  try {
    const start = text.indexOf("[");
    const end = text.lastIndexOf("]");
    if (start !== -1 && end !== -1 && end > start) {
      const sub = text.slice(start, end + 1);
      const j = JSON.parse(sub);
      if (Array.isArray(j)) return j;
    }
  } catch {}
  return null;
}

async function runLimited(items, limit, worker) {
  let i = 0;
  const runners = new Array(Math.min(limit, items.length)).fill(0).map(async (_, idx) => {
    while (i < items.length) {
      const cur = i++;
      await worker(items[cur], cur, idx);
    }
  });
  await Promise.all(runners);
}

async function fetchWithTimeout(url, init, ms, signal) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: anySignal(signal, ctrl.signal) });
  } finally {
    clearTimeout(t);
  }
}

function anySignal(a, b) {
  if (!a) return b;
  if (!b) return a;
  const ctrl = new AbortController();
  const onAbort = () => ctrl.abort();
  a.addEventListener("abort", onAbort);
  b.addEventListener("abort", onAbort);
  return ctrl.signal;
}
