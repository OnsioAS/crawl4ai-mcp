#!/usr/bin/env python3
"""
Crawl4AI MCP Server

This MCP server provides web crawling functionality to Claude Desktop
using the crawl4ai library. It enables various web crawling operations
with intelligent content extraction.
"""

import asyncio
import json
import os
import sys
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

# Import MCP SDK
from mcp.server.fastmcp import FastMCP
from mcp import Tool

# Import crawl4ai components
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel, Field

# Import dotenv for environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file if it exists
except ImportError:
    pass  # dotenv is optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawl4ai_mcp.log"))
    ]
)
logger = logging.getLogger("crawl4ai_mcp")

# Initialize FastMCP server
mcp = FastMCP("crawl4ai")

class ScrapingResult(BaseModel):
    """Structured result from a web scraping operation"""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    
class MultiCrawlResult(BaseModel):
    """Result containing multiple scraping results"""
    results: List[ScrapingResult] = []

def get_llm_config() -> LLMConfig:
    """Create LLM config based on environment variables"""
    # Try to get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    # If no API key, try other providers or warn
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY found in environment variables")
        logger.info("Will rely on crawl4ai's default extraction methods")
        
    # Create LLM config
    return LLMConfig(
        provider="anthropic/claude-3-opus-20240229",
        api_token=api_key,
    )

def format_content_with_citations(content: str, url: str) -> str:
    """Format content with citations"""
    if not content:
        return ""
    
    # Add citation
    if not content.endswith("\n"):
        content += "\n"
    content += f"\nSource: {url}"
    return content

def clean_markdown(text: str) -> str:
    """Clean up markdown text for better readability"""
    if not text:
        return ""
    
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Ensure headers have space after #
    text = re.sub(r'(^|\n)(#{1,6})([^ #])', r'\1\2 \3', text)
    
    return text

@mcp.tool()
async def crawl_page(url: str, instruction: str, cache_mode: str = "BYPASS") -> ScrapingResult:
    """
    Crawl a webpage and extract specific information based on instructions.
    
    Args:
        url: The URL to crawl
        instruction: Instructions for what content to extract from the page
        cache_mode: Cache mode (BYPASS, READ_ONLY, WRITE_ONLY, READ_WRITE)
    
    Returns:
        Extracted content or error message
    """
    try:
        logger.info(f"Crawling page: {url}")
        # Convert cache_mode string to enum
        cache_enum = getattr(CacheMode, cache_mode)
        
        # Create LLMConfig for the extraction
        llm_config = get_llm_config()
        
        # Create a basic extraction strategy
        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            extraction_type="raw",
            instruction=instruction,
            input_format="markdown",
            apply_chunking=True,
            chunk_token_threshold=4000,
            overlap_rate=0.2,
        )
        
        # Create crawler config
        crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=cache_enum,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=True,
        )
        
        # Configure browser
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        
        # Initialize crawler and run
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)
            
            if result.success:
                # Format content with citation
                formatted_content = format_content_with_citations(
                    clean_markdown(result.extracted_content), 
                    url
                )
                
                return ScrapingResult(
                    success=True,
                    content=formatted_content
                )
            else:
                logger.error(f"Crawling failed: {result.error_message}")
                return ScrapingResult(
                    success=False,
                    error=f"Crawling failed: {result.error_message}"
                )
    
    except Exception as e:
        logger.exception(f"Error during crawling: {str(e)}")
        return ScrapingResult(
            success=False,
            error=f"Error during crawling: {str(e)}"
        )

@mcp.tool()
async def crawl_with_schema(
    url: str, 
    instruction: str, 
    schema_json: str,
    cache_mode: str = "BYPASS"
) -> ScrapingResult:
    """
    Crawl a webpage and extract structured data according to a schema.
    
    Args:
        url: The URL to crawl
        instruction: Instructions for what content to extract from the page
        schema_json: JSON schema definition for the data to extract
        cache_mode: Cache mode (BYPASS, READ_ONLY, WRITE_ONLY, READ_WRITE)
    
    Returns:
        Extracted structured content or error message
    """
    try:
        logger.info(f"Crawling page with schema: {url}")
        # Convert cache_mode string to enum
        cache_enum = getattr(CacheMode, cache_mode)
        
        # Parse schema
        schema = json.loads(schema_json)
        
        # Create LLMConfig for the extraction
        llm_config = get_llm_config()
        
        # Create extraction strategy with schema
        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            extraction_type="schema",
            schema=schema,
            instruction=instruction,
            input_format="markdown",
            apply_chunking=True,
            chunk_token_threshold=4000,
            overlap_rate=0.2,
        )
        
        # Create crawler config
        crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=cache_enum,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=True,
        )
        
        # Configure browser
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        
        # Initialize crawler and run
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)
            
            if result.success:
                return ScrapingResult(
                    success=True,
                    content=result.extracted_content
                )
            else:
                logger.error(f"Schema crawling failed: {result.error_message}")
                return ScrapingResult(
                    success=False,
                    error=f"Crawling failed: {result.error_message}"
                )
    
    except Exception as e:
        logger.exception(f"Error during schema crawling: {str(e)}")
        return ScrapingResult(
            success=False,
            error=f"Error during crawling: {str(e)}"
        )

@mcp.tool()
async def get_page_links(url: str, cache_mode: str = "BYPASS") -> ScrapingResult:
    """
    Get all links from a webpage.
    
    Args:
        url: The URL to crawl
        cache_mode: Cache mode (BYPASS, READ_ONLY, WRITE_ONLY, READ_WRITE)
    
    Returns:
        List of links found on the page
    """
    try:
        logger.info(f"Getting links from: {url}")
        # Convert cache_mode string to enum
        cache_enum = getattr(CacheMode, cache_mode)
        
        # Create LLMConfig for the extraction
        llm_config = get_llm_config()
        
        # Create extraction strategy for links
        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            extraction_type="raw",
            instruction="Extract all links (URLs) from this webpage. Return them as a JSON array of strings.",
            input_format="markdown",
        )
        
        # Create crawler config
        crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=cache_enum,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=False,  # Include external links for this function
        )
        
        # Configure browser
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        
        # Initialize crawler and run
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)
            
            if result.success:
                # Format the links in a readable way
                try:
                    links = json.loads(result.extracted_content)
                    formatted_content = "Links found on the page:\n\n"
                    for i, link in enumerate(links, 1):
                        formatted_content += f"{i}. {link}\n"
                    formatted_content += f"\nSource: {url}"
                    return ScrapingResult(
                        success=True,
                        content=formatted_content
                    )
                except json.JSONDecodeError:
                    # If not valid JSON, return the raw content
                    return ScrapingResult(
                        success=True,
                        content=format_content_with_citations(result.extracted_content, url)
                    )
            else:
                logger.error(f"Link extraction failed: {result.error_message}")
                return ScrapingResult(
                    success=False,
                    error=f"Link extraction failed: {result.error_message}"
                )
    
    except Exception as e:
        logger.exception(f"Error during link extraction: {str(e)}")
        return ScrapingResult(
            success=False,
            error=f"Error during link extraction: {str(e)}"
        )

@mcp.tool()
async def extract_table_as_json(
    url: str,
    table_selector: str = "",
    cache_mode: str = "BYPASS"
) -> ScrapingResult:
    """
    Extract a table from a webpage and return it as structured JSON.
    
    Args:
        url: The URL to crawl
        table_selector: CSS selector for the table (if empty, will try to find the main table)
        cache_mode: Cache mode (BYPASS, READ_ONLY, WRITE_ONLY, READ_WRITE)
    
    Returns:
        Table data as JSON
    """
    try:
        logger.info(f"Extracting table from: {url}")
        # Convert cache_mode string to enum
        cache_enum = getattr(CacheMode, cache_mode)
        
        # Create LLMConfig for the extraction
        llm_config = get_llm_config()
        
        # Create extraction strategy for table
        instruction = f"Extract the table{' at ' + table_selector if table_selector else ''} and convert it to JSON with column headers as keys."
        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            extraction_type="raw",
            instruction=instruction,
            input_format="markdown",
        )
        
        # Create crawler config
        crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=cache_enum,
            process_iframes=False,
            remove_overlay_elements=True,
        )
        
        # Configure browser
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        
        # Initialize crawler and run
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)
            
            if result.success:
                # Add citation to the content
                content = result.extracted_content + f"\n\nSource: {url}"
                return ScrapingResult(
                    success=True,
                    content=content
                )
            else:
                logger.error(f"Table extraction failed: {result.error_message}")
                return ScrapingResult(
                    success=False,
                    error=f"Table extraction failed: {result.error_message}"
                )
    
    except Exception as e:
        logger.exception(f"Error during table extraction: {str(e)}")
        return ScrapingResult(
            success=False,
            error=f"Error during table extraction: {str(e)}"
        )

@mcp.tool()
async def crawl_many(
    urls: List[str],
    instruction: str,
    max_concurrency: int = 5,
    cache_mode: str = "BYPASS"
) -> MultiCrawlResult:
    """
    Crawl multiple webpages concurrently and extract content based on instructions.
    
    Args:
        urls: List of URLs to crawl
        instruction: Instructions for what content to extract from the pages
        max_concurrency: Maximum number of concurrent crawling tasks (default: 5)
        cache_mode: Cache mode (BYPASS, READ_ONLY, WRITE_ONLY, READ_WRITE)
    
    Returns:
        Extraction results for each URL
    """
    try:
        logger.info(f"Crawling multiple pages: {urls}")
        # Convert cache_mode string to enum
        cache_enum = getattr(CacheMode, cache_mode)
        
        # Create LLMConfig for the extraction
        llm_config = get_llm_config()
        
        # Create extraction strategy
        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            extraction_type="raw",
            instruction=instruction,
            input_format="markdown",
            apply_chunking=True,
        )
        
        # Create crawler config
        crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=cache_enum,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=True,
        )
        
        # Configure browser
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        
        # Configure dispatcher with memory adaptive settings
        from crawl4ai.dispatcher import MemoryAdaptiveDispatcher
        
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=70.0,  # Slow down if system memory exceeds 70%
            max_session_permit=max_concurrency,  # Maximum concurrent sessions
            poll_interval=1.0  # Check system resources every second
        )
        
        # Initialize crawler and run
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            # Use arun_many for parallel processing
            results = await crawler.arun_many(
                urls=urls,
                config=crawl_config,
                dispatcher=dispatcher
            )
            
            # Process results
            scraped_results = []
            for result in results:
                if result.success:
                    formatted_content = format_content_with_citations(
                        clean_markdown(result.extracted_content), 
                        result.url
                    )
                    scraped_results.append(
                        ScrapingResult(
                            success=True,
                            content=formatted_content
                        )
                    )
                else:
                    logger.error(f"Multi-page crawling failed for {result.url}: {result.error_message}")
                    scraped_results.append(
                        ScrapingResult(
                            success=False,
                            error=f"Crawling failed for {result.url}: {result.error_message}"
                        )
                    )
            
            return MultiCrawlResult(results=scraped_results)
    
    except Exception as e:
        logger.exception(f"Error during multi-page crawling: {str(e)}")
        # Return a MultiCrawlResult with a single error result
        return MultiCrawlResult(
            results=[
                ScrapingResult(
                    success=False,
                    error=f"Error during multi-page crawling: {str(e)}"
                )
            ]
        )


@mcp.tool()
async def crawl_many_streaming(
    urls: List[str],
    instruction: str,
    max_concurrency: int = 5,
    cache_mode: str = "BYPASS"
) -> MultiCrawlResult:
    """
    Crawl multiple webpages concurrently with streaming results and extract content.
    
    Args:
        urls: List of URLs to crawl
        instruction: Instructions for what content to extract from the pages
        max_concurrency: Maximum number of concurrent crawling tasks (default: 5)
        cache_mode: Cache mode (BYPASS, READ_ONLY, WRITE_ONLY, READ_WRITE)
    
    Returns:
        Extraction results for each URL as they complete
    """
    try:
        logger.info(f"Streaming crawl of multiple pages: {urls}")
        # Convert cache_mode string to enum
        cache_enum = getattr(CacheMode, cache_mode)
        
        # Create LLMConfig for the extraction
        llm_config = get_llm_config()
        
        # Create extraction strategy
        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            extraction_type="raw",
            instruction=instruction,
            input_format="markdown",
            apply_chunking=True,
        )
        
        # Create crawler config with streaming enabled
        crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=cache_enum,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=True,
            stream=True  # Enable streaming mode
        )
        
        # Configure browser
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        
        # Configure dispatcher with memory adaptive settings
        from crawl4ai.dispatcher import MemoryAdaptiveDispatcher
        
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=70.0,
            max_session_permit=max_concurrency,
            poll_interval=1.0
        )
        
        # Initialize crawler
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            # Use arun_many with streaming
            result_generator = await crawler.arun_many(
                urls=urls,
                config=crawl_config,
                dispatcher=dispatcher
            )
            
            # Process streaming results
            scraped_results = []
            async for result in result_generator:
                if result.success:
                    formatted_content = format_content_with_citations(
                        clean_markdown(result.extracted_content), 
                        result.url
                    )
                    scraped_results.append(
                        ScrapingResult(
                            success=True,
                            content=formatted_content
                        )
                    )
                else:
                    logger.error(f"Streaming multi-page crawling failed for {result.url}: {result.error_message}")
                    scraped_results.append(
                        ScrapingResult(
                            success=False,
                            error=f"Crawling failed for {result.url}: {result.error_message}"
                        )
                    )
            
            return MultiCrawlResult(results=scraped_results)
    
    except Exception as e:
        logger.exception(f"Error during streaming multi-page crawling: {str(e)}")
        # Return a MultiCrawlResult with a single error result
        return MultiCrawlResult(
            results=[
                ScrapingResult(
                    success=False,
                    error=f"Error during streaming multi-page crawling: {str(e)}"
                )
            ]
        )

def print_server_info():
    """Print server information on startup"""
    print("\n" + "=" * 60)
    print(f"🚀 Crawl4AI MCP Server")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 Python version: {sys.version.split()[0]}")
    try:
        import crawl4ai
        print(f"📦 Crawl4AI version: {crawl4ai.__version__}")
    except (ImportError, AttributeError):
        print(f"📦 Crawl4AI version: Unknown")
    print(f"🔌 MCP Tools: crawl_page, crawl_with_schema, get_page_links, extract_table_as_json, crawl_many, crawl_many_streaming")
    print("=" * 60 + "\n")

# Run the MCP server
if __name__ == "__main__":
    print_server_info()
    mcp.run()
