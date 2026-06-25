from __future__ import annotations

import math
from typing import Any

from .models import PriceResult


def round_market_price(value: float) -> float:
    if value <= 0:
        return 0.0
    if value < 20:
        return round(value + 0.49, 2)
    return float(math.ceil(value) - 0.01)


def calculate_price(cost_cny: float, marketplace: str, cfg: dict[str, Any]) -> PriceResult:
    currency = cfg.get("currency", marketplace)
    exchange = float(cfg.get("exchange_rate_cny_to_local", 1.0))
    domestic = float(cfg.get("domestic_shipping_cny", 0.0))
    first_leg = float(cfg.get("first_leg_cny", 0.0))
    commission_rate = float(cfg.get("commission_rate", 0.0))
    vat_rate = float(cfg.get("vat_rate", 0.0))
    target_margin = float(cfg.get("target_margin_rate", 0.25))
    promo_buffer = float(cfg.get("promo_buffer_rate", 0.0))

    landed_cost_local = (cost_cny + domestic + first_leg) * exchange
    denominator = 1.0 - commission_rate - vat_rate - target_margin - promo_buffer
    if denominator <= 0.05:
        denominator = 0.05
    raw_price = landed_cost_local / denominator
    list_price = round_market_price(raw_price)
    estimated_fee = list_price * commission_rate
    estimated_vat = list_price * vat_rate
    estimated_profit = list_price - landed_cost_local - estimated_fee - estimated_vat
    margin_rate = estimated_profit / list_price if list_price else 0.0
    return PriceResult(
        marketplace=marketplace,
        currency=currency,
        cost_cny=round(cost_cny, 2),
        list_price=round(list_price, 2),
        landed_cost_local=round(landed_cost_local, 2),
        estimated_fee_local=round(estimated_fee, 2),
        estimated_vat_local=round(estimated_vat, 2),
        estimated_profit_local=round(estimated_profit, 2),
        margin_rate=round(margin_rate, 4),
    )
