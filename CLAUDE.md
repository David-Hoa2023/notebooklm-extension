# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chrome extension (Manifest V3) that extracts URLs from website sitemaps, filters them by topic using LLM, and inserts selected links into NotebookLM. The extension uses ES6 modules in the service worker and has no build process - it runs directly from source files.

## Architecture

### Core Components

- **Service Worker** (`scr/sw.js`): Background script handling sitemap extraction, web crawling, and LLM filtering
- **Popup Interface** (`scr/popup.js`, `scr/popup.html`): Main UI for user interaction
- **Content Script** (`content/notebooklm-assist.js`): Minimal integration with NotebookLM for auto-focus
- **Options Page** (`options.html`, `options.js`): Settings configuration

### Key Libraries (ES6 Modules)

- `scr/lib/sitemap.js`: Sitemap extraction and URL discovery
- `scr/lib/llmFilter.js`: LLM-based topic filtering (supports OpenAI and generic endpoints)
- `scr/lib/crawler.js`: Web crawling for URL discovery

## Development Commands

This extension has no build process or package.json. Development workflow:

1. **Load Extension**: Chrome → `chrome://extensions/` → Developer mode → Load unpacked → Select extension folder
2. **Reload Changes**: Click refresh button in Chrome extensions page after code changes
3. **Debug Service Worker**: Click "Inspect views: service worker" in extensions page
4. **Debug Popup**: Right-click extension icon → Inspect popup

## Testing Approach

Manual testing through Chrome Developer Mode:
- Test sitemap extraction with various websites
- Verify LLM filtering with different topics and providers
- Test NotebookLM integration and auto-focus
- Check settings persistence in Chrome storage

## Chrome Extension Specifics

- **Manifest V3**: Uses service workers instead of background pages
- **Permissions**: storage, activeTab, scripting, clipboardWrite, host_permissions for all sites
- **Storage**: Uses `chrome.storage.local` for settings persistence
- **Messaging**: Service worker communicates with popup via `chrome.runtime.onMessage`

## LLM Integration

Supports two providers:
- **OpenAI**: Direct integration with Chat Completions API
- **Generic JSON**: Custom endpoints accepting `{topic, items}` returning `[{url, match, score}]`

Settings stored in Chrome local storage, API keys optionally persisted.