"""Deutsche Post Sendungsverfolgung — separate from Internetmarke stamp wire."""

from ....types import PortoStatus

MAP: dict[str, PortoStatus] = {
    "pre-transit": PortoStatus.CREATED,
    "transit": PortoStatus.TRANSIT,
    "out-for-delivery": PortoStatus.DELIVERY,
    "delivered": PortoStatus.DELIVERED,
    "return": PortoStatus.RETURNED,
    "failure": PortoStatus.UNDELIVERABLE,
}
