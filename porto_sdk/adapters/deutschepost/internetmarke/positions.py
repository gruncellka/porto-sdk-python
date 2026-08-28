"""Internetmarke shopping-cart position DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, NotRequired, TypedDict

VoucherLayout = Literal["ADDRESS_ZONE", "FRANKING_ZONE"]
ADDRESS_ZONE: VoucherLayout = "ADDRESS_ZONE"
FRANKING_ZONE: VoucherLayout = "FRANKING_ZONE"

_PngPositionType = Literal["AppShoppingCartPosition"]
_PdfPositionType = Literal["AppShoppingCartPDFPosition"]


class CartAddressBlock(TypedDict):
    sender: dict[str, str]
    receiver: dict[str, str]


class PngPositionWire(TypedDict):
    productCode: int
    voucherLayout: VoucherLayout
    positionType: _PngPositionType
    address: NotRequired[CartAddressBlock]


class PdfSheetSlot(TypedDict):
    labelX: int
    labelY: int
    page: int


class PdfPositionWire(TypedDict):
    productCode: int
    voucherLayout: VoucherLayout
    position: PdfSheetSlot
    positionType: _PdfPositionType
    address: NotRequired[CartAddressBlock]


@dataclass(frozen=True)
class PositionMark:
    """One Internetmarke cart line. Not a PortoMark."""

    product_code: int
    mark_type: str = "stamp"
    recipient_address: Mapping[str, str] | None = None
    sender_address: Mapping[str, str] | None = None


@dataclass(frozen=True)
class PdfPlacement:
    label_x: int = 1
    label_y: int = 1
    page: int = 1


@dataclass(frozen=True)
class PngPosition:
    product_code: int
    voucher_layout: VoucherLayout
    address: CartAddressBlock | None = None
    position_type: _PngPositionType = "AppShoppingCartPosition"

    def to_wire(self) -> PngPositionWire:
        body: PngPositionWire = {
            "productCode": self.product_code,
            "voucherLayout": self.voucher_layout,
            "positionType": self.position_type,
        }
        if self.address is not None:
            body["address"] = self.address
        return body


@dataclass(frozen=True)
class PdfPosition:
    product_code: int
    voucher_layout: VoucherLayout
    placement: PdfPlacement
    address: CartAddressBlock | None = None
    position_type: _PdfPositionType = "AppShoppingCartPDFPosition"

    def to_wire(self) -> PdfPositionWire:
        body: PdfPositionWire = {
            "productCode": self.product_code,
            "voucherLayout": self.voucher_layout,
            "position": {
                "labelX": self.placement.label_x,
                "labelY": self.placement.label_y,
                "page": self.placement.page,
            },
            "positionType": self.position_type,
        }
        if self.address is not None:
            body["address"] = self.address
        return body


def voucher_layout_for_mark_type(mark_type: str | None) -> VoucherLayout:
    if mark_type == "label":
        return ADDRESS_ZONE
    return FRANKING_ZONE


def _cart_address(
    recipient_address: Mapping[str, str] | None,
    sender_address: Mapping[str, str] | None,
    voucher_layout: VoucherLayout,
) -> CartAddressBlock | None:
    if voucher_layout != ADDRESS_ZONE or not recipient_address or not sender_address:
        return None
    return {
        "sender": {key: value or "" for key, value in sender_address.items()},
        "receiver": {key: value or "" for key, value in recipient_address.items()},
    }


class PositionFactory:
    """Builds Internetmarke shopping-cart position DTOs."""

    def png(self, mark: PositionMark) -> PngPosition:
        layout = voucher_layout_for_mark_type(mark.mark_type)
        return PngPosition(
            product_code=mark.product_code,
            voucher_layout=layout,
            address=_cart_address(mark.recipient_address, mark.sender_address, layout),
        )

    def pdf(self, mark: PositionMark, placement: PdfPlacement | None = None) -> PdfPosition:
        layout = voucher_layout_for_mark_type(mark.mark_type)
        return PdfPosition(
            product_code=mark.product_code,
            voucher_layout=layout,
            placement=placement or PdfPlacement(),
            address=_cart_address(mark.recipient_address, mark.sender_address, layout),
        )
