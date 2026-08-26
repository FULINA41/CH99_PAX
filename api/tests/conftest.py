from decimal import Decimal

from duty.compute import term
from models import Effectivity, Layer


def layer(hts: str = "9903.00.00", *, kind: str = "additive", pct: str | None = None,
          amount: str | None = None, unit: str | None = None, scope: str = "by_code") -> Layer:
    return Layer(
        hts=hts, description="", scope=scope,
        term=term(kind=kind, text="", ad_valorem_pct=Decimal(pct) if pct else None,
                  specific_amount=Decimal(amount) if amount else None, specific_unit=unit),
        effectivity=Effectivity(status="in_force", standing="in_force"), evidence=[],
    )
