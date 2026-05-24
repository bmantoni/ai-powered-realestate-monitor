import json
with open('data/properties.json') as f:
    data = json.load(f)

print("=== CHECKING NEW DATA ===")
for pid, prop in data['properties'].items():
    if prop.get('is_available') and 150000 <= prop['price'] <= 200000 and prop['bedrooms'] == 1:
        has_property = prop['property_name'] in ['Allegheny Springs', 'Rimfire Lodge']
        location_text = f"{prop.get('location') or ''} {prop.get('description') or ''}".lower()
        has_location = 'snowshoe' in location_text
        
        print(f"\n{prop['title']}:")
        print(f"  Property: {prop['property_name']} {'✓' if has_property else '✗'}")
        print(f"  Location: {prop.get('location')} {'✓' if has_location else '✗'}")
        print(f"  Description: {prop.get('description', '')[:60]}...")
