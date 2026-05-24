"""Quick script to check all listing prices without AI."""
import asyncio
import os
import re

os.environ.setdefault("EMAIL_RECIPIENT", "test@example.com")

import httpx
from bs4 import BeautifulSoup

async def check_all_pages():
    """Fetch all pages and extract prices without AI."""
    base_url = "https://www.firsttracts.com/mls/ajax/results.cfm"
    
    all_listings = []
    
    for page in range(1, 15):
        print(f"Fetching page {page}...")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(base_url, params={"page": page}, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.firsttracts.com/real-estate/our-listings"
            })
            
            if "~~" in response.text:
                parts = response.text.split("~~")
                listings_html = parts[0]
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(listings_html, "html.parser")
                
                # Find all property panels
                for panel in soup.find_all("div", class_="panel"):
                    mls_number = panel.get("data-mlsnumber", "")
                    
                    # Extract title
                    title_link = panel.find("h3", class_="panel-title")
                    if title_link:
                        title_a = title_link.find("a")
                        title = title_a.get_text(strip=True) if title_a else "Unknown"
                        
                        # Extract price
                        price_span = title_link.find("span", class_="pull-right")
                        if price_span:
                            price_text = price_span.get_text(strip=True)
                            # Extract number from price text
                            price_match = re.search(r'\$([\d,]+)', price_text)
                            price = int(price_match.group(1).replace(',', '')) if price_match else 0
                        else:
                            price = 0
                        
                        # Extract bedrooms/bathrooms from panel body
                        body = panel.find("div", class_="panel-body")
                        bedrooms = None
                        if body:
                            bed_match = re.search(r'(\d+)\s* bedrooms', body.get_text(), re.IGNORECASE)
                            if bed_match:
                                bedrooms = int(bed_match.group(1))
                        
                        all_listings.append({
                            "title": title,
                            "price": price,
                            "bedrooms": bedrooms,
                            "mls": mls_number,
                        })
    
    # Sort by price
    all_listings.sort(key=lambda x: x["price"])
    
    print(f"\n{'='*60}")
    print(f"Total listings found: {len(all_listings)}")
    print(f"{'='*60}\n")
    
    print("CHEAPEST LISTINGS:")
    for i, listing in enumerate(all_listings[:20]):
        match = "✓" if 150000 <= listing["price"] <= 200000 else " "
        print(f"{match} ${listing['price']:>8,} - {listing['bedrooms']}BR - {listing['title']}")
    
    # Count matches
    matches = [l for l in all_listings if 150000 <= l["price"] <= 200000]
    print(f"\n{'='*60}")
    print(f"Listings in $150k-$200k range: {len(matches)}")
    print(f"{'='*60}")
    
    if matches:
        print("\nMATCHING LISTINGS:")
        for listing in matches:
            print(f"  ${listing['price']:>8,} - {listing['bedrooms']}BR - {listing['title']} (MLS: {listing['mls']})")

if __name__ == "__main__":
    asyncio.run(check_all_pages())
