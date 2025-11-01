#!/usr/bin/env python3
"""
Bulk import script for NotebookLM
Reads notebooks and sources from CSV/Excel/JSON files and imports them
"""

import asyncio
import json
import yaml
import pandas as pd
from pathlib import Path
from typing import List, Dict
import logging
from notebooklm_automation import NotebookLMAutomation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BulkImporter:
    """Handle bulk import of notebooks and sources from various file formats"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize with configuration"""
        self.config = self.load_config(config_path)
        self.automation = NotebookLMAutomation(
            headless=self.config['browser']['headless']
        )
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
            
    def load_from_csv(self, csv_path: str) -> List[Dict]:
        """
        Load notebooks data from CSV file
        Expected columns: notebook_name, source_url
        """
        df = pd.read_csv(csv_path)
        
        # Group by notebook name
        notebooks = []
        for notebook_name, group in df.groupby('notebook_name'):
            notebooks.append({
                'name': notebook_name,
                'sources': group['source_url'].tolist()
            })
            
        logger.info(f"Loaded {len(notebooks)} notebooks from CSV")
        return notebooks
        
    def load_from_excel(self, excel_path: str, sheet_name: str = 'Sheet1') -> List[Dict]:
        """
        Load notebooks data from Excel file
        Expected columns: notebook_name, source_url
        """
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        
        # Group by notebook name
        notebooks = []
        for notebook_name, group in df.groupby('notebook_name'):
            notebooks.append({
                'name': notebook_name,
                'sources': group['source_url'].dropna().tolist()
            })
            
        logger.info(f"Loaded {len(notebooks)} notebooks from Excel")
        return notebooks
        
    def load_from_json(self, json_path: str) -> List[Dict]:
        """
        Load notebooks data from JSON file
        Expected format: [{"name": "...", "sources": ["url1", "url2", ...]}]
        """
        with open(json_path, 'r') as f:
            notebooks = json.load(f)
            
        logger.info(f"Loaded {len(notebooks)} notebooks from JSON")
        return notebooks
        
    async def import_notebooks(self, notebooks_data: List[Dict]) -> Dict:
        """Import notebooks with progress tracking"""
        results = {
            'successful': [],
            'failed': [],
            'total': len(notebooks_data)
        }
        
        try:
            # Initialize browser
            user_data_dir = self.config['browser'].get('user_data_dir')
            await self.automation.init_browser(user_data_dir)
            
            # Login if needed
            await self.automation.login_if_needed()
            
            # Process each notebook
            for i, notebook in enumerate(notebooks_data, 1):
                name = notebook['name']
                sources = notebook.get('sources', [])
                
                logger.info(f"[{i}/{len(notebooks_data)}] Processing: {name}")
                
                try:
                    # Create notebook
                    success = await self.automation.create_new_notebook(name)
                    
                    if success and sources:
                        # Add sources in batches
                        batch_size = self.config['bulk_operations']['batch_size']
                        for j in range(0, len(sources), batch_size):
                            batch = sources[j:j+batch_size]
                            await self.automation.add_sources(batch)
                            
                            # Delay between batches
                            if j + batch_size < len(sources):
                                await asyncio.sleep(
                                    self.config['notebooklm']['delays']['between_bulk_ops']
                                )
                    
                    if success:
                        results['successful'].append(name)
                        logger.info(f"✓ Successfully imported: {name}")
                    else:
                        results['failed'].append(name)
                        logger.error(f"✗ Failed to import: {name}")
                        
                except Exception as e:
                    results['failed'].append(name)
                    logger.error(f"✗ Error importing {name}: {e}")
                    
                # Delay between notebooks
                if i < len(notebooks_data):
                    await asyncio.sleep(
                        self.config['notebooklm']['delays']['between_bulk_ops']
                    )
                    
        finally:
            await self.automation.close()
            
        return results
        
    async def run(self, data_source: str, file_path: str):
        """
        Run the bulk import
        
        Args:
            data_source: Type of data source ('csv', 'excel', 'json')
            file_path: Path to the data file
        """
        # Load data based on source type
        if data_source == 'csv':
            notebooks_data = self.load_from_csv(file_path)
        elif data_source == 'excel':
            notebooks_data = self.load_from_excel(file_path)
        elif data_source == 'json':
            notebooks_data = self.load_from_json(file_path)
        else:
            raise ValueError(f"Unsupported data source: {data_source}")
            
        # Import notebooks
        results = await self.import_notebooks(notebooks_data)
        
        # Print summary
        logger.info("\n" + "="*50)
        logger.info("IMPORT SUMMARY")
        logger.info("="*50)
        logger.info(f"Total notebooks: {results['total']}")
        logger.info(f"Successful: {len(results['successful'])}")
        logger.info(f"Failed: {len(results['failed'])}")
        
        if results['failed']:
            logger.info("\nFailed imports:")
            for name in results['failed']:
                logger.info(f"  - {name}")
                
        return results


def create_sample_files():
    """Create sample data files for testing"""
    
    # Sample CSV
    csv_data = """notebook_name,source_url
AI Research,https://arxiv.org/abs/2307.09288
AI Research,https://arxiv.org/abs/2303.08774
AI Research,https://openai.com/research
Python Tutorials,https://docs.python.org/3/tutorial/
Python Tutorials,https://realpython.com/
Python Tutorials,https://www.w3schools.com/python/
Web Development,https://developer.mozilla.org/
Web Development,https://react.dev/
Web Development,https://vuejs.org/"""
    
    with open('sample_notebooks.csv', 'w') as f:
        f.write(csv_data)
        
    # Sample JSON
    json_data = [
        {
            "name": "Machine Learning Resources",
            "sources": [
                "https://scikit-learn.org/stable/",
                "https://pytorch.org/tutorials/",
                "https://www.tensorflow.org/tutorials",
                "https://huggingface.co/docs"
            ]
        },
        {
            "name": "Data Science Tools",
            "sources": [
                "https://pandas.pydata.org/docs/",
                "https://numpy.org/doc/stable/",
                "https://matplotlib.org/stable/tutorials/index.html"
            ]
        }
    ]
    
    with open('sample_notebooks.json', 'w') as f:
        json.dump(json_data, f, indent=2)
        
    # Sample Excel (requires pandas)
    df = pd.DataFrame({
        'notebook_name': [
            'Cloud Computing', 'Cloud Computing', 'Cloud Computing',
            'DevOps', 'DevOps', 'DevOps'
        ],
        'source_url': [
            'https://aws.amazon.com/documentation/',
            'https://cloud.google.com/docs',
            'https://docs.microsoft.com/en-us/azure/',
            'https://docs.docker.com/',
            'https://kubernetes.io/docs/',
            'https://docs.github.com/en/actions'
        ]
    })
    df.to_excel('sample_notebooks.xlsx', index=False)
    
    logger.info("Created sample files: sample_notebooks.csv, sample_notebooks.json, sample_notebooks.xlsx")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bulk import notebooks to NotebookLM')
    parser.add_argument('--source', choices=['csv', 'excel', 'json'], 
                       default='csv', help='Data source type')
    parser.add_argument('--file', required=False, help='Path to data file')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--create-samples', action='store_true', 
                       help='Create sample data files')
    
    args = parser.parse_args()
    
    if args.create_samples:
        create_sample_files()
        return
        
    if not args.file:
        # Use default sample file based on source type
        file_map = {
            'csv': 'sample_notebooks.csv',
            'excel': 'sample_notebooks.xlsx',
            'json': 'sample_notebooks.json'
        }
        args.file = file_map[args.source]
        
        if not Path(args.file).exists():
            logger.error(f"File not found: {args.file}")
            logger.info("Run with --create-samples to create sample files")
            return
            
    # Run bulk import
    importer = BulkImporter(args.config)
    await importer.run(args.source, args.file)


if __name__ == '__main__':
    asyncio.run(main())