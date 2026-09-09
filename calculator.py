from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping


def round_up_100(value: float) -> int:
    return int(math.ceil(max(0.0, value) / 100.0) * 100)


# -----------------------------------------------------------------------------
# Existing simple / house-cleaning quote calculator
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class CompanySettings:
    labor_cost_per_person_hour: float = 2000.0
    vehicle_cost_per_km: float = 35.0
    monthly_fixed_cost: float = 60000.0
    monthly_job_count: float = 30.0
    minimum_margin: float = 0.15
    target_margin: float = 0.30
    aggressive_markup: float = 0.10
    minimum_charge: float = 12000.0


@dataclass(frozen=True)
class JobConditions:
    occupancy_multiplier: float = 1.15
    dirt_multiplier: float = 1.00
    pet_additional_person_hours: float = 0.0
    crew_size: int = 1
    one_way_minutes: float = 30.0
    one_way_km: float = 10.0
    parking_cost: float = 0.0
    subcontract_cost: float = 0.0
    other_variable_cost: float = 0.0


def calculate_quote(
    selected_services: Iterable[Mapping[str, float]],
    settings: CompanySettings,
    conditions: JobConditions,
    custom_person_hours: float = 0.0,
    custom_material_cost: float = 0.0,
    custom_public_reference: float = 0.0,
) -> dict:
    service_hours_raw = 0.0
    material_cost = 0.0
    public_reference = 0.0

    for item in selected_services:
        qty = max(0.0, float(item.get("quantity", 0)))
        service_hours_raw += qty * float(item.get("standard_person_hours", 0))
        material_cost += qty * float(item.get("material_cost_yen", 0))
        public_reference += qty * float(item.get("public_price_reference_yen", 0))

    service_hours_raw += max(0.0, custom_person_hours)
    material_cost += max(0.0, custom_material_cost)
    public_reference += max(0.0, custom_public_reference)

    adjusted_service_hours = (
        service_hours_raw
        * max(0.0, conditions.occupancy_multiplier)
        * max(0.0, conditions.dirt_multiplier)
    )
    pet_hours = max(0.0, conditions.pet_additional_person_hours)
    travel_person_hours = (
        max(0.0, conditions.one_way_minutes) * 2.0 / 60.0
        * max(1, int(conditions.crew_size))
    )
    total_person_hours = adjusted_service_hours + pet_hours + travel_person_hours
    onsite_clock_hours = (
        (adjusted_service_hours + pet_hours) / max(1, int(conditions.crew_size))
    )

    labor_cost = total_person_hours * max(0.0, settings.labor_cost_per_person_hour)
    vehicle_cost = max(0.0, conditions.one_way_km) * 2.0 * max(0.0, settings.vehicle_cost_per_km)
    fixed_cost_allocation = (
        max(0.0, settings.monthly_fixed_cost) / settings.monthly_job_count
        if settings.monthly_job_count > 0 else 0.0
    )

    total_cost = (
        labor_cost
        + material_cost
        + vehicle_cost
        + max(0.0, conditions.parking_cost)
        + max(0.0, conditions.subcontract_cost)
        + max(0.0, conditions.other_variable_cost)
        + fixed_cost_allocation
    )

    def price_for_margin(margin: float) -> float:
        margin = min(max(float(margin), 0.0), 0.95)
        return total_cost / (1.0 - margin)

    minimum_price_raw = max(settings.minimum_charge, price_for_margin(settings.minimum_margin))
    target_price_raw = max(settings.minimum_charge, price_for_margin(settings.target_margin))
    aggressive_price_raw = target_price_raw * (1.0 + max(0.0, settings.aggressive_markup))

    minimum_price = round_up_100(minimum_price_raw)
    target_price = round_up_100(target_price_raw)
    aggressive_price = round_up_100(aggressive_price_raw)

    return {
        "service_person_hours_raw": service_hours_raw,
        "adjusted_service_person_hours": adjusted_service_hours,
        "pet_person_hours": pet_hours,
        "travel_person_hours": travel_person_hours,
        "total_person_hours": total_person_hours,
        "onsite_clock_hours": onsite_clock_hours,
        "labor_cost": labor_cost,
        "material_cost": material_cost,
        "vehicle_cost": vehicle_cost,
        "parking_cost": max(0.0, conditions.parking_cost),
        "subcontract_cost": max(0.0, conditions.subcontract_cost),
        "other_variable_cost": max(0.0, conditions.other_variable_cost),
        "fixed_cost_allocation": fixed_cost_allocation,
        "total_cost": total_cost,
        "minimum_price": minimum_price,
        "target_price": target_price,
        "aggressive_price": aggressive_price,
        "public_price_reference": public_reference,
        "target_profit": target_price - total_cost,
        "target_profit_margin": (target_price - total_cost) / target_price if target_price else 0.0,
    }


def simulate_offer(offer_price: float, total_cost: float, minimum_margin: float) -> dict:
    offer_price = max(0.0, float(offer_price))
    profit = offer_price - total_cost
    margin = profit / offer_price if offer_price > 0 else 0.0
    return {
        "offer_price": offer_price,
        "profit": profit,
        "margin": margin,
        "acceptable": margin >= minimum_margin,
    }


# -----------------------------------------------------------------------------
# New recurring / commercial cleaning estimator
# -----------------------------------------------------------------------------

FREQUENCY_TO_MONTHLY_VISITS = {
    "月1回": 1.0,
    "月2回": 2.0,
    "週1回": 52.0 / 12.0,
    "週2回": 2.0 * 52.0 / 12.0,
    "週3回": 3.0 * 52.0 / 12.0,
    "週5回": 5.0 * 52.0 / 12.0,
    "週6回": 6.0 * 52.0 / 12.0,
    "毎日": 365.0 / 12.0,
}


def recurring_cleaning_quote(
    *,
    area_sqm: float,
    productivity_sqm_per_person_hour: float,
    crew_size: int,
    monthly_visits: float,
    labor_cost_per_person_hour: float,
    monthly_material_cost: float,
    monthly_transport_cost: float,
    monthly_other_direct_cost: float,
    overhead_rate: float,
    target_margin: float,
    current_contract_price: float = 0.0,
    future_labor_cost_per_person_hour: float | None = None,
) -> dict:
    """Calculate a recurring-cleaning monthly quote.

    Notes
    -----
    * `productivity_sqm_per_person_hour` must be supplied by the user. It is not
      intended to represent a universal industry standard.
    * `overhead_rate` is applied to direct operating cost for a simple MVP model.
    * `target_margin` is margin on sales, so price = cost / (1 - margin).
    """

    area_sqm = max(0.0, float(area_sqm))
    productivity = max(0.000001, float(productivity_sqm_per_person_hour))
    crew_size = max(1, int(crew_size))
    monthly_visits = max(0.0, float(monthly_visits))
    labor_rate = max(0.0, float(labor_cost_per_person_hour))
    materials = max(0.0, float(monthly_material_cost))
    transport = max(0.0, float(monthly_transport_cost))
    other_direct = max(0.0, float(monthly_other_direct_cost))
    overhead_rate = min(max(float(overhead_rate), 0.0), 5.0)
    target_margin = min(max(float(target_margin), 0.0), 0.95)
    current_contract_price = max(0.0, float(current_contract_price))

    person_hours_per_visit = area_sqm / productivity
    clock_hours_per_visit = person_hours_per_visit / crew_size
    monthly_person_hours = person_hours_per_visit * monthly_visits
    monthly_labor_cost = monthly_person_hours * labor_rate
    direct_cost = monthly_labor_cost + materials + transport + other_direct
    overhead_cost = direct_cost * overhead_rate
    total_cost = direct_cost + overhead_cost
    recommended_price_raw = total_cost / (1.0 - target_margin) if target_margin < 1.0 else float("inf")
    recommended_price = round_up_100(recommended_price_raw)
    target_profit = recommended_price - total_cost
    price_per_visit = recommended_price / monthly_visits if monthly_visits > 0 else 0.0
    monthly_price_per_sqm = recommended_price / area_sqm if area_sqm > 0 else 0.0

    current_profit = current_contract_price - total_cost if current_contract_price > 0 else None
    current_margin = (
        current_profit / current_contract_price
        if current_contract_price > 0 and current_profit is not None
        else None
    )

    future = None
    if future_labor_cost_per_person_hour is not None:
        future_labor_rate = max(0.0, float(future_labor_cost_per_person_hour))
        future_labor_cost = monthly_person_hours * future_labor_rate
        future_direct_cost = future_labor_cost + materials + transport + other_direct
        future_overhead_cost = future_direct_cost * overhead_rate
        future_total_cost = future_direct_cost + future_overhead_cost
        future_recommended_price = round_up_100(
            future_total_cost / (1.0 - target_margin) if target_margin < 1.0 else float("inf")
        )
        future = {
            "labor_rate": future_labor_rate,
            "labor_cost": future_labor_cost,
            "total_cost": future_total_cost,
            "recommended_price": future_recommended_price,
            "cost_increase": future_total_cost - total_cost,
            "price_increase": future_recommended_price - recommended_price,
            "current_contract_gap": (
                future_recommended_price - current_contract_price
                if current_contract_price > 0
                else None
            ),
        }

    return {
        "person_hours_per_visit": person_hours_per_visit,
        "clock_hours_per_visit": clock_hours_per_visit,
        "monthly_visits": monthly_visits,
        "monthly_person_hours": monthly_person_hours,
        "monthly_labor_cost": monthly_labor_cost,
        "monthly_material_cost": materials,
        "monthly_transport_cost": transport,
        "monthly_other_direct_cost": other_direct,
        "direct_cost": direct_cost,
        "overhead_cost": overhead_cost,
        "total_cost": total_cost,
        "recommended_price": recommended_price,
        "target_profit": target_profit,
        "target_profit_margin": target_profit / recommended_price if recommended_price else 0.0,
        "price_per_visit": price_per_visit,
        "monthly_price_per_sqm": monthly_price_per_sqm,
        "current_contract_price": current_contract_price,
        "current_profit": current_profit,
        "current_margin": current_margin,
        "future": future,
    }
