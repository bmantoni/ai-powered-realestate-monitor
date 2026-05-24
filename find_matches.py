"""Quick script to find all matching listings without AI."""
import asyncio
import os
import re

os.environ.setdefault("EMAIL_RECIPIENT", "test@example.com")

import httpx
from bs4 import BeautifulSoup

async def find_matches():
    """Find all listings matching criteria without AI."""
    base_url = "https://www.firsttracts.com/mls/ajax/results.cfm"
    
    matches = []
    
    for page in range(1, 15):
        print(f"Checking page {page}...", end=" ", flush=True)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(base_url, params={"page": page}, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.firsttracts.com/real-estate/our-listings"
            })
            
            if "~~" in response.text:
                parts = response.text.split("~~")
                listings_html = parts[0]
                
                soup = BeautifulSoup(listings_html, "html.parser")
                
                for panel in soup.find_all("div", class_="panel"):
                    mls_number = panel.get("data-mlsnumber", "")
                    
                    title_link = panel.find("h3", class_="panel-title")
                    if not title_link:
                        continue
                    
                    title_a = title_link.find("a")
                    title = title_a.get_text(strip=True) if title_a else "Unknown"
                    
                    price_span = title_link.find("span", class_="pull-right")
                    if not price_span:
                        continue
                    
                    price_text = price_span.get_text(strip=True)
                    price_match = re.search(r'\$([\d,]+)', price_text)
                    if not price_match:
                        continue
                    
                    price = int(price_match.group(1).replace(',', ''))
                    
                    # Check price range
                    if not (150000 <= price <= 200000):
                        continue
                    
                    # Extract bedrooms from panel
                    bedrooms = None
                    panel_text = panel.get_text()
                    bed_match = re.search(r'(\d+)\s*bedrooms?', panel_text, re.IGNORECASE)
                    if bed_match:
                        bedrooms = int(bed_match.group(1))
                    
                    # Check if it's Allegheny Springs or Rimfire Lodge
                    is_target_property = (
                        'allegheny' in title.lower() or 
                        'rimfire' in title.lower()
                    )
                    
                    matches.append({
                        "title": title,
                        "price": price,
                        "bedrooms": bedrooms,
                        "mls": mls_number,
                        "page": page,
                        "is_target": is_target_property,
                    })
        
        print(f"{len([m for m in matches if m['page'] == page])} matches")
    
    # Sort by price
    matches.sort(key=lambda x: x["price"])
    
    print(f"\n{'='*70}")
    print(f"TOTAL MATCHES: {len(matches)} listings in $150k-$200k range")
    print(f"{'='*70}\n")
    
    target_matches = [m for m in matches if m["is_target"]]
    other_matches = [m for m in matches if not m["is_target"]]
    
    if target_matches:
        print(f"TARGET PROPERTIES (Allegheny Springs / Rimfire Lodge): {len(target_matches)}")
        print("-" * 70)
        for m in target_matches:
            bed_info = f"{m['bedrooms']}BR" if m['bedrooms'] else "?BR"
            print(f"  ${m['price']:>8,} - {bed_info} - {m['title']} (MLS: {m['mls']}, Page {m['page']})")
    
    if other_matches:
        print(f"\nOTHER PROPERTIES IN PRICE RANGE: {len(other_matches)}")
        print("-" * 70)
        for m in other_matches:
            bed_info = f"{m['bedrooms']}BR" if m['bedrooms'] else "?BR"
            print(f"  ${m['price']:>8,} - {bed_info} - {m['title']} (MLS: {m['mls']}, Page {m['page']})")

if __name__ == "__main__":
    asyncio.run(find_matches())
