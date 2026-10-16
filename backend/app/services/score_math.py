"""Round composite points once, using the published decimal component values."""
from decimal import Decimal, ROUND_HALF_UP, localcontext


def composite_points(components, normalized_weights):
    available = [(value, normalized_weights.get(key, 0)) for key, value in components.items()
                 if value is not None and normalized_weights.get(key, 0) > 0]
    if not available:
        return None
    with localcontext() as context:
        context.prec = 800
        weighted = sum((Decimal(str(value)) * Decimal(str(weight)) for value, weight in available), Decimal(0))
        return float((weighted / Decimal(100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
