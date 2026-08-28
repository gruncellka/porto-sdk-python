# Porto SDK

[![validation](https://github.com/gruncellka/porto-sdk-python/actions/workflows/validation.yml/badge.svg)](https://github.com/gruncellka/porto-sdk-python/actions/workflows/validation.yml)
[![codecov](https://codecov.io/gh/gruncellka/porto-sdk-python/branch/main/graph/badge.svg)](https://codecov.io/gh/gruncellka/porto-sdk-python)

Cross-provider postal SDK for Python.

Supported providers: Deutsche Post, Ukrposhta, La Poste, and Swiss Post.

## Install

```bash
pip install gruncellka-porto-sdk
```

`porto-data` ships as a runtime dependency (products, pricing, restrictions, formats). You do not install it separately.

## Quick start

`PortoClient` is the entry point. `client.provider(...)` returns a `ProviderClient` for one postal operator. `options()`, `resolve()`, `price()`, and `restrictions.check()` need no credentials. `mark()` does.

```python
from porto_sdk import PortoClient

client = PortoClient()
dp = client.provider("deutschepost")
```

## Discover options

List available products for a destination, weight, and optional envelope. Each `ProductOption` includes the services available with that product.

```python
options = dp.options(country_code="DE", weight=20, envelope_id="DL")
product = next(row for row in options if row.id == "standardbrief")
```

```text
ProductOption(
  id="standardbrief",
  amount=95,
  currency="EUR",
  services=[
    ServiceOption(id="einschreiben", kind="registered", name="Einschreiben", amount=265, currency="EUR"),
    ServiceOption(id="einschreiben_rueckschein", kind="registered_return_receipt", name="Einschreiben Rückschein", amount=485, currency="EUR"),
    ...
  ],
)
```

## Resolve

When one product matches the weight, `resolve` can omit `product_id`. Otherwise choose a product from discovery. Select services by `ServiceOption.kind`. If several options share the same kind, also pass the selected service ID.

```python
return_receipt = next(svc for svc in product.services if svc.kind == "registered_return_receipt")
porto = dp.resolve(
    country_code="DE",
    weight=20,
    envelope_id="DL",
    product_id=product.id,
    services=[return_receipt.kind],
)
```

```text
Porto(
  amount=580,
  currency="EUR",
  components=[
    PriceComponent(kind="product", id="standardbrief", amount=95),
    PriceComponent(kind="service", id="einschreiben_rueckschein", amount=485),
  ],
)
# 95 + 485 = 580
```

When several `ServiceOption`s share a kind (for example `registered`), pass that option’s `id` as `service_ids` (`PORTO_SERVICE_AMBIGUOUS` otherwise):

```python
service = next(svc for svc in product.services if svc.id == "einschreiben")
registered_porto = dp.resolve(
    country_code="DE",
    weight=20,
    envelope_id="DL",
    product_id=product.id,
    services=[service.kind],
    service_ids=[service.id],
)
```

`price()` returns the same amount, currency, and components for the same selection. It is not required after `resolve()`.

## Restrictions

`resolve()` attaches country-level restrictions on `Porto.restrictions`. At country precision, regional restrictions produce `impact="warn"`. Use `restrictions.check()` with a region code for a more precise result:

```python
to_ukraine = dp.resolve(country_code="UA", weight=20)
```

```text
to_ukraine.restrictions → Restrictions(impact="warn", legal=(...), routing=())
```

```python
kherson = dp.restrictions.check("UA", "UA-65")
```

```text
Restrictions(
  impact="warn",
  legal=(
    LegalRestriction(
      impact="warn",
      country_code="UA",
      region_code="UA-65",
      partial=True,
      reason="Regional legal restrictions apply.",
      description="Applicable jurisdictional measures cover part of this region.",
      jurisdictions=(
        JurisdictionInstrument(jurisdiction="EU", reference="https://eur-lex.europa.eu/eli/reg/2022/1903/oj", effective_from="2022-10-06"),
      ),
    ),
  ),
  routing=(),
)
```

## Mark

`mark()` uses the resolved Porto and does not re-price it.

The **provider** is the operator you chose. A **wire** is the execution integration (for example Internetmarke). Adapters stay internal — omit `wire` when the default integration applies. Pass credentials per call on `ExecutionParameters`; per-call values override runtime defaults.

```python
import asyncio

from porto_sdk import ExecutionParameters, PortoMarkRequest

mark = asyncio.run(
    dp.mark(
        PortoMarkRequest(porto=porto),
        ExecutionParameters(credentials={"username": "***", "password": "***"}),
    )
)
```

```text
PortoMark(
  id="…",
  provider="deutschepost",
  wire="internetmarke",
  content="https://…",
  content_type="application/pdf",
  amount=580,
  currency="EUR",
)
```

## CLI

`identify` (envelope format and dimensions), `resolve`, `price`, `mark`, `track`, `config {check,init}`, `auth {login,status,logout}`. Human-readable by default; `--json` for machines. Credentials via environment or `porto auth login` (`~/.porto/config.json`).

## Porto ecosystem

- [porto-sdk-typescript](https://github.com/gruncellka/porto-sdk-typescript) software development kit
- [porto-data](https://github.com/gruncellka/porto-data) — runtime postal data
- [porto-features](https://github.com/gruncellka/porto-features) — shared behavioral contract

---

🔳 gruncellka
