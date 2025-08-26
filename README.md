# eBay to Amazon Inventory Searcher
This project was aimed at automating the sourcing process for finding products to sell on Amazon. Particularly, I was interested in a strategy of 'Online Arbitrage' where I would find things on eBay, ship them to my house, and resell them on amazon FBA. I was particularly specialized in reselling camera equipment so I focused in that niche. 

This is really rough code, but it was very helpful for reducing the monotonous time spent sourcing. 

My workflow would be as follows. Every few hours I would run this script to search for new inventory opportunities which would get saved as a excel file and also emailed to me for convenience. 

I had a postgreSQL database, that I was manually updating as I found profitable flips, and this script automated the process of searching for those products on eBay and the individual listings I can resell. The idea was to resell the same type of camera over and over and just keep buying that camera. But, searching the camera model, scrolling through listings, finding profitable listings, etc, was a very repetitive process. 