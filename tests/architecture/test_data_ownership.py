"""Services must not construct PortoDataLoader themselves."""

from pathlib import Path

_SERVICES = Path(__file__).resolve().parents[2] / "porto_sdk" / "services"
_FILES = ("validation.py", "product_options.py")


def test_listed_services_do_not_use_porto_data_loader() -> None:
    for name in _FILES:
        path = _SERVICES / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert "PortoDataLoader" not in text
