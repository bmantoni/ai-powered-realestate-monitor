# Overview
Build a process that can run daily to research available ski condos to buy in Snowshow, WV that meet my critera (provided below).
It should send me a daily (configurable) notification via email with a well-formatted list of new properties that meet my criteria, and any important updates to properties highlighted earlier. For example, a change in price or availability.
It should also keep track of some overview metrics over time such as the volume of properties and the average price of those that meet my criteria.
Format the notification into a pleasing HTML based message with a table and pictures from the listings.

# Source Data
Use https://www.firsttracts.com/real-estate/our-listings to find listings, though this should be configurable to extend to different, and potentially, multiple listing sources. The daily report should include links that can be followed to the listing.

# Models
This should use Gemini (Free Tier) or Kimi for Coding models via API keys I've set as environment variables, but this should be configurable to different models.

# Operations
I'd prefer to run this as a github action on github. But if that doesn't work I have a home server that could run a container.

# My Criteria
* In the Snowshow village
* Properties: Allegheny Springs or Rimfire Lodge
* 1 Bedroom
* View: I want a view that is either facing the mountains on the opposte side of the ski area (across the parking lot), or directly facing the ski area.
* Price: $150k - $200k
