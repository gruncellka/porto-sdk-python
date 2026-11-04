"""La Poste Suivi — placeholder map for future live wire."""

from ....types import PortoStatus

MAP: dict[str, PortoStatus] = {
    "PC1": PortoStatus.CREATED,
    "PC2": PortoStatus.TRANSIT,
    "PC3": PortoStatus.DELIVERY,
    "LIV": PortoStatus.DELIVERED,
    "REN": PortoStatus.RETURNED,
    "NDR": PortoStatus.UNDELIVERABLE,
}
