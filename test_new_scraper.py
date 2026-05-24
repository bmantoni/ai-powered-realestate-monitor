"""Test the new HTML parser scraper."""
import asyncio
import os

os.environ.setdefault("EMAIL_RECIPIENT", "test@example.com")

import httpx
from src.firsttracts_scraper import parse_listings_html

async def test_scraper():
    """Test the new scraper on real data."""
    print("Fetching page 9 (contains Rimfire Lodge listings)...")
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            "https://www.firsttracts.com/mls/ajax/results.cfm?page=9",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.firsttracts.com/real-estate/our-listings"
            }
        )
        
        if "~~" in response.text:
            parts = response.text.split("~~")
            listings_html = parts[0]
            
            print(f"HTML length: {len(listings_html)} chars")
            
            # Parse with the new scraper
            listings = parse_listings_html(listings_html, "https://www.firsttracts.com/mls/ajax/results.cfm?page=9")
            
            print(f"\nFound {len(listings)} listings\n")
            
            # Show all listings
            for prop in listings:
                print(f"ID: {prop.id}")
                print(f"Title: {prop.title}")
                print(f"Price: ${prop.price:,.0f}")
                print(f"Bedrooms: {prop.bedrooms}")
                print(f"Bathrooms: {prop.bathrooms}")
                print(f"Property: {prop.property_name}")
                print(f"Location: {prop.location}")
                print(f"URL: {prop.listing_url}")
                print(f"Images: {len(prop.image_urls)} image(s)")
                print(f"Description: {prop.description[:100]}...")
                print("-" * 60)
        else:
            print("No ~~ separator found")

if __name__ == "__main__":
    asyncio.run(test_scraper())
