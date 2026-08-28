"""BDD steps for core/mark_requires.feature and paid adapter marks.feature."""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from porto_sdk.execution import PortoMarkRequest, build_porto_mark
from porto_sdk.requires import ADDRESS, RECIPIENT, SENDER
from porto_sdk.types import Address
from tests.bdd.steps.async_util import run_async
from tests.bdd.steps.helpers import public_resolve
from tests.support.addresses import licko_recipient, licko_sender
from tests.support.bound_provider import bound_provider
from tests.support.paid_many_artifacts import persist_paid_many_artifacts

DE_SENDER = licko_sender()
DE_RECIPIENT = licko_recipient("DE")
DE_INVALID = Address(
    name="x",
    street="x",
    house_number="1",
    postal_code="1",
    locality="x",
    country_code="DE",
)


class _CaptureAdapter:
    def __init__(self) -> None:
        self.requests: list = []

    @property
    def provider_id(self) -> str:
        return "deutschepost"

    @property
    def wire_id(self) -> str:
        return "internetmarke"

    async def mark(self, request, resolved_product=None, execution=None):
        self.requests.append(request)
        return build_porto_mark(
            provider="deutschepost",
            wire="internetmarke",
            content="https://example.test/mark.png",
            content_type="image/png",
            amount=request.value,
        )


def _capture_error(error: object) -> dict[str, str]:
    code = getattr(error, "code", None)
    if hasattr(code, "value"):
        code = code.value
    return {
        "code": str(code or ""),
        "message": getattr(error, "message", str(error)),
    }


def _install_capture(client) -> None:
    bound_provider(client)._execution.adapter = _CaptureAdapter()


_COVERAGE_CANDIDATES: dict[str, list[dict]] = {
    "domestic base": [
        {"country_code": "DE", "weight": 20},
        {"country_code": "DE", "weight": 50},
        {"country_code": "DE", "weight": 100},
    ],
    "other-zone + service": [
        {
            "country_code": "FR",
            "weight": 20,
            "service_ids": ["einschreiben"],
            "services": ["registered"],
        },
        {
            "country_code": "US",
            "weight": 20,
            "service_ids": ["einschreiben"],
            "services": ["registered"],
        },
        {
            "country_code": "UA",
            "weight": 20,
            "service_ids": ["einschreiben"],
            "services": ["registered"],
        },
        {
            "country_code": "FR",
            "weight": 50,
            "service_ids": ["einschreiben"],
            "services": ["registered"],
        },
        {
            "country_code": "FR",
            "weight": 100,
            "service_ids": ["einschreiben"],
            "services": ["registered"],
        },
    ],
    "feature-bearing": [
        {
            "country_code": "DE",
            "weight": 20,
            "service_ids": ["einschreiben_rueckschein"],
            "services": ["registered_return_receipt"],
        },
        {
            "country_code": "DE",
            "weight": 50,
            "service_ids": ["einschreiben_rueckschein"],
            "services": ["registered_return_receipt"],
        },
        {
            "country_code": "DE",
            "weight": 100,
            "service_ids": ["einschreiben_rueckschein"],
            "services": ["registered_return_receipt"],
        },
        {
            "country_code": "DE",
            "weight": 20,
            "service_ids": ["einschreiben_einwurf"],
            "services": ["registered"],
        },
        {
            "country_code": "DE",
            "weight": 20,
            "service_ids": ["einschreiben"],
            "services": ["registered"],
        },
    ],
}


def _resolve(client, *, service_ids: list[str] | None = None, weight: int = 20):
    return bound_provider(client).resolve(
        country_code="DE",
        weight=weight,
        services=["registered"] if service_ids else None,
        service_ids=service_ids,
    )


def _stamp_many_ok(porto) -> bool:
    if porto.mark_type not in (None, "stamp"):
        return False
    return not ADDRESS.intersection(porto.requires)


def _matches_coverage(porto, coverage: str) -> bool:
    if not _stamp_many_ok(porto):
        return False
    if coverage == "domestic base":
        return porto.zone.id == "domestic" and not porto.service_ids
    if coverage == "other-zone + service":
        return porto.zone.id != "domestic" and bool(porto.service_ids)
    if coverage == "feature-bearing":
        if porto.features:
            return True
        selected = set(porto.service_ids)
        return any(svc.id in selected and svc.features for svc in porto.available_services)
    return False


def _reset_roles(context) -> None:
    context.pop("sender", None)
    context.pop("recipient", None)
    context["mark_error"] = None
    context.pop("resolved_portos", None)
    context.pop("mark", None)
    context.pop("marks", None)


def _as_address(value: object | None) -> Address | None:
    if value is None:
        return None
    if isinstance(value, Address):
        return value
    if isinstance(value, dict):
        return Address(
            name=str(value.get("name") or "Test"),
            street=str(value.get("street") or "") or None,
            house_number=(
                str(value["house_number"]) if value.get("house_number") is not None else None
            ),
            postal_code=str(value.get("postal_code") or ""),
            locality=str(value.get("locality") or ""),
            country_code=str(value.get("country_code") or ""),
            region_code=value.get("region_code"),
        )
    return None


def _resolve_roles(context) -> tuple[Address | None, Address | None]:
    if "sender" in context or "recipient" in context:
        return _as_address(context.get("sender")), _as_address(context.get("recipient"))
    return None, None


@given("a resolved stamp Porto")
def given_resolved_stamp_porto(context):
    client = context["client"]
    _reset_roles(context)
    _install_capture(client)
    context["resolved_porto"] = _resolve(client)


@given("the resolved Porto includes registered mail")
def given_resolved_porto_includes_registered_mail(context):
    client = context["client"]
    _reset_roles(context)
    _install_capture(client)
    context["resolved_porto"] = _resolve(client, service_ids=["einschreiben"])


@given("a resolved Porto that requires ADDRESS_SENDER and ADDRESS_RECIPIENT")
def given_resolved_porto_requires_sender_and_recipient(context):
    client = context["client"]
    _reset_roles(context)
    _install_capture(client)
    porto = _resolve(client)
    context["resolved_porto"] = porto.model_copy(
        update={"requires": frozenset({SENDER, RECIPIENT})}
    )


@given("recipient is valid")
def given_recipient_is_valid(context):
    context["recipient"] = DE_RECIPIENT


@given("sender is missing")
def given_sender_is_missing(context):
    context["sender"] = None


@given("sender is valid")
def given_sender_is_valid(context):
    context["sender"] = DE_SENDER


@given("recipient is missing")
def given_recipient_is_missing(context):
    context["recipient"] = None


@given("sender fails the jurisdiction form")
def given_sender_fails_jurisdiction_form(context):
    context["sender"] = DE_INVALID
    context["recipient"] = DE_RECIPIENT


@given("recipient fails the jurisdiction form")
def given_recipient_fails_jurisdiction_form(context):
    context["sender"] = DE_SENDER
    context["recipient"] = DE_INVALID


@given("sender and recipient are valid")
def given_sender_and_recipient_are_valid(context):
    context["sender"] = DE_SENDER
    context["recipient"] = DE_RECIPIENT


@given("two resolved Portos with different products")
def given_two_resolved_portos_with_different_products(context):
    client = context["client"]
    _reset_roles(context)
    small = _resolve(client)
    large = _resolve(client, weight=400)
    context["resolved_porto"] = small
    context["resolved_portos"] = [small, large]


@given("the resolved Porto requires ADDRESS_RECIPIENT")
def given_resolved_porto_requires_recipient(context):
    client = context["client"]
    _reset_roles(context)
    porto = _resolve(client)
    context["resolved_porto"] = porto.model_copy(update={"requires": frozenset({RECIPIENT})})


@given("two equivalent stamp Portos")
def given_two_equivalent_stamp_portos(context):
    client = context["client"]
    _reset_roles(context)
    porto = _resolve(client)
    context["resolved_porto"] = porto
    context["resolved_portos"] = [porto, porto]


@given("a third valid Porto that differs in product")
def given_third_porto_differs_in_product(context):
    large = _resolve(context["client"], weight=400)
    portos = list(context.get("resolved_portos") or [context["resolved_porto"]])
    context["resolved_portos"] = [*portos, large]


@given(parsers.parse('a resolved stamp Porto covering "{coverage}"'))
def given_resolved_stamp_porto_covering(coverage: str, context):
    client = context["client"]
    _reset_roles(context)
    key = coverage.strip()
    candidates = _COVERAGE_CANDIDATES.get(key)
    if not candidates:
        raise AssertionError(f"unknown coverage type {coverage!r}")
    porto = None
    for candidate in candidates:
        try:
            resolved = bound_provider(client).resolve(**candidate)
        except Exception:  # noqa: BLE001 — try next catalog-valid combo
            continue
        if _matches_coverage(resolved, key):
            porto = resolved
            break
    assert porto is not None, f"no catalog-valid stamp Porto for coverage {coverage!r}"
    context["resolved_porto"] = porto
    context["coverage"] = key


@given(parsers.parse('valid destination address for country "{country_code}"'))
def given_valid_destination_for_country(country_code: str, context):
    context["recipient"] = licko_recipient(country_code)
    context["destination_country"] = country_code.strip().upper()


@when("I create a mark without sender or recipient")
def when_create_mark_without_sender_or_recipient(context):
    client = context["client"]
    porto = context["resolved_porto"]

    async def _run() -> None:
        context["mark"] = await bound_provider(client).mark(PortoMarkRequest(porto=porto))
        context["mark_error"] = None

    run_async(_run())


@when("I create a mark")
def when_create_mark(context):
    client = context["client"]

    async def _run() -> None:
        porto = context.get("resolved_porto")
        if porto is None:
            porto = public_resolve(context)
            context["resolved_porto"] = porto
        sender, recipient = _resolve_roles(context)
        try:
            context["mark"] = await bound_provider(client).mark(
                PortoMarkRequest(
                    porto=porto,
                    sender=sender,
                    recipient=recipient,
                )
            )
            context["mark_error"] = None
        except Exception as exc:  # noqa: BLE001 — BDD capture
            context["mark_error"] = _capture_error(exc)
            context["mark"] = None

    run_async(_run())


@when("I create three equivalent marks together")
def when_create_three_equivalent_marks(context):
    client = context["client"]
    porto = context["resolved_porto"]
    sender, recipient = _resolve_roles(context)

    async def _run() -> None:
        context["marks"] = await bound_provider(client).mark(
            [PortoMarkRequest(porto=porto, sender=sender, recipient=recipient) for _ in range(3)]
        )
        context["mark_error"] = None

    run_async(_run())


@when("I attempt to create the marks together")
def when_attempt_create_marks_in_one_many_call(context):
    client = context["client"]
    portos = context.get("resolved_portos")
    if not portos:
        porto = context["resolved_porto"]
        portos = [porto, porto]
    sender, recipient = _resolve_roles(context)

    async def _run() -> None:
        try:
            context["marks"] = await bound_provider(client).mark(
                [
                    PortoMarkRequest(
                        porto=item,
                        sender=sender,
                        recipient=recipient,
                    )
                    for item in portos
                ]
            )
            context["mark_error"] = None
        except Exception as exc:  # noqa: BLE001 — BDD capture
            context["mark_error"] = _capture_error(exc)

    run_async(_run())


@then("mark creation should succeed")
def then_mark_creation_should_succeed(context):
    assert context.get("mark_error") is None
    assert context.get("mark") is not None or context.get("marks") is not None


@then("the mark should be created successfully")
def then_the_mark_should_be_created_successfully(context):
    assert context.get("mark_error") is None, context.get("mark_error")
    assert context.get("mark") is not None


@then("the mark should have an id")
def then_the_mark_should_have_an_id(context):
    mark = context.get("mark")
    assert mark is not None
    assert getattr(mark, "id", None)


@then("three marks should be returned")
def then_three_marks_should_be_returned(context):
    assert context.get("mark_error") is None, context.get("mark_error")
    marks = context.get("marks")
    assert marks is not None
    assert len(marks) == 3


@then("every returned mark should have an id")
def then_every_returned_mark_should_have_an_id(context):
    marks = context.get("marks")
    assert marks is not None
    for mark in marks:
        assert getattr(mark, "id", None)


@then("the returned mark ids should be distinct")
def then_returned_mark_ids_should_be_distinct(context):
    marks = context.get("marks")
    assert marks is not None
    ids = [mark.id for mark in marks]
    assert len(set(ids)) == len(ids)


@then("the returned marks should share one external id")
def then_returned_marks_should_share_one_external_id(context):
    marks = context.get("marks")
    assert marks is not None
    externals = [getattr(mark, "external_id", None) for mark in marks]
    assert all(externals), externals
    assert len(set(externals)) == 1
    adapter = bound_provider(context["client"])._execution.adapter
    slug = str(context.get("coverage") or "many").replace(" ", "-").replace("+", "plus")
    run_async(
        persist_paid_many_artifacts(
            slug=slug,
            marks=list(marks),
            trace=getattr(adapter, "last_many_trace", None),
        )
    )
