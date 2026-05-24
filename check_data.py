import json
with open('data/properties.json') as f:
    data = json.load(f)
for pid, prop in data['properties'].items():
    if 'rimfire' in prop['title'].lower() and 150000 <= prop['price'] <= 200000:
        print(f"ID: {pid}")
        print(f"Title: {prop['title']}")
        print(f"Price: ${prop['price']:,.0f}")
        print(f"Bedrooms: {prop['bedrooms']}")
        print(f"Property: {prop['property_name']}")
        print(f"Location: {prop['location']}")
        print()
