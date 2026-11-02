# Changelog

[Unreleased]

### Added

- `PortoStatus` is the normalized carrier status. `TrackingState` remains a deprecated alias for this minor.
- `statuses.json` set-parity (contract only; no runtime JSON).
- Native status maps stay under each provider. Unknown native codes leave `status` null. They are not `transit` and there is no `UNKNOWN` member.
- Optional `provider_raw` / `providerRaw` on `PortoMark` and `TrackingStatus`. Opaque, sanitized, not a compatibility contract.
- Deutsche Post live tracking only on the explicit `shipment` wire with a base URL. Internetmarke is not a tracking wire and does not invent `created`.
- `track_stamp` / `trackStamp` is a deprecated delegate to the unsupported stamp path.
- Carrier event times preserve explicit offsets or zoneless local semantics through `occurred_kind`; poll time never substitutes for a missing carrier time.
- `last_update` is the latest carrier event time, while `status_changed_at` marks the start of the current normalized status run.
- Tracking event identity prefers provider-native ids and sequences, and provider chronology owns event order.

## 0.1.0

Initial release
