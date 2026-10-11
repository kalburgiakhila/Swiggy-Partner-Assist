# QuickEats — Swiggy-like Food Delivery (Flask + SQLite)
QuickEats is a Swiggy-*like* (not affiliated) food delivery web app built with **Python Flask + SQLite**.

It demonstrates a realistic multi-role marketplace:
- **Customer**: browse, cart, checkout, pay (simulated), live tracking
- **Restaurant owner**: menu CRUD, accept orders, mark ready
- **Delivery partner (rider)**: go online, accept jobs, pickup, deliver, earnings
- **Admin**: monitor users/restaurants/orders + finance totals

## What this project includes
- Roles: Customer, Restaurant Owner, Delivery Partner, Admin
- Restaurant profile + menu CRUD (with images)
- **Cart isolation**:
  - Guests: browser-only cart (session)
  - Logged-in customers: DB cart (per user)
  - Guest cart merges into user cart on login
- Order lifecycle:
  - `placed → accepted → ready_for_pickup → picked_up → delivered`
- **Payment simulation**:
  - COD: payment collected on delivery (demo)
  - UPI/Card: redirects to a Pay page and sets payment to “paid” (simulated)
- **Commission + payouts (demo finance model)**:
  - Platform commission (15% of subtotal)
  - Restaurant payout (subtotal − commission)
  - Rider earning (base + per-km)
  - Rider/restaurant settlement becomes **earned** only after successful delivery
- **Partner Assist (handoff / reassignment)**:
  - If a rider picked up but can’t finish, they can trigger **Partner assist**
  - System selects a **nearby online rider** (cost-effective = nearest to handoff point)
  - Rider earning is **split**: first rider earns partial at handoff, second rider earns the rest after delivery
- Live tracking:
  - Customer order page shows restaurant/destination + route + rider live GPS marker
  - Live notifications: rider assigned, picked up, nearby delivery, delivered
- Routing:
  - Road-accurate route from free public **OSRM**
  - Fallback to A* grid route if OSRM is unreachable

## How it works (what happens end-to-end)

### Customer side
1. Browse restaurants and open a restaurant menu.
2. Add items (quantities update live).
3. Checkout:
   - Enter delivery address
   - Pin delivery location on map (or use GPS)
   - Choose payment method
4. If you chose **UPI/Card**:
   - Order is created but payment is **pending**
   - You are redirected to `/orders/<id>/pay`
   - Clicking **Pay now (Simulated)** marks payment as **paid**
5. Track the order at `/orders/<id>`:
   - Route polyline + live rider marker
   - Notifications for key events

### Restaurant owner side
1. Owner opens `/restaurant/dashboard` to see new orders.
2. Owner can **Accept** (UPI/Card orders only after payment is paid).
3. Owner marks **Ready**:
   - System tries to auto-assign the **nearest online rider** (who is not already busy).

### Rider side
1. Rider opens `/delivery/dashboard` and toggles **Online**.
2. When online, the browser sends GPS heartbeats to keep rider location fresh.
3. Rider accepts a job, then:
   - clicks **Picked up**
   - clicks **Delivered**
   - or clicks **Partner assist** to reassign to a nearby rider (handoff)
4. On delivery:
   - COD is marked as **paid**
   - Rider/restaurant settlements become **earned**
5. Rider can check `/delivery/earnings`.

### Admin side
1. Admin opens `/admin/` dashboard.
2. Admin can view `/admin/finance` for totals:
   - commission
   - rider earnings (earned)
   - restaurant payouts (earned)

## Quick start (Windows / PowerShell)

If you are setting this up on a fresh Windows machine, the fastest path is to double-click `setup-client.bat` or run:
```powershell
.\setup-client.bat
```
That script will install Python 3.11 if needed, create `.venv`, install `requirements.txt`, generate a local `.env`, and start the app.

If you prefer to do the steps manually:
```powershell
cd d:\swiggy2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`.

On first run, the app auto-creates `instance/app.db` and seeds demo data.

## Demo logins
- Admin: `admin@demo.com` / `Admin@1234`
- Customer: `customer@demo.com` / `Customer@1234`
- Customer (alt): `customer2@demo.com` / `Customer@1234`
- Restaurant owner: `owner@demo.com` / `Owner@1234`
- Restaurant owner (alt): `owner2@demo.com` / `Owner@1234`
- Delivery partner: `rider@demo.com` / `Rider@1234`
- Delivery partner (alt): `rider2@demo.com` / `Rider@1234`

## Notes
- Live location in Chrome works on `http://localhost` / `http://127.0.0.1` (or HTTPS). Allow Location permission.
- For access over **LAN IP** (e.g. `http://192.168.x.x:5000`), Chrome may require **HTTPS** for geolocation. You can run HTTPS by setting:
  - `SSL_CERT_FILE` and `SSL_KEY_FILE` env vars (paths to cert/key), then `python run.py`
  - Or use a local reverse proxy (Caddy/Nginx) with HTTPS
- OSRM is a free public service; if it’s unreachable, route will fall back to A*.
- Rider auto-assignment needs the rider to be **Online** with recent GPS (keep the dashboard open).
- Anti-scam geo checks:
  - Pickup requires rider to be near the restaurant
  - Delivery requires rider to be near the destination
  - Disable for testing/demo: set `ANTI_SCAM_GEO_CHECKS=0`

## Manual test checklist (recommended)
Use **two Chrome windows** (or normal + incognito) so you can log in as multiple roles.

### 0) Reset demo data (optional)
```powershell
cd d:\swiggy2
.\.venv\Scripts\Activate.ps1
python -c "from app import create_app; app=create_app(); app.app_context().push(); from app.seed import seed_demo_data; seed_demo_data(); print('seeded')"
```

### 1) Customer: place an order
1. Login as Customer: `customer@demo.com` / `Customer@1234`
2. Open `/` and choose a restaurant
3. Add items → open `/cart` → checkout `/checkout`
4. Choose **UPI/Card** to test pay flow:
   - You should be redirected to `/orders/<id>/pay`
   - Click **Pay now (Simulated)** and return to order page

### 2) Owner: accept + ready
1. Login as Owner: `owner@demo.com` / `Owner@1234`
2. Open `/restaurant/dashboard`
3. Click **Accept**, then **Ready**

### 3) Rider: deliver with live tracking
1. Login as Rider: `rider@demo.com` / `Rider@1234`
2. Open `/delivery/dashboard` and toggle **Online** (allow location)
3. Accept the order → open the job page
4. Click **Start sharing live location**
5. Click **Picked up**, then **Delivered**
6. Check `/delivery/earnings`

### 4) Admin: finance
1. Login as Admin: `admin@demo.com` / `Admin@1234`
2. Open `/admin/finance`

## Finance screens
- Rider earnings: `/delivery/earnings`
- Admin finance: `/admin/finance`

## Run tests
```powershell
cd d:\swiggy2
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Important code locations
- App bootstrap: `run.py`, `app/__init__.py`
- Models (orders, finance, rider state, cart): `app/models.py`
- SQLite additive migration helper: `app/schema.py`
- Dispatch (nearest rider): `app/services/dispatch.py`
- Routing (OSRM + A* fallback): `app/services/routing.py`
- WebSocket tracking + notifications: `app/web/sockets.py`
