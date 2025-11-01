# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chrome extension project called "Bói Kiều" that displays random quotes from the Vietnamese literary classic "Truyện Kiều" by Nguyễn Du. The extension can fetch quotes from Google Docs or use default embedded quotes.

## Architecture

### Chrome Extension Structure (Manifest V3)
- **manifest.json**: Chrome extension configuration using Manifest V3
- **popup.html/popup.js**: Main UI that appears when clicking the extension icon
- **background.js**: Service worker for background tasks and notifications
- **quotes.js**: Helper functions for fetching quotes from Google Docs

### Key Components

1. **Quote Fetching System**
   - Fetches quotes from Google Docs via export URL (`https://docs.google.com/document/d/{docId}/export?format=txt`)
   - Falls back to hardcoded quotes if fetch fails
   - Supports both user-provided and default Google Doc IDs

2. **Notification System**
   - Sends periodic browser notifications with quotes
   - Configurable intervals (5, 10, 15, 30 minutes)
   - Uses Chrome notifications API

3. **UI Features**
   - Winamp-inspired retro design with animated visualizers
   - "Bói Kiều" fortune-telling feature for random quote display
   - Settings persistence using Chrome storage API

## Development Commands

### Installing the Extension
1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" 
3. Click "Load unpacked"
4. Select the `quote-extension` directory

### Testing Changes
- After modifying files, click the refresh icon in `chrome://extensions/` to reload the extension
- Right-click the extension icon and select "Inspect popup" to debug popup.html
- Check service worker logs via "Inspect views: service worker" in extension details

### Creating Icons
- Run `python create_icons.py` to generate required icon sizes (16x16, 48x48, 128x128)

## Important Files

- **background.js:1**: Contains hardcoded Google Doc ID that may need updating
- **popup.js**: Main logic for UI interactions and quote display
- **popup.html**: UI structure with extensive inline CSS styling

## Chrome APIs Used
- `chrome.storage.local`: For persisting user settings
- `chrome.notifications`: For displaying system notifications
- Service Worker (background.js): For scheduled tasks

## Notes
- No build process or bundling required - vanilla JavaScript
- No external dependencies except Google Fonts (Roboto)
- Uses Tailwind-inspired inline styles but not actual Tailwind CSS
- Supports offline operation with fallback quotes