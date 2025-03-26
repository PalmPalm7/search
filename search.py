from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import quote_plus
from mcp.server.fastmcp import FastMCP
# Initialize FastMCP server
mcp = FastMCP("websearch")
# Constants - You'll need to provide your own API keys
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "your_serper_api_key")
SERPER_API_URL = "https://google.serper.dev/search"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
async def make_search_request(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Make a request to Serper API for Google search results."""
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": num_results
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                SERPER_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
async def fetch_webpage_content(url: str) -> str:
    """Fetch content from a webpage with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT
    }
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            return f"Error fetching page: {str(e)}"
def format_search_result(result: Dict[str, Any]) -> str:
    """Format a search result into a readable string."""
    title = result.get("title", "No title")
    link = result.get("link", "No link")
    snippet = result.get("snippet", "No description available")
    return f"""
Title: {title}
URL: {link}
Snippet: {snippet}
"""
@mcp.tool()
async def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web for the given query and return formatted results.
    Args:
        query: The search query
        num_results: Number of results to return (default: 5)
    """
    search_results = await make_search_request(query, num_results)
    if "error" in search_results:
        return f"Error performing search: {search_results['error']}"
    if "organic" not in search_results or not search_results["organic"]:
        return "No results found for your query."
    formatted_results = [
        format_search_result(result)
        for result in search_results["organic"][:num_results]
    ]
    return "\n---\n".join(formatted_results)
@mcp.tool()
async def fetch_and_parse_webpage(url: str, extraction_type: str = "full_text") -> str:
    """
    Fetch a webpage and extract content based on extraction_type.
    Args:
        url: The URL of the webpage to fetch and parse
        extraction_type: Type of content to extract - "full_text", "main_content",
                        "headings", or "links" (default: "full_text")
    """
    html_content = await fetch_webpage_content(url)
    if html_content.startswith("Error"):
        return html_content
    soup = BeautifulSoup(html_content, 'html.parser')
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    if extraction_type == "full_text":
        # Get all text
        text = soup.get_text(separator="\n", strip=True)
        return text[:10000] + "..." if len(text) > 10000 else text
    elif extraction_type == "main_content":
        # Try to find main content (simplified approach)
        main_elements = soup.find_all(['article', 'main', 'div'], class_=lambda c: c and ('content' in c.lower() or 'article' in c.lower()))
        if main_elements:
            main_content = "\n\n".join([elem.get_text(separator="\n", strip=True) for elem in main_elements])
            return main_content[:10000] + "..." if len(main_content) > 10000 else main_content
        else:
            return "Couldn't identify main content. Try using full_text extraction instead."
    elif extraction_type == "headings":
        # Extract all headings
        headings = []
        for tag in ['h1', 'h2', 'h3']:
            for heading in soup.find_all(tag):
                headings.append(f"{tag.upper()}: {heading.get_text(strip=True)}")
        return "\n".join(headings) if headings else "No headings found on the page."
    elif extraction_type == "links":
        # Extract all links
        links = []
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True) or "[No text]"
            href = link['href']
            links.append(f"{text}: {href}")
        return "\n".join(links[:100]) if links else "No links found on the page."
    else:
        return f"Invalid extraction_type: {extraction_type}. Valid options are 'full_text', 'main_content', 'headings', or 'links'."
@mcp.tool()
async def deep_research(topic: str, depth: int = 2) -> str:
    """
    Perform multi-stage research on a topic by searching and then exploring top results.
    Args:
        topic: The research topic
        depth: How many top search results to explore (default: 2)
    """
    # First perform a search
    search_results = await make_search_request(topic, depth + 2)
    if "error" in search_results:
        return f"Error performing search: {search_results['error']}"
    if "organic" not in search_results or not search_results["organic"]:
        return "No results found for your topic."
    # Structure for the research report
    research_report = [f"# Deep Research: {topic}\n"]
    research_report.append("## Search Results Overview\n")
    # Add search results summary
    for i, result in enumerate(search_results["organic"][:depth + 2]):
        research_report.append(f"{i+1}. **{result.get('title', 'No title')}**")
        research_report.append(f"   URL: {result.get('link', 'No link')}")
        research_report.append(f"   Summary: {result.get('snippet', 'No description')}\n")
    # Now explore the top results in depth
    research_report.append("## Detailed Content Analysis\n")
    for i, result in enumerate(search_results["organic"][:depth]):
        title = result.get('title', 'No title')
        url = result.get('link', 'No link')
        research_report.append(f"### Source {i+1}: {title}")
        research_report.append(f"URL: {url}\n")
        # Get the content
        html_content = await fetch_webpage_content(url)
        if html_content.startswith("Error"):
            research_report.append(f"Could not access this page: {html_content}\n")
            continue
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        # Extract headings for an outline
        research_report.append("#### Key Points:\n")
        headings = []
        for tag in ['h1', 'h2', 'h3']:
            for heading in soup.find_all(tag):
                heading_text = heading.get_text(strip=True)
                if heading_text and len(heading_text) > 3:  # Filter out too short headings
                    headings.append(f"- {heading_text}")
        if headings:
            research_report.extend(headings[:10])  # Limit to first 10 headings
            research_report.append("")  # Empty line
        else:
            research_report.append("- No clear headings found on this page.")
            research_report.append("")  # Empty line
        # Try to get main content (simplified approach)
        main_elements = soup.find_all(['article', 'main', 'div'], class_=lambda c: c and ('content' in c.lower() or 'article' in c.lower()))
        research_report.append("#### Summary of Content:\n")
        if main_elements:
            main_text = main_elements[0].get_text(separator=" ", strip=True)
            # Create a simple summary by taking the first few paragraphs
            paragraphs = main_text.split('\n')
            content_summary = " ".join(paragraphs[:3])[:500] + "..."
            research_report.append(content_summary)
        else:
            # Fall back to page text
            page_text = soup.get_text(separator=" ", strip=True)
            content_summary = page_text[:500] + "..."
            research_report.append(content_summary)
        research_report.append("\n---\n")
    # Conclusion
    research_report.append("## Research Summary")
    research_report.append(f"This research explored {depth} sources on the topic '{topic}'. To further explore this topic, consider reading the full content of the most relevant sources or refining your search terms.")
    return "\n".join(research_report)
    
if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
