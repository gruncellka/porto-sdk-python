# Changelog

[Unreleased]

## 0.2.0 - 2026-11-04

### Added

- `feature_kinds` on `Porto`, `PortoMark`, and `ServiceOption` lists the kinds of the purchased service.
- `PortoStatus` is the normalized carrier status, generated from `statuses.json`.
- `provider_raw` on `PortoMark` and `TrackingStatus` is a sanitized opaque payload.
- Deutsche Post tracks on the `shipment` wire when a base URL is set. Internetmarke does not poll.
- `last_update` is the latest carrier event time, and `status_changed_at` starts the current status.

### Changed

- Require porto-features 0.6.0.
- `tracking_kind` is gone. A tracking number and `capabilities.track` are enough, and the wire id stays `shipment`.
- Unknown native codes stay unmapped: no `UNKNOWN`, and no coercion to `transit`.
- `occurred_kind` keeps an explicit offset or a zoneless local time. Poll time is not carrier time.
- Event identity prefers provider ids and sequences, and provider chronology owns the order.

### Deprecated

- `TrackingState` remains through 0.2.x. Use `PortoStatus`.
- `track_stamp` remains. Use `ProviderClient.track` on the `shipment` wire.

## 0.1.0 - 2026-08-28

Initial release
