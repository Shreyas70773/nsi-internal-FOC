import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

WEIGHT_REQUIRED_FIELDS = 0.30
WEIGHT_LINE_ITEM_COMPLETENESS = 0.20
WEIGHT_LINE_MATH = 0.20
WEIGHT_SUBTOTAL = 0.15
WEIGHT_GRAND_TOTAL = 0.15


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _check_required_fields(variables: dict) -> tuple[float, str | None]:
    required = ["buyer_name", "seller_name", "line_items"]
    missing = [f for f in required if not variables.get(f)]
    if not missing:
        return WEIGHT_REQUIRED_FIELDS, None
    ratio = 1 - len(missing) / len(required)
    return (
        round(WEIGHT_REQUIRED_FIELDS * ratio, 4),
        f"Missing required fields: {', '.join(missing)}",
    )


def _check_line_item_completeness(variables: dict) -> tuple[float, str | None]:
    items = variables.get("line_items")
    if not items:
        return 0.0, "No line items found"
    issues: list[str] = []
    for i, item in enumerate(items, 1):
        missing = []
        if not item.get("qty") and item.get("qty") != 0:
            missing.append("qty")
        if not item.get("unit_price") and item.get("unit_price") != 0:
            missing.append("unit_price")
        if missing:
            issues.append(f"Line item {i}: missing {', '.join(missing)}")
    if not issues:
        return WEIGHT_LINE_ITEM_COMPLETENESS, None
    ratio = 1 - len(issues) / len(items)
    return (
        round(WEIGHT_LINE_ITEM_COMPLETENESS * max(ratio, 0), 4),
        "; ".join(issues),
    )


def _check_line_math(variables: dict) -> tuple[float, str | None]:
    items = variables.get("line_items")
    if not items:
        return 0.0, "No line items to validate math"
    issues: list[str] = []
    for i, item in enumerate(items, 1):
        qty = _to_decimal(item.get("qty"))
        unit_price = _to_decimal(item.get("unit_price"))
        total = _to_decimal(item.get("total"))
        if qty is None or unit_price is None or total is None:
            continue
        expected = qty * unit_price
        if expected != total:
            issues.append(
                f"Line item {i}: calculated total ({expected}) "
                f"doesn't match stated total ({total})"
            )
    if not issues:
        return WEIGHT_LINE_MATH, None
    ratio = 1 - len(issues) / len(items)
    return (
        round(WEIGHT_LINE_MATH * max(ratio, 0), 4),
        "; ".join(issues),
    )


def _check_subtotal(variables: dict) -> tuple[float, str | None]:
    items = variables.get("line_items")
    stated_subtotal = _to_decimal(variables.get("subtotal"))
    if stated_subtotal is None or not items:
        if not items:
            return 0.0, "No line items to verify subtotal"
        return WEIGHT_SUBTOTAL * 0.5, "Subtotal not provided"

    computed = Decimal("0")
    for item in items:
        t = _to_decimal(item.get("total"))
        if t is not None:
            computed += t

    if computed == stated_subtotal:
        return WEIGHT_SUBTOTAL, None
    return (
        0.0,
        f"Subtotal mismatch: sum of line totals ({computed}) "
        f"!= stated subtotal ({stated_subtotal})",
    )


def _check_grand_total(variables: dict) -> tuple[float, str | None]:
    subtotal = _to_decimal(variables.get("subtotal"))
    tax = _to_decimal(variables.get("tax")) or Decimal("0")
    grand_total = _to_decimal(variables.get("grand_total"))

    if grand_total is None:
        return WEIGHT_GRAND_TOTAL * 0.5, "Grand total not provided"
    if subtotal is None:
        return WEIGHT_GRAND_TOTAL * 0.5, "Cannot verify grand total without subtotal"

    expected = subtotal + tax
    if expected == grand_total:
        return WEIGHT_GRAND_TOTAL, None
    return (
        0.0,
        f"Grand total mismatch: subtotal ({subtotal}) + tax ({tax}) = {expected}, "
        f"but stated grand total is {grand_total}",
    )


async def evaluate_document(
    doc_type: str, variables: dict
) -> tuple[float, list[str]]:
    checks = [
        _check_required_fields,
        _check_line_item_completeness,
        _check_line_math,
        _check_subtotal,
        _check_grand_total,
    ]

    score = 0.0
    issues: list[str] = []

    for check_fn in checks:
        points, issue = check_fn(variables)
        score += points
        if issue:
            issues.append(issue)

    score = round(min(score, 1.0), 2)
    logger.info(
        "Self-eval for %s: score=%.2f, issues=%d", doc_type, score, len(issues)
    )
    return score, issues
