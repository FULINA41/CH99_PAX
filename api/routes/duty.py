from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query

from duty.explain import NotClassified, explain
from models import DutyStack

router = APIRouter(tags=["duty"])


@router.get("/duty/{hts}", response_model=DutyStack)
def read_duty(
    hts: str,
    country: str | None = Query(
        default=None, min_length=2, max_length=2,
        description="ISO 3166-1 alpha-2 country of origin. Without it the provisions that "
                    "key on origin cannot be judged, and the answer says so.",
    ),
    on: date | None = Query(
        default=None,
        description="Judge each provision's standing against this date rather than today. "
                    "9903.91.14 begins on 2026-11-10 and is not an answer before then.",
    ),
    value: Decimal | None = Query(
        default=None, ge=0, description="Declared customs value in USD, for the ad valorem duty."
    ),
    quantity: Decimal | None = Query(
        default=None, ge=0,
        description="Shipment quantity in the code's own unit, for specific duties. Without "
                    "it a specific duty is reported as uncomputable rather than as zero.",
    ),
) -> DutyStack:
    """What Chapter 99 does to one good from one country, and why each part of that is claimed.

    Everything the web app shows comes from here, so a number on a page can always be checked
    against the object that produced it.

    Raises:
        HTTPException: 404 when the code is not in the base schedule.
    """
    try:
        return explain(hts, country_code=country.upper() if country else None, on_date=on,
                       declared_value_usd=value, quantity=quantity)
    except NotClassified as missing:
        raise HTTPException(
            status_code=404,
            detail=f"{missing.args[0]} is not a code in chapters 1-97 of this revision",
        ) from missing
