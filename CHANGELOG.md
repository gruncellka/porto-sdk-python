# Changelog

[Unreleased]

### Added

- `feature_kinds` on `Porto`, `PortoMark`, and `ServiceOption` lists the feature kinds of the purchased service.
- `PortoStatus` as the normalized carrier status.
- `statuses.json` set-parity (contract only; no runtime JSON). `PortoStatus` is generated from that catalog.
- Optional opaque, sanitized `provider_raw` on `PortoMark` and `TrackingStatus`.
- Deutsche Post live tracking only on the explicit `shipment` wire with a base URL. Internetmarke is not a tracking wire and does not invent `created`.
- `last_update` is the latest carrier event time, while `status_changed_at` marks the start of the current normalized status run.

### Changed

- Drop public `tracking_kind`. A tracking number plus `capabilities.track` is enough. The Deutsche Post wire id stays `shipment`.
- Unknown native status codes remain unmapped; they are not coerced to `transit`, and there is no `UNKNOWN` member.
- Carrier event times preserve explicit offsets or zoneless local semantics through `occurred_kind`; poll time never substitutes for carrier time.
- Tracking event identity prefers provider-native ids and sequences, and provider chronology owns event order.

### Deprecated

- `TrackingState`; use `PortoStatus`. The alias remains through 0.2.x.
- `track_stamp`; use `ProviderClient.track` on the `shipment` wire when a base URL is set.

## 0.1.0

Initial release
