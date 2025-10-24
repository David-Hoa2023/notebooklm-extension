// options.js - Settings page for the extension

"use strict"

const endpointEl = document.getElementById("endpoint")
const apiKeyEl = document.getElementById("apiKey")
const batchSizeEl = document.getElementById("batchSize")
const metaLimitEl = document.getElementById("metaLimit")
const notebookIdEl = document.getElementById("notebookId")
const saveBtn = document.getElementById("saveBtn")
const backBtn = document.getElementById("backBtn")
const statusEl = document.getElementById("status")

// Load settings when page opens
chrome.storage.local.get(["settings", "apiKeyPersisted"], ({ settings, apiKeyPersisted }) => {
  if (settings) {
    if (settings.endpoint) endpointEl.value = settings.endpoint
    if (settings.apiKey && apiKeyPersisted) apiKeyEl.value = settings.apiKey
    if (settings.batchSize) batchSizeEl.value = settings.batchSize
    if (settings.metaLimit) metaLimitEl.value = settings.metaLimit
    if (settings.notebookId) notebookIdEl.value = settings.notebookId
  }
})

// Save settings when button clicked
saveBtn.addEventListener("click", async () => {
  const settings = {
    endpoint: endpointEl.value.trim(),
    apiKey: apiKeyEl.value.trim(),
    batchSize: Number(batchSizeEl.value),
    metaLimit: Number(metaLimitEl.value),
    notebookId: notebookIdEl.value.trim()
  }

  await chrome.storage.local.set({ 
    settings: settings,
    apiKeyPersisted: true 
  })

  statusEl.textContent = "Settings saved successfully!"
  setTimeout(() => {
    statusEl.textContent = ""
  }, 3000)
})

// Back button - navigate back to popup
backBtn.addEventListener("click", () => {
  // Close the options page and open the popup
  chrome.tabs.getCurrent((tab) => {
    if (tab) {
      chrome.tabs.remove(tab.id)
    }
  })
  // Try to open the popup (note: this may not work in all contexts)
  chrome.action.openPopup().catch(() => {
    // If we can't open popup programmatically, just close the tab
    // User can click the extension icon to open popup again
  })
})

