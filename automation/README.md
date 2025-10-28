# NotebookLM Browser Automation

This automation suite allows you to programmatically interact with NotebookLM using Playwright, enabling bulk operations like creating notebooks and adding sources.

## Features

- 🤖 **Automated Notebook Creation**: Click the "Create new" button programmatically
- 📚 **Bulk Source Addition**: Add multiple URLs/sources to notebooks automatically
- 🔄 **Batch Processing**: Import hundreds of notebooks from CSV/Excel/JSON files
- 🔐 **Persistent Login**: Use Chrome profile to maintain login session
- 📊 **Progress Tracking**: Real-time logging and progress reporting
- ⚙️ **Configurable**: YAML-based configuration for easy customization

## Installation

1. Install Python 3.8+ if not already installed

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

## Quick Start

### 1. Simple Usage

```python
from notebooklm_automation import NotebookLMAutomation
import asyncio

async def main():
    # Initialize automation
    automation = NotebookLMAutomation(headless=False)
    await automation.init_browser()
    
    # Login (will prompt if needed)
    await automation.login_if_needed()
    
    # Create a new notebook
    await automation.create_new_notebook("My Research")
    
    # Add sources
    await automation.add_sources([
        "https://example.com/article1",
        "https://example.com/article2"
    ])
    
    await automation.close()

asyncio.run(main())
```

### 2. Bulk Import from CSV

Create a CSV file with your notebooks:
```csv
notebook_name,source_url
AI Research,https://arxiv.org/abs/2307.09288
AI Research,https://openai.com/research
Python Tutorials,https://docs.python.org/3/
```

Run the bulk import:
```bash
python bulk_import.py --source csv --file notebooks.csv
```

### 3. Create Sample Files

Generate sample data files for testing:
```bash
python bulk_import.py --create-samples
```

## Configuration

Edit `config.yaml` to customize:

- **Browser settings**: Headless mode, viewport size, timeouts
- **Persistent login**: Set Chrome profile path to avoid re-login
- **Delays**: Adjust wait times between operations
- **Selectors**: Update if NotebookLM UI changes

### Setting Up Persistent Login

To avoid logging in each time:

1. Find your Chrome profile path:
   - Windows: `C:\Users\[YourName]\AppData\Local\Google\Chrome\User Data`
   - Mac: `/Users/[YourName]/Library/Application Support/Google/Chrome`
   - Linux: `/home/[YourName]/.config/google-chrome`

2. Update `config.yaml`:
```yaml
browser:
  user_data_dir: "C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data"
```

## Usage Examples

### Example 1: Create Multiple Notebooks

```python
notebooks_data = [
    {
        'name': 'Machine Learning',
        'sources': [
            'https://pytorch.org/tutorials/',
            'https://scikit-learn.org/'
        ]
    },
    {
        'name': 'Web Development',
        'sources': [
            'https://developer.mozilla.org/',
            'https://react.dev/'
        ]
    }
]

results = await automation.bulk_create_notebooks_with_sources(notebooks_data)
```

### Example 2: Import from Excel

```bash
python bulk_import.py --source excel --file research_notebooks.xlsx
```

### Example 3: Import from JSON

```json
[
  {
    "name": "Python Documentation",
    "sources": [
      "https://docs.python.org/3/",
      "https://realpython.com/"
    ]
  }
]
```

```bash
python bulk_import.py --source json --file notebooks.json
```

## API Reference

### NotebookLMAutomation Class

#### Methods

- `init_browser(user_data_dir=None)`: Initialize browser with optional persistent profile
- `login_if_needed()`: Check and handle login requirement
- `create_new_notebook(name=None)`: Create a new notebook
- `add_sources(sources, source_type='url')`: Add sources to current notebook
- `get_notebooks_list()`: Get list of existing notebooks
- `select_notebook(notebook_id_or_title)`: Select an existing notebook
- `bulk_create_notebooks_with_sources(notebooks_data)`: Create multiple notebooks
- `close()`: Close the browser

## Troubleshooting

### Issue: "Could not find 'Create new' button"

The UI might have changed. Update selectors in `config.yaml` or check the page manually:

```python
# Debug mode - keeps browser open
automation = NotebookLMAutomation(headless=False)
```

### Issue: Login Required in Headless Mode

Use persistent context with your Chrome profile:

```python
await automation.init_browser(user_data_dir="path/to/chrome/profile")
```

### Issue: Rate Limiting

Increase delays in `config.yaml`:

```yaml
delays:
  between_bulk_ops: 5  # Increase to 5 seconds
```

## Advanced Usage

### Custom Selectors

If NotebookLM's UI changes, update selectors in code:

```python
# Add custom selector
create_button_selectors = [
    'button:has-text("Create new")',
    'your-custom-selector-here'
]
```

### Error Handling

The automation includes retry logic and error handling:

```python
try:
    await automation.create_new_notebook()
except Exception as e:
    logger.error(f"Failed: {e}")
    # Implement retry logic
```

## Data File Formats

### CSV Format
```csv
notebook_name,source_url
Research Topic,https://example.com/paper1
Research Topic,https://example.com/paper2
```

### Excel Format
Same structure as CSV, saved as .xlsx

### JSON Format
```json
[
  {
    "name": "Notebook Name",
    "sources": ["url1", "url2", "url3"]
  }
]
```

## Best Practices

1. **Start with small batches**: Test with 2-3 notebooks first
2. **Use delays**: Avoid overwhelming the service
3. **Monitor progress**: Check logs for errors
4. **Save session**: Use persistent Chrome profile
5. **Handle errors**: Implement retry logic for failed operations

## Limitations

- Requires active Google account login
- Subject to NotebookLM's rate limits
- UI changes may break selectors
- File upload sources not yet implemented

## Contributing

Feel free to submit issues or pull requests to improve the automation.

## License

This automation tool is for educational and productivity purposes. Please respect NotebookLM's terms of service.