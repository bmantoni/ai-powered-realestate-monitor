"""Debug script to check specific listing HTML."""
import asyncio
import os

os.environ.setdefault("EMAIL_RECIPIENT", "test@example.com")

import httpx
from bs4 import BeautifulSoup

async def check_listing():
    """Fetch and inspect a specific listing page."""
    # Check one of the Rimfire Lodge listings
    url = "https://www.firsttracts.com/mls/property.cfm?mlsid=63&wsid=1&mlsnumber=251443"
    
    print(f"Fetching: {url}")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.firsttracts.com/real-estate/our-listings"
        })
        
        print(f"Status: {response.status_code}")
        print(f"Length: {len(response.text)}")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for property details
        print("\nLooking for property details...")
        
        # Find bedrooms
        bed_elements = soup.find_all(text=lambda t: t and 'bedroom' in t.lower())
        print(f"Found {len(bed_elements)} bedroom mentions:")
        for elem in bed_elements[:5]:
            print(f"  {elem.strip()}")
        
        # Find price
        price_elements = soup.find_all(text=lambda t: t and '$' in t)
        print(f"\nFound {len(price_elements)} price mentions:")
        for elem in price_elements[:5]:
            print(f"  {elem.strip()}")
        
        # Look for property name
        prop_elements = soup.find_all(text=lambda t: t and 'rimfire' in t.lower())
        print(f"\nFound {len(prop_elements)} Rimfire mentions:")
        for elem in prop_elements[:5]:
            print(f"  {elem.strip()}")

if __name__ == "__main__":
    asyncio.run(check_listing())
