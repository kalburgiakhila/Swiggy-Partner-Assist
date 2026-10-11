# Market-ready feature outline (Swiggy-like)
This document is an implementation checklist to make the app feel realistic and closer to a market-ready food delivery product.

## Roles and responsibilities

### Customer (end user)
- Browse restaurants and menus; search + filters (cuisine, price, rating, delivery time)
- Cart is **per user** (guest cart is per-browser only); merge guest cart → account on login
- Checkout: address + pin on map; delivery instructions; contact number
- Payment simulation: COD / UPI / Card
- Order lifecycle + tracking:
  - placed → accepted → prepared/ready → rider assigned → picked up → nearby → delivered
  - live rider location on map + road-accurate route polyline
  - notifications: rider assigned, picked up, nearby, delivered
- Order history; invoices/receipts; refunds (simulated)
- Ratings/reviews for restaurant and rider (later)

### Restaurant owner
- Restaurant profile: location, hours/open flag, images
- Menu CRUD with availability toggles
- Order operations:
  - accept/reject, mark prepared/ready
  - see assigned rider + ETA to pickup
- Settlement:
  - commission charged by platform per order
  - payouts (restaurant payout = subtotal - commission - taxes/fees)
  - basic reports (orders, revenue) (later)

### Delivery partner (rider)
- **Go online/offline** (availability)
- Continuous background location updates while online (browser GPS) to support dispatch
- Dispatch / assignment:
  - auto-assigned by proximity + availability
  - rider sees “assigned” job with pickup + drop pins + route
- Job execution:
  - arrived at restaurant (optional) → picked up → delivered
- Earnings:
  - per-order earning (base + per-km) (simulated)
  - daily/weekly totals (later)

### Admin / Ops
- Monitor all orders; override status; cancel/refund (simulated)
- Manage users/restaurants/riders; activate/deactivate
- Commission configuration; rider fee configuration
- Basic fraud/abuse checks (later)

## Production behaviors (must-have for realism)
- **Per-user cart** and cart merge on login
- Rider availability + last-seen GPS + proximity based assignment
- Road-accurate route (OSRM) + fallback
- Live tracking events + push-like notifications (Socket.IO)
- Commission + rider earnings + payment simulation stored per order

