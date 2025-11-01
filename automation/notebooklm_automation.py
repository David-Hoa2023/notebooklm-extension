#!/usr/bin/env python3
"""
NotebookLM Automation Script using Playwright
Automates bulk operations for NotebookLM including creating notebooks and adding sources
"""

import asyncio
import json
import time
from typing import List, Dict, Optional
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser, ElementHandle
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NotebookLMAutomation:
    """Automate NotebookLM operations using Playwright"""
    
    def __init__(self, headless: bool = False):
        """
        Initialize the automation class
        
        Args:
            headless: Run browser in headless mode (False for debugging)
        """
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context = None
        
    async def init_browser(self, user_data_dir: Optional[str] = None):
        """
        Initialize the browser with persistent context
        
        Args:
            user_data_dir: Path to Chrome user data directory for persistent login
        """
        playwright = await async_playwright().start()
        
        if user_data_dir:
            # Use persistent context to maintain login
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled'],
                viewport={'width': 1280, 'height': 720}
            )
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        else:
            # Use regular browser
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            self.page = await self.context.new_page()
            
        logger.info("Browser initialized")
        
    async def login_if_needed(self):
        """Check if login is needed and wait for manual login if required"""
        await self.page.goto('https://notebooklm.google.com')
        
        # Check if we're on a login page
        if 'accounts.google.com' in self.page.url:
            logger.info("Login required. Please log in manually in the browser window...")
            logger.info("Press Enter after logging in successfully...")
            
            if not self.headless:
                input("Press Enter after logging in...")
            else:
                logger.error("Cannot login in headless mode. Use persistent context with user_data_dir")
                raise Exception("Login required but running in headless mode")
                
        await self.page.wait_for_load_state('networkidle')
        logger.info("Successfully logged in to NotebookLM")
        
    async def create_new_notebook(self, notebook_name: Optional[str] = None) -> bool:
        """
        Create a new notebook by clicking the 'Create new' button
        
        Args:
            notebook_name: Optional name for the notebook
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Creating new notebook...")
            
            # Wait for and click the "Create new" button
            # Try multiple selectors as the UI might vary
            create_button_selectors = [
                'button:has-text("Create new")',
                '[aria-label*="Create new"]',
                'button:has-text("+ Create new")',
                'button:has-text("New notebook")',
                '[role="button"]:has-text("Create new")',
                # Based on your screenshot
                'text="Create new"',
                'button >> text="Create new"'
            ]
            
            button_clicked = False
            for selector in create_button_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    await self.page.click(selector)
                    button_clicked = True
                    logger.info(f"Clicked create button using selector: {selector}")
                    break
                except:
                    continue
                    
            if not button_clicked:
                logger.error("Could not find 'Create new' button")
                return False
                
            # Wait for the new notebook to be created
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)  # Give it time to fully load
            
            # If a name is provided, try to rename the notebook
            if notebook_name:
                await self.rename_notebook(notebook_name)
                
            logger.info("Successfully created new notebook")
            return True
            
        except Exception as e:
            logger.error(f"Error creating notebook: {e}")
            return False
            
    async def rename_notebook(self, name: str) -> bool:
        """
        Rename the current notebook
        
        Args:
            name: New name for the notebook
        """
        try:
            # Try to find and click on the notebook title to edit it
            title_selectors = [
                '[contenteditable="true"]',
                'h1[contenteditable="true"]',
                '[aria-label*="notebook name"]',
                '[aria-label*="title"]'
            ]
            
            for selector in title_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    await element.click()
                    await element.fill(name)
                    await self.page.keyboard.press('Enter')
                    logger.info(f"Renamed notebook to: {name}")
                    return True
                except:
                    continue
                    
            logger.warning("Could not rename notebook")
            return False
            
        except Exception as e:
            logger.error(f"Error renaming notebook: {e}")
            return False
            
    async def add_sources(self, sources: List[str], source_type: str = 'url') -> bool:
        """
        Add multiple sources to the current notebook
        
        Args:
            sources: List of sources (URLs, text, or file paths)
            source_type: Type of source ('url', 'text', or 'file')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Adding {len(sources)} sources...")
            
            # Find and click the "Add sources" button
            add_sources_selectors = [
                'button:has-text("Add source")',
                'button:has-text("Add sources")',
                '[aria-label*="Add source"]',
                'button:has-text("+")',
                '[role="button"]:has-text("Add")',
                'text="Add source"'
            ]
            
            button_clicked = False
            for selector in add_sources_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    await self.page.click(selector)
                    button_clicked = True
                    logger.info(f"Clicked add sources button using selector: {selector}")
                    break
                except:
                    continue
                    
            if not button_clicked:
                logger.error("Could not find 'Add sources' button")
                return False
                
            # Wait for the dialog/input field to appear
            await asyncio.sleep(1)
            
            # Find the input field for sources
            input_selectors = [
                'textarea[placeholder*="source"]',
                'input[placeholder*="source"]',
                'textarea[placeholder*="link"]',
                'input[placeholder*="link"]',
                'textarea[placeholder*="URL"]',
                'input[placeholder*="URL"]',
                '[contenteditable="true"]',
                'textarea',
                'input[type="text"]'
            ]
            
            input_found = False
            for selector in input_selectors:
                try:
                    input_element = await self.page.wait_for_selector(selector, timeout=3000)
                    
                    if source_type == 'url':
                        # For URLs, join with newlines
                        sources_text = '\n'.join(sources)
                        await input_element.fill(sources_text)
                    elif source_type == 'text':
                        # For text, join with double newlines
                        sources_text = '\n\n'.join(sources)
                        await input_element.fill(sources_text)
                    else:
                        logger.error(f"Unsupported source type: {source_type}")
                        return False
                        
                    input_found = True
                    logger.info(f"Filled input field with {len(sources)} sources")
                    break
                except:
                    continue
                    
            if not input_found:
                logger.error("Could not find input field for sources")
                return False
                
            # Click the submit/add button
            submit_selectors = [
                'button:has-text("Add")',
                'button:has-text("Insert")',
                'button:has-text("Submit")',
                'button[type="submit"]',
                '[aria-label*="Submit"]',
                '[aria-label*="Add"]'
            ]
            
            for selector in submit_selectors:
                try:
                    await self.page.click(selector, timeout=3000)
                    logger.info("Clicked submit button")
                    break
                except:
                    continue
                    
            # Wait for sources to be processed
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)  # Give it time to process
            
            logger.info("Successfully added sources")
            return True
            
        except Exception as e:
            logger.error(f"Error adding sources: {e}")
            return False
            
    async def get_notebooks_list(self) -> List[Dict[str, str]]:
        """
        Get list of existing notebooks
        
        Returns:
            List of notebook dictionaries with 'id' and 'title'
        """
        notebooks = []
        
        try:
            # Navigate to the main page if not already there
            if 'notebook' not in self.page.url:
                await self.page.goto('https://notebooklm.google.com')
                await self.page.wait_for_load_state('networkidle')
            
            # Find notebook elements
            notebook_selectors = [
                '[role="listitem"]',
                '.notebook-item',
                '[data-notebook-id]',
                'article',
                '[aria-label*="notebook"]'
            ]
            
            for selector in notebook_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        for element in elements:
                            title = await element.text_content()
                            # Try to get ID from attributes
                            notebook_id = await element.get_attribute('data-notebook-id') or \
                                        await element.get_attribute('data-id') or \
                                        await element.get_attribute('id') or \
                                        title
                            
                            if title:
                                notebooks.append({
                                    'id': notebook_id,
                                    'title': title.strip()
                                })
                        break
                except:
                    continue
                    
            logger.info(f"Found {len(notebooks)} notebooks")
            return notebooks
            
        except Exception as e:
            logger.error(f"Error getting notebooks list: {e}")
            return notebooks
            
    async def select_notebook(self, notebook_id_or_title: str) -> bool:
        """
        Select an existing notebook by ID or title
        
        Args:
            notebook_id_or_title: Notebook ID or title to select
        """
        try:
            # Try to find and click the notebook
            selectors = [
                f'[data-notebook-id="{notebook_id_or_title}"]',
                f'[data-id="{notebook_id_or_title}"]',
                f'text="{notebook_id_or_title}"',
                f'[aria-label*="{notebook_id_or_title}"]'
            ]
            
            for selector in selectors:
                try:
                    await self.page.click(selector, timeout=3000)
                    logger.info(f"Selected notebook: {notebook_id_or_title}")
                    await self.page.wait_for_load_state('networkidle')
                    return True
                except:
                    continue
                    
            logger.error(f"Could not find notebook: {notebook_id_or_title}")
            return False
            
        except Exception as e:
            logger.error(f"Error selecting notebook: {e}")
            return False
            
    async def bulk_create_notebooks_with_sources(self, notebooks_data: List[Dict]) -> Dict[str, bool]:
        """
        Create multiple notebooks with their respective sources
        
        Args:
            notebooks_data: List of dictionaries with 'name' and 'sources' keys
            
        Returns:
            Dictionary with notebook names and success status
        """
        results = {}
        
        for notebook in notebooks_data:
            name = notebook.get('name', f'Notebook {time.time()}')
            sources = notebook.get('sources', [])
            
            logger.info(f"Creating notebook: {name}")
            
            # Create new notebook
            if await self.create_new_notebook(name):
                # Add sources
                if sources:
                    success = await self.add_sources(sources, source_type='url')
                    results[name] = success
                else:
                    results[name] = True
            else:
                results[name] = False
                
            # Small delay between operations
            await asyncio.sleep(2)
            
        return results
        
    async def close(self):
        """Close the browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")


async def main():
    """Example usage of the NotebookLM automation"""
    
    # Example data for bulk operations
    notebooks_to_create = [
        {
            'name': 'AI Research Papers',
            'sources': [
                'https://arxiv.org/abs/2307.09288',  # Llama 2 paper
                'https://arxiv.org/abs/2303.08774',  # GPT-4 paper
                'https://arxiv.org/abs/2305.10403',  # Anthropic Constitutional AI
            ]
        },
        {
            'name': 'Python Documentation',
            'sources': [
                'https://docs.python.org/3/tutorial/',
                'https://docs.python.org/3/library/',
                'https://realpython.com/python-first-steps/',
            ]
        },
        {
            'name': 'Web Development Resources',
            'sources': [
                'https://developer.mozilla.org/en-US/docs/Web/JavaScript',
                'https://react.dev/learn',
                'https://vuejs.org/guide/',
            ]
        }
    ]
    
    # Initialize automation
    automation = NotebookLMAutomation(headless=False)  # Set to True for headless mode
    
    try:
        # Initialize browser
        # Use persistent context to maintain login
        # Replace with your Chrome profile path for persistent login
        # Windows: C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data
        # Mac: /Users/YourName/Library/Application Support/Google/Chrome
        # Linux: /home/YourName/.config/google-chrome
        
        await automation.init_browser()  # Add user_data_dir parameter for persistent login
        
        # Login if needed
        await automation.login_if_needed()
        
        # Example 1: Create a single notebook with sources
        logger.info("Creating single notebook...")
        await automation.create_new_notebook("Test Notebook")
        await automation.add_sources([
            'https://example.com/page1',
            'https://example.com/page2',
            'https://example.com/page3'
        ])
        
        # Wait a bit between operations
        await asyncio.sleep(3)
        
        # Example 2: Bulk create notebooks with sources
        logger.info("Starting bulk notebook creation...")
        results = await automation.bulk_create_notebooks_with_sources(notebooks_to_create)
        
        # Print results
        logger.info("Bulk creation results:")
        for name, success in results.items():
            status = "✓" if success else "✗"
            logger.info(f"  {status} {name}")
            
        # Example 3: Get list of notebooks
        notebooks = await automation.get_notebooks_list()
        logger.info(f"Found {len(notebooks)} notebooks:")
        for nb in notebooks:
            logger.info(f"  - {nb['title']} (ID: {nb['id']})")
            
    except Exception as e:
        logger.error(f"Automation error: {e}")
        
    finally:
        await automation.close()


if __name__ == '__main__':
    asyncio.run(main())