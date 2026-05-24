import json
with open('data/properties.json') as f:
    data = json.load(f)

print("=== MATCHING LISTINGS ===")
for pid, prop in data['properties'].items():
    if prop.get('is_available') and 150000 <= prop['price'] <= 200000 and prop['bedrooms'] == 1:
        if prop['property_name'] in ['Allegheny Springs', 'Rimfire Lodge']:
            print(f"\n{prop['title']}:")
            print(f"  Price: ${prop['price']:,.0f}")
            print(f"  Bedrooms: {prop['bedrooms']}")
            print(f"  Property: {prop['property_name']}")
            print(f"  Location: {prop.get('location')}")
            print(f"  URL: {prop['listing_url']}")
            print(f"  Description: {prop.get('description', '')[:80]}...")
            print(f"  Images: {len(prop.get('image_urls', []))} image(s)")
