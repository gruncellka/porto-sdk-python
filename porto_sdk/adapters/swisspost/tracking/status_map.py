"""Swiss Post — placeholder map for future live wire."""

from ....types import PortoStatus

MAP: dict[str, PortoStatus] = {
    "NOT_YET_SENT": PortoStatus.CREATED,
    "ON_THE_WAY": PortoStatus.TRANSIT,
    "OUT_FOR_DELIVERY": PortoStatus.DELIVERY,
    "DELIVERED": PortoStatus.DELIVERED,
    "RETURNED": PortoStatus.RETURNED,
    "NOT_DELIVERED": PortoStatus.UNDELIVERABLE,
}
