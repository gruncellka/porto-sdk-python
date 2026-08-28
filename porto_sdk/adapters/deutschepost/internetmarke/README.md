# Internetmarke Adapter

## Overview

Deutsche Post Internetmarke execution adapter: Portokasse auth, REST shopping-cart (`directCheckout`), and mark purchase.

## Structure

```
internetmarke/
├── __init__.py          # Public API exports
├── adapter.py           # Main adapter (facade) — PortoMark minting
├── checkout.py          # One shopping-cart checkout → CheckoutResult
├── client.py            # Dumb HTTP: create_cart / checkout_png / checkout_pdf
├── positions.py         # PositionFactory + provider position DTOs
├── error_mapper.py      # HTTP failure → PortoError
├── auth.py              # Authentication (REST API)
└── utils.py             # Address normalization, vendor error codes
```

## Design

- **SRP:** adapter, checkout, HTTP client, position DTOs, error mapping, and auth live in separate modules.
- **OCP:** Protocol-based clients allow alternate transports without changing the facade.
- **LSP:** Implements `ExecutionAdapter` so the registry can swap wires.
- **DIP:** Adapter depends on `ExecutionAdapter` and client abstractions.

## Module responsibilities

### `adapter.py`
Main facade: validates requests, coordinates checkout, maps `CheckoutResult` → `PortoMark`.

### `auth.py`
Two-level authentication: app credentials (DHL API) + customer credentials (Portokasse). Session tokens and expiration.

### `checkout.py`
One provider operation: create cart → PNG/PDF request → `directCheckout` → `CheckoutResult`. No `PortoMark`, no `last_checkout_trace`.

### `client.py`
Dumb HTTP client: `create_cart`, `checkout_png`, `checkout_pdf`.

### `positions.py`
`PositionFactory.png(mark)` / `.pdf(mark, placement)` and typed cart position DTOs (`ADDRESS_ZONE` / `FRANKING_ZONE`).

### `error_mapper.py`
Provider HTTP failures → `PortoError`.

### `utils.py`
Address normalization, product code mapping, vendor error-code helpers, response parsing.

## Usage

```python
from porto_sdk.adapters.deutschepost.internetmarke import InternetmarkeAdapter

adapter = InternetmarkeAdapter(
    api_key="dhl-api-key",
    api_secret="dhl-api-secret",
    email="customer@example.com",
    password="customer-password",
)
```

## Testing

- Unit tests for utilities
- Integration / BDD for adapter errors and offline paths
- Paid canary/heavy suites for live mark purchase (require secrets)
