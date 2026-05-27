"""
Utility Portal CSV Parser

Research findings (see SOURCES.md):
Utility portals (EnergyHub, Urjanet, Green Button, utility self-service portals) 
typically export CSVs with these shapes:

1. Green Button (NAESB REQ.21) - XML primarily, CSV variant available
2. Utility self-service portal exports (e.g., PG&E, National Grid, EDF)
3. Urjanet / Arcadia data feeds (aggregator CSVs)

Key challenges:
- Billing periods don't align with calendar months (e.g., 17-Oct to 19-Nov)
- Multiple meters per facility (sub-meters, check meters)
- Units: kWh is standard but some exports use MWh or kW (demand vs consumption confusion)
- Tariff structure mixed in (demand charges, reactive power) alongside consumption
- Supply mix / REES data sometimes embedded (for market-based Scope 2)
- Estimated vs actual reads flagged differently per utility

We chose portal CSV export because:
1. All utilities offer it; no API credentials needed
2. Green Button XML adds complexity for same data
3. Urjanet/Arcadia requires paid subscription

Grid emission factors: DEFRA 2023 UK average + EPA eGRID 2022 US
For market-based: if REGOs/RECs supplied, use 0 (renewable), else location-based fallback
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import List, Tuple, Optional, Dict
import re

# Location-based grid emission factors (kgCO2e per kWh)
# Source: DEFRA 2023 (UK), EPA eGRID 2022 (US regions), IEA 2022 (others)
GRID_EMISSION_FACTORS = {
    'UK': Decimal('0.20493'),
    'US-ERCT': Decimal('0.42312'),   # ERCOT (Texas)
    'US-WECC': Decimal('0.27084'),   # Western US
    'US-RFC': Decimal('0.38200'),    # Mid-Atlantic
    'US-SERC': Decimal('0.40000'),   # Southeast
    'US': Decimal('0.38600'),        # US average
    'EU': Decimal('0.27600'),        # EU average
    'IN': Decimal('0.70800'),        # India
    'DEFAULT': Decimal('0.40000'),   # Conservative fallback
}


def _parse_date_flexible(date_str: str) -> Optional[date]:
    """Try multiple date formats common in utility exports."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    formats = [
        '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y',
        '%d %b %Y', '%b %d, %Y', '%Y%m%d',
        '%m/%d/%y', '%d/%m/%y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _normalise_kwh(value: Decimal, unit: str) -> Decimal:
    """Normalise energy consumption to kWh."""
    unit = unit.strip().upper()
    if unit in ('KWH', 'KW·H', 'KILOWATT-HOUR', 'KILOWATTHOUR'):
        return value
    elif unit in ('MWH', 'MEGAWATT-HOUR', 'MEGAWATTHOUR'):
        return value * 1000
    elif unit in ('GWH',):
        return value * 1_000_000
    elif unit == 'J':
        return value / Decimal('3600000')
    elif unit == 'GJ':
        return value / Decimal('0.0036')
    elif unit == 'MMBTU':
        return value * Decimal('293.071')
    return value  # assume kWh if unknown


def _detect_columns(fieldnames: list) -> dict:
    """
    Map arbitrary column names to canonical names.
    Utility portals have no standard — this handles the most common variants.
    """
    lower_map = {f.lower().strip(): f for f in fieldnames}

    def find_col(*candidates):
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    return {
        'meter_id': find_col('meter id', 'meter_id', 'meterid', 'account number', 'meter number', 'meter serial'),
        'site': find_col('site', 'site name', 'location', 'address', 'facility', 'premise'),
        'period_start': find_col('start date', 'period start', 'from date', 'billing start', 'read from', 'service from'),
        'period_end': find_col('end date', 'period end', 'to date', 'billing end', 'read to', 'service to', 'service through'),
        'consumption': find_col('consumption', 'usage', 'kwh', 'energy', 'total consumption', 'kwh usage', 'net consumption'),
        'unit': find_col('unit', 'units', 'uom', 'consumption unit', 'usage unit'),
        'read_type': find_col('read type', 'actual/estimated', 'est/actual', 'read status'),
        'tariff': find_col('tariff', 'rate', 'rate code', 'service type'),
        'renewable_pct': find_col('renewable %', 'green %', 'renewable pct', 'rego', 'rec pct'),
        'meter_type': find_col('meter type', 'commodity', 'service', 'utility type'),
    }


def parse_utility_csv(
    file_content: str,
    grid_region: str = 'DEFAULT',
    market_based: bool = False,
) -> Tuple[List[dict], List[dict]]:
    """
    Parse a utility portal CSV export.

    Args:
        file_content: Raw CSV string
        grid_region: Grid region code for location-based emission factor lookup
        market_based: If True, use market-based approach (check for renewable supply)

    Returns:
        (parsed_rows, error_rows)
    """
    parsed, errors = [], []

    # Detect delimiter
    sample = file_content[:2000]
    delimiter = ',' if sample.count(',') >= sample.count(';') else ';'

    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)
    if not reader.fieldnames:
        return [], [{'row': 0, 'error': 'Empty file or no headers found'}]

    cols = _detect_columns(reader.fieldnames)

    # Emission factor selection
    ef = GRID_EMISSION_FACTORS.get(grid_region, GRID_EMISSION_FACTORS['DEFAULT'])
    ef_source = f"DEFRA 2023 / EPA eGRID 2022 | Region: {grid_region}"

    for i, row in enumerate(reader):
        row_num = i + 2

        try:
            # Skip obviously non-data rows (subtotals, blanks)
            values = list(row.values())
            if all(not v or not v.strip() for v in values):
                continue
            first_val = values[0] if values else ''
            if any(skip in first_val.lower() for skip in ('total', 'subtotal', 'summary', '---')):
                continue

            # Consumption
            consumption_str = (row.get(cols['consumption']) or '').strip().replace(',', '')
            if not consumption_str:
                errors.append({'row': row_num, 'error': 'Missing consumption value', 'raw': dict(row)})
                continue

            try:
                consumption_raw = Decimal(consumption_str)
            except InvalidOperation:
                errors.append({'row': row_num, 'error': f'Invalid consumption: {consumption_str}', 'raw': dict(row)})
                continue

            if consumption_raw < 0:
                errors.append({'row': row_num, 'error': f'Negative consumption: {consumption_raw} (check for credits)', 'raw': dict(row)})
                continue

            # Unit
            unit_raw = (row.get(cols['unit']) or 'kWh').strip()
            consumption_kwh = _normalise_kwh(consumption_raw, unit_raw)

            # Dates — billing periods often don't align to calendar months
            start_str = row.get(cols['period_start']) or ''
            end_str = row.get(cols['period_end']) or ''
            period_start = _parse_date_flexible(start_str)
            period_end = _parse_date_flexible(end_str)

            if not period_end:
                errors.append({'row': row_num, 'error': f'Cannot parse period end date: {end_str!r}', 'raw': dict(row)})
                continue
            if not period_start:
                # Approximate: 30 days before end
                from datetime import timedelta
                period_start = period_end.replace(day=1)

            # Market-based: check renewable percentage
            actual_ef = ef
            scope_type = 'scope2_lb'
            suspicion_reasons = []

            if market_based:
                ren_pct_str = (row.get(cols['renewable_pct']) or '').strip().replace('%', '')
                if ren_pct_str:
                    try:
                        ren_pct = Decimal(ren_pct_str)
                        effective_carbon_pct = (100 - ren_pct) / 100
                        actual_ef = ef * effective_carbon_pct
                        scope_type = 'scope2_mb'
                    except InvalidOperation:
                        pass

            co2e = consumption_kwh * actual_ef

            # Read type flag
            read_type = (row.get(cols['read_type']) or '').strip().lower()
            if any(t in read_type for t in ('est', 'estimated', 'e')):
                suspicion_reasons.append('estimated_read')

            # Unusually high consumption check (>500,000 kWh per record is worth a flag)
            if consumption_kwh > 500000:
                suspicion_reasons.append('high_consumption_flag')

            meter_id = row.get(cols['meter_id']) or ''
            site = row.get(cols['site']) or ''

            parsed.append({
                'scope': scope_type,
                'category': 'electricity',
                'quantity_kg_co2e': co2e,
                'period_start': period_start,
                'period_end': period_end,
                'description': f"Electricity | {site or meter_id} | {consumption_kwh:.1f} kWh",
                'source_quantity': float(consumption_kwh),
                'source_unit': 'kWh',
                'source_date_raw': f"{start_str} → {end_str}",
                'source_row_id': f"UTIL-{i+1}-{meter_id}",
                'emission_factor_value': float(actual_ef),
                'emission_factor_unit': 'kgCO2e per kWh',
                'emission_factor_source': ef_source,
                'source_extra': {
                    'meter_id': meter_id,
                    'site': site,
                    'unit_original': unit_raw,
                    'read_type': read_type,
                    'tariff': row.get(cols['tariff']) or '',
                },
                'is_suspicious': bool(suspicion_reasons),
                'suspicion_reasons': suspicion_reasons,
            })

        except Exception as e:
            errors.append({'row': row_num, 'error': str(e), 'raw': dict(row)})

    return parsed, errors
