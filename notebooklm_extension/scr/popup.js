// popup.js (full revised) — MV3 action popup
// Wires UI → background service worker for sitemap extraction & LLM topic filtering,
// tracks selection, and optionally nudges NotebookLM's "Add sources" via content script.

"use strict";

/* ------------------------- DOM helpers & refs ------------------------- */
const $ = (sel) => document.querySelector(sel);

// Extract
const baseUrlEl = $("#baseUrl");
const extractBtn = $("#extractBtn");
const extractProgress = $("#extractProgress");
const extractProgressBar = $("#extractProgressBar");
const extractStatus = $("#extractStatus");

// Manual URL input
const manualUrlsEl = $("#manualUrls");
const loadManualBtn = $("#loadManualBtn");

// Web Crawler
const crawlUrlEl = $("#crawlUrl");
const crawlBtn = $("#crawlBtn");
const crawlDepthEl = $("#crawlDepth");
const crawlMaxEl = $("#crawlMax");
const crawlSameDomainEl = $("#crawlSameDomain");
const crawlProgress = $("#crawlProgress");
const crawlProgressBar = $("#crawlProgressBar");
const crawlStatus = $("#crawlStatus");

// Filter
const topicInput = $("#topicInput");
const thresholdEl = $("#threshold");
const thresholdOut = $("#thresholdOut");
const filterBtn = $("#filterBtn");
const filterProgress = $("#filterProgress");
const filterProgressBar = $("#filterProgressBar");
const filterStatus = $("#filterStatus");

// LLM settings
const providerEl = $("#provider");
const endpointEl = $("#endpoint");
const modelEl = $("#model");
const apiKeyEl = $("#apiKey");
const batchSizeEl = $("#batchSize");
const metaLimitEl = $("#metaLimit");
const rememberKeyEl = $("#rememberKey");
const saveSettingsBtn = $("#saveSettingsBtn");

// Assist (opt‑in)
const assistEnabledEl = $("#assistEnabled");

// List & selection
const selectAllEl = $("#selectAll");
const showMatchesOnlyEl = $("#showMatchesOnly");
const countsEl = $("#counts");
const urlList = $("#urlList");

// Insert
const insertBtn = $("#insertBtn");
const logEl = $("#log");

/* ------------------------------ state ------------------------------- */
const state = {
  allUrls: /** @type {string[]} */ ([]),
  matchesSet: new Set(),
  selectedSet: new Set(),
  showMatchesOnly: true,
  results: /** @type {Record<string, {match:boolean, score:number}>} */ ({}),
  settings: {
    provider: "openai",
    endpoint: "https://api.openai.com/v1/chat/completions",
    model: "gpt-4o-mini",
    apiKey: "",
    batchSize: 100,
    metaLimit: 200,
    assistEnabled: false
  }
};

/* --------------------------- boot / preload -------------------------- */

// Prefill base URL from current tab (best-effort; URL may be omitted without "tabs" perm)
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  try {
    const u = new URL(tabs?.[0]?.url || "");
    baseUrlEl.value = u.origin;
    crawlUrlEl.value = u.origin;  // Also prefill crawler URL
  } catch { /* ignore */ }
});

// Load persisted settings
chrome.storage.local.get(["settings", "apiKeyPersisted"]).then(({ settings, apiKeyPersisted }) => {
  if (settings) Object.assign(state.settings, settings);

  // LLM settings → UI
  providerEl.value = state.settings.provider;
  endpointEl.value = state.settings.endpoint;
  modelEl.value = state.settings.model;
  batchSizeEl.value = String(state.settings.batchSize);
  metaLimitEl.value = String(state.settings.metaLimit);
  rememberKeyEl.checked = Boolean(apiKeyPersisted);

  // API key only if user opted to persist
  if (apiKeyPersisted && settings?.apiKey) {
    state.settings.apiKey = settings.apiKey;
    apiKeyEl.value = settings.apiKey;
  }

  // Assist opt‑in
  if (assistEnabledEl) assistEnabledEl.checked = !!state.settings.assistEnabled;
});

// Reflect threshold value
if (thresholdOut && thresholdEl) {
  thresholdOut.textContent = Number(thresholdEl.value || 0.5).toFixed(2);
}

/* --------------------------- event handlers -------------------------- */

// Open settings page
document.getElementById("openSettingsBtn").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

// Update threshold bubble
thresholdEl?.addEventListener("input", () => {
  thresholdOut.textContent = Number(thresholdEl.value).toFixed(2);
});

// Listen for background progress (extraction + filtering)
chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.type === "EXTRACT_PROGRESS") {
    const p = msg.payload;
    extractProgress.hidden = false;
    extractStatus.textContent = p.message || "";
    if (p.stage === "urls" && typeof p.urls === "number") {
      // heuristic progress curve up to 90%
      extractProgressBar.value = Math.min(90, 20 + Math.log10(1 + p.urls) * 20);
    }
    if (p.stage === "done" || p.stage === "stop") {
      extractProgressBar.value = 100;
    }
  } else if (msg?.type === "CRAWL_PROGRESS") {
    const p = msg.payload;
    crawlProgress.hidden = false;
    crawlStatus.textContent = p.message || "";
    if (p.stage === "crawling" && p.crawled && p.discovered) {
      // Progress based on crawled vs discovered
      const progress = Math.min(90, (p.crawled / Math.max(1, p.discovered)) * 90);
      crawlProgressBar.value = progress;
    }
    if (p.stage === "done") {
      crawlProgressBar.value = 100;
    }
  } else if (msg?.type === "FILTER_PROGRESS") {
    const p = msg.payload;
    filterProgress.hidden = false;
    filterStatus.textContent = p.message || "";
    if (p.stage === "meta") {
      filterProgressBar.value = Math.min(30, Math.floor((p.completed / Math.max(1, p.total)) * 30));
    } else if (p.stage === "classify") {
      const base = 30;
      const portion = 70 * (p.completed / Math.max(1, p.total));
      filterProgressBar.value = base + portion;
    } else if (p.stage === "done") {
      filterProgressBar.value = 100;
    }
  }
});

// Extract sitemap URLs
extractBtn?.addEventListener("click", async () => {
  const baseUrl = baseUrlEl.value.trim();
  if (!baseUrl) return toast("Enter a site URL.");
  resetList();
  extractProgress.hidden = false;
  extractProgressBar.value = 0;
  extractStatus.textContent = "Extracting…";
  const resp = await chrome.runtime.sendMessage({ type: "EXTRACT_SITEMAP", baseUrl, maxDepth: 3, maxUrls: 20000 });
  if (resp?.ok) {
    state.allUrls = resp.urls || [];
    renderList();
    toast(`Extracted ${state.allUrls.length} URL(s).`);
  } else {
    toast(`Extraction failed: ${resp?.error || "Unknown error"}`);
  }
});

// Crawl website
crawlBtn?.addEventListener("click", async () => {
  const startUrl = crawlUrlEl.value.trim();
  if (!startUrl) return toast("Enter a start URL.");
  
  resetList();
  crawlProgress.hidden = false;
  crawlProgressBar.value = 0;
  crawlStatus.textContent = "Starting crawl…";
  
  const maxDepth = Number(crawlDepthEl.value || 2);
  const maxUrls = Number(crawlMaxEl.value || 1000);
  const sameDomain = crawlSameDomainEl.checked;
  
  const resp = await chrome.runtime.sendMessage({ 
    type: "CRAWL_WEBSITE", 
    startUrl, 
    maxDepth, 
    maxUrls, 
    sameDomain 
  });
  
  if (resp?.ok) {
    state.allUrls = resp.urls || [];
    renderList();
    toast(`Crawled ${state.allUrls.length} URL(s).`);
  } else {
    toast(`Crawl failed: ${resp?.error || "Unknown error"}`);
  }
});

// Load manual URLs
loadManualBtn?.addEventListener("click", () => {
  const text = manualUrlsEl.value.trim();
  if (!text) return toast("Enter URLs (one per line).");
  
  const lines = text.split('\n');
  const urls = [];
  
  for (const line of lines) {
    const url = line.trim();
    if (!url) continue;
    
    // Basic URL validation
    try {
      new URL(url);
      urls.push(url);
    } catch {
      // Skip invalid URLs
    }
  }
  
  if (urls.length === 0) return toast("No valid URLs found.");
  
  resetList();
  state.allUrls = urls;
  renderList();
  toast(`Loaded ${urls.length} URL(s).`);
});

// Filter with LLM
filterBtn?.addEventListener("click", async () => {
  const topic = topicInput.value.trim();
  if (!topic) return toast("Enter a topic.");
  if ((state.allUrls?.length || 0) === 0) return toast("Extract URLs first.");

  // Gather latest settings from UI
  const uiSettings = getSettingsFromUI();
  Object.assign(state.settings, uiSettings);

  filterProgress.hidden = false;
  filterProgressBar.value = 0;
  filterStatus.textContent = "Preparing…";

  const threshold = Number(thresholdEl.value || 0.5);

  const resp = await chrome.runtime.sendMessage({
    type: "FILTER_URLS_BY_TOPIC",
    topic,
    threshold,
    urls: state.allUrls,
    settings: state.settings
  });

  if (resp?.ok) {
    state.results = resp.results || {};
    state.matchesSet = new Set(resp.matches || []);
    applyShowMatches();
    toast(`Matched ${resp.matches?.length || 0} URL(s) for “${topic}”.`);
  } else {
    toast(`Filter failed: ${resp?.error || "Unknown error"}`);
  }
});

// Select all shown
selectAllEl?.addEventListener("change", () => {
  const check = selectAllEl.checked;
  document.querySelectorAll('input[data-row="sel"]').forEach((el) => {
    el.checked = check;
    const u = el.getAttribute("data-url");
    if (check) state.selectedSet.add(u);
    else state.selectedSet.delete(u);
  });
  insertBtn.disabled = state.selectedSet.size === 0;
  updateCounts();
});

// Show matches only
showMatchesOnlyEl?.addEventListener("change", () => {
  state.showMatchesOnly = showMatchesOnlyEl.checked;
  applyShowMatches();
});

// Insert into NotebookLM (copy + open; optional assist nudge)
insertBtn?.addEventListener("click", async () => {
  const urls = [...state.selectedSet];
  if (urls.length === 0) return toast("Select at least one link.");
  try {
    await navigator.clipboard.writeText(urls.join("\n"));

    chrome.tabs.create({ url: "https://notebooklm.google.com/" }, (tab) => {
      // If assist is enabled, ping the content script when the tab finishes loading.
      if (state.settings.assistEnabled && tab?.id) {
        const tabId = tab.id;
        const listener = (updatedTabId, changeInfo) => {
          if (updatedTabId === tabId && changeInfo.status === "complete") {
            chrome.tabs.onUpdated.removeListener(listener);
            // Best-effort: tell the content script to focus Add sources
            chrome.tabs.sendMessage(tabId, { type: "ASSIST_FOCUS" }, () => {
              // ignore lastError if script not ready
              void chrome.runtime.lastError;
            });
          }
        };
        chrome.tabs.onUpdated.addListener(listener);
      }
    });

    toast(`Copied ${urls.length} link(s) to clipboard. NotebookLM opened—paste into “Add sources”.`);
  } catch (e) {
    toast(`Clipboard/tab error: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// Save settings button
saveSettingsBtn?.addEventListener("click", async () => {
  const settings = getSettingsFromUI();
  Object.assign(state.settings, settings);

  const persistKey = !!(rememberKeyEl && rememberKeyEl.checked);
  await saveSettingsToStorage(state.settings, persistKey);
  toast("Settings saved.");
});

// Persist assist toggle immediately when changed (quality-of-life)
assistEnabledEl?.addEventListener("change", async () => {
  state.settings.assistEnabled = !!assistEnabledEl.checked;
  const persistKey = !!(rememberKeyEl && rememberKeyEl.checked);
  await saveSettingsToStorage({ ...state.settings, apiKey: apiKeyEl.value.trim() }, persistKey);
  toast(state.settings.assistEnabled ? "NotebookLM Assist enabled." : "NotebookLM Assist disabled.");
});

/* ------------------------------ render ------------------------------- */

function resetList() {
  state.allUrls = [];
  state.matchesSet = new Set();
  state.selectedSet = new Set();
  state.results = {};
  urlList.innerHTML = "";
  updateCounts();
  insertBtn.disabled = true;
}

function applyShowMatches() {
  renderList();
}

function renderList() {
  const urls = state.allUrls;
  urlList.innerHTML = "";
  const frag = document.createDocumentFragment();

  const showMatchesOnly = showMatchesOnlyEl?.checked ?? true;
  const matches = state.matchesSet;
  let visibleCount = 0;

  for (const url of urls) {
    const isMatch = matches.size ? matches.has(url) : true;
    if (showMatchesOnly && !isMatch) continue;
    visibleCount++;

    const li = document.createElement("li");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.setAttribute("data-row", "sel");
    cb.setAttribute("data-url", url);
    cb.addEventListener("change", () => {
      if (cb.checked) state.selectedSet.add(url);
      else state.selectedSet.delete(url);
      insertBtn.disabled = state.selectedSet.size === 0;
      updateCounts();
    });

    const code = document.createElement("code");
    code.textContent = url;

    const tag = document.createElement("span");
    tag.className = "tag";
    if (state.results[url]) {
      const s = document.createElement("span");
      s.className = "score";
      s.textContent = (state.results[url].score ?? 0).toFixed(2);
      tag.textContent = isMatch ? "match " : "no-match ";
      tag.appendChild(s);
    } else {
      tag.textContent = "–";
    }

    li.appendChild(cb);
    li.appendChild(code);
    li.appendChild(tag);
    frag.appendChild(li);
  }
  urlList.appendChild(frag);

  // Re-check previously selected
  document.querySelectorAll('input[data-row="sel"]').forEach((el) => {
    const u = el.getAttribute("data-url");
    el.checked = state.selectedSet.has(u);
  });

  updateCounts(visibleCount);
  insertBtn.disabled = state.selectedSet.size === 0;
}

function updateCounts(visibleCount = undefined) {
  const total = state.allUrls.length;
  const matches = state.matchesSet.size || 0;
  const selected = state.selectedSet.size;
  const shown = visibleCount ?? document.querySelectorAll('#urlList li').length;
  countsEl.textContent = `All: ${total} · Matches: ${matches} · Shown: ${shown} · Selected: ${selected}`;
}

function toast(msg) {
  logEl.textContent = msg;
}

/* --------------------------- settings utils -------------------------- */

function getSettingsFromUI() {
  return {
    provider: providerEl.value,
    endpoint: endpointEl.value.trim(),
    model: modelEl.value.trim(),
    apiKey: apiKeyEl.value.trim(),
    batchSize: Number(batchSizeEl.value || 100),
    metaLimit: Number(metaLimitEl.value || 200),
    assistEnabled: !!(assistEnabledEl && assistEnabledEl.checked)
  };
}

async function saveSettingsToStorage(settings, persistKey) {
  const toStore = {
    settings: { ...settings, apiKey: persistKey ? settings.apiKey : undefined },
    apiKeyPersisted: !!persistKey
  };
  await chrome.storage.local.set(toStore);
}
