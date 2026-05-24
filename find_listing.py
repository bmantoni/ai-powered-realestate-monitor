"""Debug script to find a specific listing in AJAX response."""
import asyncio
import os
import re

os.environ.setdefault("EMAIL_RECIPIENT", "test@example.com")

import httpx
from bs4 import BeautifulSoup

async def find_listing():
    """Find a specific listing in the AJAX response."""
    base_url = "https://www.firsttracts.com/mls/ajax/results.cfm"
    target_mls = "251443"  # 256 Rimfire Lodge $169,900
    
    for page in range(1, 15):
        print(f"Checking page {page}...")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(base_url, params={"page": page}, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.firsttracts.com/real-estate/our-listings"
            })
            
            if "~~" in response.text:
                parts = response.text.split("~~")
                listings_html = parts[0]
                
                if target_mls in listings_html:
                    print(f"\n✓ Found MLS {target_mls} on page {page}")
                    
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(listings_html, "html.parser")
                    
                    # Find the specific panel
                    panel = soup.find("div", {"data-mlsnumber": target_mls})
                    if panel:
                        print("\nPanel HTML:")
                        print(panel.prettify()[:2000])
                    
                    # Also check for bedroom info in the full HTML
                    bed_matches = re.findall(r'(\d+)\s*bedrooms?', listings_html, re.IGNORECASE)
                    print(f"\nBedroom counts found on page: {bed_matches}")
                    
                    return
    
    print("Listing not found")

if __name__ == "__main__":
    asyncio.run(find_listing())
