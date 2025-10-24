# NotebookLM Extension - Sitemap Filter Insert

A Chrome extension that extracts URLs from website sitemaps, filters them by topic using LLM, and inserts selected links into NotebookLM.

## Features

- **Sitemap Extraction**: Automatically discover and extract URLs from website sitemaps
- **Web Crawling**: Alternative method to crawl websites and discover URLs by following links
- **Manual URL Input**: Paste URLs manually for processing
- **LLM Topic Filtering**: Use AI to filter URLs by relevance to specific topics
- **NotebookLM Integration**: Seamlessly insert filtered URLs into NotebookLM
- **Auto-focus Assist**: Optional feature to automatically focus the "Add sources" field in NotebookLM

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/David-Hoa2023/notebooklm-extension.git
   ```

2. Open Chrome and navigate to `chrome://extensions/`

3. Enable "Developer mode" in the top right corner

4. Click "Load unpacked" and select the extension folder

5. The extension icon should appear in your Chrome toolbar

## Usage

### 1. Extract URLs

**Option A: Sitemap Extraction**
- Enter a website URL (e.g., `https://example.com`)
- Click "Extract Links" to discover URLs from sitemaps

**Option B: Web Crawling**
- Enter a start URL
- Configure crawl depth (1-5 levels) and maximum pages
- Choose whether to stay within the same domain
- Click "Crawl Website"

**Option C: Manual Input**
- Paste URLs manually (one per line)
- Click "Load URLs"

### 2. Filter by Topic

- Enter a topic keyword (e.g., "AI ethics", "machine learning")
- Adjust the relevance threshold (0.0 - 1.0)
- Configure LLM settings:
  - Provider: OpenAI or Generic JSON endpoint
  - API endpoint and key
  - Batch size and metadata limits
- Click "Filter" to process URLs with AI

### 3. Select and Insert

- Review filtered URLs with relevance scores
- Select desired URLs using checkboxes
- Click "Insert into NotebookLM" to copy links and open NotebookLM
- Paste the links into the "Add sources" field

## Configuration

### LLM Settings

The extension supports multiple LLM providers:

**OpenAI**
- Endpoint: `https://api.openai.com/v1/chat/completions`
- Models: `gpt-4o-mini`, `gpt-4`, `gpt-3.5-turbo`
- API Key: Your OpenAI API key

**Generic JSON Endpoint**
- Custom endpoint that accepts `{topic, items}` and returns `[{url, match, score}]`
- Useful for self-hosted LLM services

### Settings Page

Access the settings page by clicking the "Cài đặt" (Settings) button in the popup to configure:
- LLM endpoint and API key
- Batch processing size
- Metadata fetch limits
- NotebookLM notebook ID

## File Structure

```
notebooklm_extension/
├── manifest.json              # Extension manifest
├── content/
│   └── notebooklm-assist.js   # Content script for NotebookLM integration
├── icons/
│   ├── icon48.png            # Extension icon (48px)
│   └── icon128.png           # Extension icon (128px)
├── scr/
│   ├── lib/
│   │   ├── crawler.js        # Web crawling functionality
│   │   ├── llmFilter.js      # LLM topic filtering
│   │   └── sitemap.js        # Sitemap extraction
│   ├── popup.html            # Main popup interface
│   ├── popup.css            # Popup styling
│   ├── popup.js             # Popup logic
│   └── sw.js                # Background service worker
├── options.html              # Settings page
├── options.js               # Settings page logic
└── README.md                # This file
```

## Technical Details

### Permissions

- `storage`: Save user settings and preferences
- `activeTab`: Access current tab information
- `scripting`: Inject content scripts
- `clipboardWrite`: Copy URLs to clipboard
- `host_permissions`: Access all websites and NotebookLM

### Architecture

- **Manifest V3**: Uses modern Chrome extension architecture
- **Service Worker**: Background processing for sitemap extraction and LLM filtering
- **Content Script**: Minimal integration with NotebookLM for auto-focus
- **Popup Interface**: Main user interface for the extension

### LLM Integration

The extension uses a flexible LLM integration system:
- Supports OpenAI's Chat Completions API
- Generic JSON endpoint support for custom LLM services
- Batch processing for efficiency
- Configurable concurrency and timeouts

## Development

### Prerequisites

- Chrome browser with developer mode enabled
- Basic understanding of Chrome extensions

### Building

No build process required - the extension runs directly from source files.

### Testing

1. Load the extension in Chrome developer mode
2. Test sitemap extraction with various websites
3. Verify LLM filtering with different topics
4. Test NotebookLM integration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please check the repository for license details.

## Support

For issues and questions:
- Create an issue in the GitHub repository
- Check the extension's settings page for configuration help
- Ensure your LLM API credentials are correct

## Changelog

### Version 1.0.0
- Initial release
- Sitemap extraction functionality
- Web crawling alternative
- LLM topic filtering
- NotebookLM integration
- Auto-focus assist feature
- Settings page for configuration
