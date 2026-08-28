"""Internetmarke shopping-cart position DTOs."""

from porto_sdk.adapters.deutschepost.internetmarke.positions import PositionFactory, PositionMark
from tests.support.addresses import internetmarke_cart_address


def test_png_position_includes_discriminator() -> None:
    pos = PositionFactory().png(
        PositionMark(
            product_code=21,
            mark_type="label",
            recipient_address=internetmarke_cart_address("valid_DE"),
            sender_address=internetmarke_cart_address("origin_DE"),
        )
    )
    wire = pos.to_wire()
    assert wire["positionType"] == "AppShoppingCartPosition"
    assert wire["productCode"] == 21
    assert wire["voucherLayout"] == "ADDRESS_ZONE"
    assert "address" in wire


def test_png_position_franking_zone_omits_address() -> None:
    pos = PositionFactory().png(
        PositionMark(
            product_code=21,
            mark_type="stamp",
            recipient_address=internetmarke_cart_address("valid_DE"),
            sender_address=internetmarke_cart_address("origin_DE"),
        )
    )
    wire = pos.to_wire()
    assert wire["voucherLayout"] == "FRANKING_ZONE"
    assert "address" not in wire
