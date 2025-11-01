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
const stopCrawlBtn = $("#stopCrawlBtn");
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
const notebookSelect = $("#notebookSelect");
const refreshNotebooksBtn = $("#refreshNotebooksBtn");

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
  },
  notebooks: [] // Store fetched notebooks
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
  
  // Load notebooks on startup
  loadNotebooks();
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
  
  // Show stop button, hide crawl button
  crawlBtn.style.display = "none";
  stopCrawlBtn.style.display = "inline-block";
  
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
  
  // Restore button states
  crawlBtn.style.display = "inline-block";
  stopCrawlBtn.style.display = "none";
  
  if (resp?.ok) {
    state.allUrls = resp.urls || [];
    renderList();
    toast(`Crawled ${state.allUrls.length} URL(s).`);
  } else {
    toast(`Crawl failed: ${resp?.error || "Unknown error"}`);
  }
});

// Stop crawling
stopCrawlBtn?.addEventListener("click", async () => {
  const resp = await chrome.runtime.sendMessage({ type: "STOP_CRAWL" });
  
  // Restore button states immediately
  crawlBtn.style.display = "inline-block";
  stopCrawlBtn.style.display = "none";
  
  if (resp?.ok) {
    toast("Crawl stopped.");
  } else {
    toast(`Failed to stop crawl: ${resp?.error || "Unknown error"}`);
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

// Insert into NotebookLM
insertBtn?.addEventListener("click", async () => {
  const urls = [...state.selectedSet];
  if (urls.length === 0) return toast("Select at least one link.");
  
  const selectedNotebook = notebookSelect.value;
  const isNewNotebook = selectedNotebook === "new";
  
  try {
    // Prepare the content to insert
    const content = urls.join("\n");
    
    // Send message to service worker to handle NotebookLM interaction
    const resp = await chrome.runtime.sendMessage({
      type: "INSERT_TO_NOTEBOOKLM",
      urls: urls,
      notebookId: selectedNotebook,
      createNew: isNewNotebook,
      assistEnabled: state.settings.assistEnabled
    });
    
    if (resp?.ok) {
      toast(`Successfully inserted ${urls.length} link(s) into NotebookLM.`);
      // Refresh notebooks list in case a new one was created
      if (isNewNotebook) {
        await loadNotebooks();
      }
    } else {
      toast(`Failed to insert: ${resp?.error || "Unknown error"}`);
    }
  } catch (e) {
    toast(`Error: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// Refresh notebooks list
refreshNotebooksBtn?.addEventListener("click", async () => {
  await loadNotebooks();
  toast("Notebooks list refreshed.");
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

/* --------------------------- notebook management -------------------------- */

async function loadNotebooks() {
  notebookSelect.innerHTML = '<option value="new">Create New Notebook</option>';
  notebookSelect.innerHTML += '<option value="loading" disabled>Loading notebooks...</option>';
  
  try {
    // Send message to service worker to fetch notebooks
    const resp = await chrome.runtime.sendMessage({ type: "FETCH_NOTEBOOKS" });
    
    // Clear loading option
    notebookSelect.innerHTML = '<option value="new">Create New Notebook</option>';
    
    if (resp?.ok) {
      if (resp.notebooks && resp.notebooks.length > 0) {
        state.notebooks = resp.notebooks;
        
        // Add a separator
        const separator = document.createElement('option');
        separator.disabled = true;
        separator.textContent = '──────────';
        notebookSelect.appendChild(separator);
        
        // Add existing notebooks
        resp.notebooks.forEach(notebook => {
          const option = document.createElement('option');
          option.value = notebook.id;
          option.textContent = notebook.title || `Notebook ${notebook.id}`;
          notebookSelect.appendChild(option);
        });
        
        console.log(`Loaded ${resp.notebooks.length} notebooks`);
      } else {
        // No notebooks found
        if (resp.message) {
          console.log('Notebooks fetch result:', resp.message);
        } else {
          console.log('No existing notebooks found');
        }
        
        // Add informational option
        const infoOption = document.createElement('option');
        infoOption.disabled = true;
        infoOption.textContent = '(No existing notebooks found)';
        notebookSelect.appendChild(infoOption);
      }
    } else {
      // Error occurred
      console.warn('Failed to fetch notebooks:', resp?.error);
      toast(`Failed to fetch notebooks: ${resp?.error || 'Unknown error'}`);
      
      // Add error option
      const errorOption = document.createElement('option');
      errorOption.disabled = true;
      errorOption.textContent = '(Error loading notebooks)';
      notebookSelect.appendChild(errorOption);
    }
  } catch (e) {
    console.error('Error loading notebooks:', e);
    const errorMsg = e.message || 'Unknown error';
    toast(`Error loading notebooks: ${errorMsg}`);
    
    notebookSelect.innerHTML = '<option value="new">Create New Notebook</option>';
    const errorOption = document.createElement('option');
    errorOption.disabled = true;
    
    if (errorMsg.includes('Could not establish connection')) {
      errorOption.textContent = '(Content script not loaded - reload extension)';
    } else if (errorMsg.includes('not responding')) {
      errorOption.textContent = '(Content script not responding - refresh NotebookLM)';
    } else {
      errorOption.textContent = '(Open NotebookLM to see existing notebooks)';
    }
    
    notebookSelect.appendChild(errorOption);
  }
}
