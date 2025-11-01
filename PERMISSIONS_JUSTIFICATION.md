# Permissions Justification for Chrome Web Store

This document explains why each permission is necessary for the extension's functionality.

## Required Permissions

### 1. `storage`
**Usage:** Storing user settings and preferences
- **Files using it:** `popup.js`, `options.js`, `content/notebooklm-assist.js`
- **Purpose:** 
  - Saves LLM API settings (endpoint, model, API key if user chooses)
  - Stores user preferences for auto-assist mode
  - Persists batch size and metadata fetch limits

### 2. `tabs`
**Usage:** Managing browser tabs for NotebookLM integration
- **Files using it:** `scr/sw.js`, `scr/popup.js`
- **Purpose:**
  - Query existing NotebookLM tabs to avoid duplicates
  - Create new tabs to open NotebookLM
  - Update tab focus when inserting content
  - Send messages to content scripts in specific tabs

## Host Permissions

### 1. `*://*/*`
**Usage:** Fetching sitemaps and crawling websites
- **Files using it:** `scr/sw.js`, `scr/lib/sitemap.js`, `scr/lib/crawler.js`
- **Purpose:**
  - Extract URLs from any website's sitemap
  - Crawl websites to discover URLs
  - Fetch page titles and descriptions for LLM context

### 2. `https://notebooklm.google.com/*`
**Usage:** Content script injection for NotebookLM integration
- **Files using it:** `content/notebooklm-assist.js`
- **Purpose:**
  - Programmatically insert URLs into NotebookLM
  - Detect and interact with notebook selection
  - Auto-focus input fields when enabled

## Removed Permissions

### ~~`scripting`~~ (REMOVED)
- **Reason for removal:** Not used. Content scripts are declared statically in manifest.json

### ~~`clipboardWrite`~~ (REMOVED)
- **Reason for removal:** No longer needed after implementing direct programmatic insertion

### ~~`activeTab`~~ (REMOVED)
- **Reason for removal:** Not needed. We use specific `tabs` permission with content scripts

## Notes for Chrome Web Store Review

1. All permissions are actively used and necessary for core functionality
2. The broad host permission `*://*/*` is required because users need to extract sitemaps from any website they choose
3. The extension cannot predict which websites users will want to analyze
4. Each permission has been audited and unused ones have been removed