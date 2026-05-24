import json
with open('data/properties.json') as f:
    data = json.load(f)

print("=== ALL PROPERTIES ===")
for pid, prop in data['properties'].items():
    if prop.get('is_available'):
        print(f"{prop['title']}: ${prop['price']:,.0f}, {prop['bedrooms']}BR, Property: {prop['property_name']}")

print("\n=== CHECKING WHY ONLY 1 MATCHED ===")
# Check the last snapshot
if data['snapshots']:
    last_snapshot = data['snapshots'][-1]
    print(f"Total listings in snapshot: {last_snapshot['total_listings']}")
    print(f"New listings: {last_snapshot['new_listings']}")
    
    # Check properties that should match
    for pid, prop in data['properties'].items():
        if prop.get('is_available') and 150000 <= prop['price'] <= 200000:
            has_bedroom = prop['bedrooms'] == 1
            has_property = prop['property_name'] in ['Allegheny Springs', 'Rimfire Lodge']
            desc = prop.get('description', '').lower()
            has_location = 'snowshoe' in desc or 'snowshoe' in (prop.get('location') or '').lower()
            
            print(f"\n{prop['title']}:")
            print(f"  Price: ${prop['price']:,.0f} ✓" if 150000 <= prop['price'] <= 200000 else f"  Price: ${prop['price']:,.0f} ✗")
            print(f"  Bedrooms: {prop['bedrooms']} {'✓' if has_bedroom else '✗'}")
            print(f"  Property: {prop['property_name']} {'✓' if has_property else '✗'}")
            print(f"  Location/Snowshoe in desc: {'✓' if has_location else '✗'}")
            print(f"  Description: {desc[:80]}...")
