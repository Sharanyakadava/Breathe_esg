"""
SAP Flat File Parser

Research findings (see SOURCES.md):
We chose SAP's Application Link Enabling (ALE) flat file / IDOC-style export because:
1. It's what sustainability teams actually get when they don't have API access
2. OData requires SAP NetWeaver Gateway configured by IT; most clients can't enable this
3. BAPIs require ABAP expertise; flat file exports are self-service
4. The typical export is a delimited text file with a fixed header structure

Real SAP flat files have:
- MARA/MARC material master segments with plant codes (WERKS)
- EKPO/EKKO purchasing document items with material groups (MATKL)
- Date fields in YYYYMMDD format (SAP internal)
- Quantity + UOM in separate columns (MENGE, MEINS)
- German or EN column headers depending on system language setting
- Cost center (KOSTL) for Scope 1 fuel entries
- Movement type (BWART) for goods movements (201=cost center issue, 261=production order)

We map movement type 201 (GI for cost center) = stationary combustion fuel
Movement type 261 = mobile/production fuel
Material group FUELX* = fuel materials, PROCX* = procurement
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from datetime import date
import re
from typing import List, Dict, Tuple, Optional

# Fuel emission factors (kg CO2e per unit)
# Source: DEFRA 2023 Conversion Factors
FUEL_EMISSION_FACTORS = {
    # liquid fuels - per litre
    'diesel': {'factor': Decimal('2.5147'), 'unit': 'litre', 'scope': 'scope1', 'category': 'fuel_stationary'},
    'petrol': {'factor': Decimal('2.3096'), 'unit': 'litre', 'scope': 'scope1', 'category': 'fuel_mobile'},
    'hfo': {'factor': Decimal('3.1790'), 'unit': 'litre', 'scope': 'scope1', 'category': 'fuel_stationary'},
    # gaseous - per m3
    'naturalgas': {'factor': Decimal('2.0427'), 'unit': 'm3', 'scope': 'scope1', 'category': 'fuel_stationary'},
    'lpg': {'factor': Decimal('1.5554'), 'unit': 'litre', 'scope': 'scope1', 'category': 'fuel_stationary'},
    # default fallback per kg
    'coal': {'factor': Decimal('2.4238'), 'unit': 'kg', 'scope': 'scope1', 'category': 'fuel_stationary'},
}

# SAP UOM (MEINS) → standard unit mappings
SAP_UOM_MAP = {
    'L': 'litre',
    'LT': 'litre',
    'LTR': 'litre',
    'M3': 'm3',
    'KG': 'kg',
    'G': 'kg',  # convert grams to kg
    'T': 'kg',  # tonnes → kg (multiply by 1000)
    'GAL': 'litre',  # US gallon → litre (multiply by 3.785)
}

# SAP movement types relevant to Scope 1
SCOPE1_MOVEMENT_TYPES = {'201', '261', '262'}

# Procurement material groups → Scope 3
PROCUREMENT_MATKL_PREFIXES = ('PROC', 'RAW', 'PACK', 'CHEM')


def _parse_sap_date(date_str: str) -> Optional[date]:
    """SAP stores dates as YYYYMMDD internally. Some exports add slashes."""
    if not date_str or date_str.strip() in ('', '00000000', '0'):
        return None
    date_str = date_str.strip().replace('/', '').replace('-', '')
    try:
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except (ValueError, IndexError):
        return None


def _convert_quantity(qty: Decimal, sap_uom: str) -> Tuple[Decimal, str]:
    """Normalise SAP UOM to standard units."""
    uom = sap_uom.upper().strip()
    std_unit = SAP_UOM_MAP.get(uom, uom.lower())
    if uom == 'G':
        qty = qty / 1000
    elif uom == 'T':
        qty = qty * 1000
    elif uom == 'GAL':
        qty = qty * Decimal('3.78541')
    return qty, std_unit


def _detect_fuel_type(material_desc: str, material_group: str) -> Optional[str]:
    """Best-effort fuel type detection from material description/group."""
    text = (material_desc + ' ' + material_group).lower()
    if 'diesel' in text:
        return 'diesel'
    if 'petrol' in text or 'gasolin' in text or 'benzin' in text:
        return 'petrol'
    if 'natural gas' in text or 'erdgas' in text or 'natgas' in text:
        return 'naturalgas'
    if 'lpg' in text or 'propane' in text or 'butan' in text:
        return 'lpg'
    if 'heavy fuel' in text or 'hfo' in text or 'mazut' in text:
        return 'hfo'
    if 'coal' in text or 'kohle' in text:
        return 'coal'
    return None


def parse_sap_flat_file(file_content: str, tenant_facilities: dict) -> Tuple[List[dict], List[dict]]:
    """
    Parse SAP flat file export.

    Expected columns (tab or semicolon delimited):
    BWART, WERKS, BUKRS, BUDAT, BLDAT, MATNR, MATKL, MAKTX, MENGE, MEINS,
    KOSTL, AUFNR, DMBTR, WAERS

    German equivalents also accepted:
    Bewegungsart, Werk, Buchungskreis, Buchungsdatum, Belegdatum, etc.

    Returns: (parsed_rows, error_rows)
    """
    # Column name aliases: German → canonical English
    COLUMN_ALIASES = {
        'bewegungsart': 'BWART',
        'werk': 'WERKS',
        'buchungskreis': 'BUKRS',
        'buchungsdatum': 'BUDAT',
        'belegdatum': 'BLDAT',
        'materialnummer': 'MATNR',
        'materialgruppe': 'MATKL',
        'materialkurztext': 'MAKTX',
        'menge': 'MENGE',
        'mengeneinheit': 'MEINS',
        'kostenstelle': 'KOSTL',
        'auftrag': 'AUFNR',
        'betrag in hauswährung': 'DMBTR',
        'währung': 'WAERS',
        # English variants
        'movement type': 'BWART',
        'plant': 'WERKS',
        'posting date': 'BUDAT',
        'document date': 'BLDAT',
        'material': 'MATNR',
        'material group': 'MATKL',
        'material description': 'MAKTX',
        'quantity': 'MENGE',
        'uom': 'MEINS',
        'cost center': 'KOSTL',
    }

    parsed, errors = [], []

    # Detect delimiter
    sample = file_content[:2000]
    delimiter = ';' if sample.count(';') > sample.count('\t') else '\t'
    if sample.count(',') > sample.count(delimiter):
        delimiter = ','

    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    # Normalize column headers
    original_fieldnames = reader.fieldnames or []
    col_map = {}
    for col in original_fieldnames:
        canonical = COLUMN_ALIASES.get(col.lower().strip(), col.upper().strip())
        col_map[col] = canonical

    for i, row in enumerate(reader):
        row_num = i + 2
        norm_row = {col_map.get(k, k): v for k, v in row.items()}

        try:
            bwart = norm_row.get('BWART', '').strip()
            if not bwart:
                errors.append({'row': row_num, 'error': 'Missing BWART (movement type)', 'raw': dict(row)})
                continue

            menge_str = norm_row.get('MENGE', '').strip().replace(',', '.')
            if not menge_str:
                errors.append({'row': row_num, 'error': 'Missing MENGE (quantity)', 'raw': dict(row)})
                continue

            try:
                menge = Decimal(menge_str)
            except InvalidOperation:
                errors.append({'row': row_num, 'error': f'Invalid MENGE: {menge_str}', 'raw': dict(row)})
                continue

            meins = norm_row.get('MEINS', 'L').strip()
            werks = norm_row.get('WERKS', '').strip()
            matkl = norm_row.get('MATKL', '').strip()
            maktx = norm_row.get('MAKTX', '').strip()
            budat = _parse_sap_date(norm_row.get('BUDAT', ''))
            bldat = _parse_sap_date(norm_row.get('BLDAT', ''))
            period_date = budat or bldat

            if not period_date:
                errors.append({'row': row_num, 'error': 'Cannot parse date', 'raw': dict(row)})
                continue

            # Determine if this is fuel/scope1 or procurement/scope3
            is_fuel = bwart in SCOPE1_MOVEMENT_TYPES
            is_procurement = any(matkl.upper().startswith(pfx) for pfx in PROCUREMENT_MATKL_PREFIXES)

            if not (is_fuel or is_procurement):
                # Skip non-relevant movement types
                continue

            qty_std, unit_std = _convert_quantity(menge, meins)

            # Facility lookup
            facility_id = tenant_facilities.get(werks)

            if is_fuel:
                fuel_type = _detect_fuel_type(maktx, matkl)
                if not fuel_type:
                    factor_info = None
                    co2e = None
                    suspicion = ['unknown_fuel_type']
                else:
                    factor_info = FUEL_EMISSION_FACTORS.get(fuel_type)
                    co2e = qty_std * factor_info['factor'] if factor_info else None
                    suspicion = []

                parsed.append({
                    'scope': factor_info['scope'] if factor_info else 'scope1',
                    'category': factor_info['category'] if factor_info else 'fuel_stationary',
                    'quantity_kg_co2e': co2e,
                    'period_start': period_date.replace(day=1),
                    'period_end': period_date,
                    'facility_id': facility_id,
                    'description': f"{maktx} | Plant: {werks} | MvT: {bwart}",
                    'source_quantity': float(qty_std),
                    'source_unit': unit_std,
                    'source_date_raw': norm_row.get('BUDAT', ''),
                    'source_row_id': f"SAP-{i+1}-{norm_row.get('MATNR', '')}",
                    'emission_factor_value': float(factor_info['factor']) if factor_info else None,
                    'emission_factor_unit': f"kgCO2e per {factor_info['unit']}" if factor_info else '',
                    'emission_factor_source': 'DEFRA 2023',
                    'source_extra': {
                        'BWART': bwart, 'WERKS': werks, 'MATKL': matkl,
                        'KOSTL': norm_row.get('KOSTL', ''), 'DMBTR': norm_row.get('DMBTR', ''),
                    },
                    'is_suspicious': bool(suspicion) or co2e is None,
                    'suspicion_reasons': suspicion + ([] if co2e else ['co2e_not_calculated']),
                })
            else:
                # Procurement → Scope 3; spend-based, rough estimate
                dmbtr_str = norm_row.get('DMBTR', '0').replace(',', '.')
                try:
                    spend = Decimal(dmbtr_str)
                except InvalidOperation:
                    spend = Decimal('0')
                # Rough spend-based factor: 0.5 kgCO2e per currency unit (placeholder)
                co2e = spend * Decimal('0.5')
                parsed.append({
                    'scope': 'scope3',
                    'category': 'procurement',
                    'quantity_kg_co2e': co2e,
                    'period_start': period_date.replace(day=1),
                    'period_end': period_date,
                    'facility_id': facility_id,
                    'description': f"Procurement: {maktx} | {matkl}",
                    'source_quantity': float(spend),
                    'source_unit': norm_row.get('WAERS', 'USD'),
                    'source_date_raw': norm_row.get('BUDAT', ''),
                    'source_row_id': f"SAP-{i+1}-{norm_row.get('MATNR', '')}",
                    'emission_factor_value': 0.5,
                    'emission_factor_unit': 'kgCO2e per currency unit',
                    'emission_factor_source': 'Spend-based estimate (EEIO placeholder)',
                    'source_extra': {'MATKL': matkl, 'WAERS': norm_row.get('WAERS', ''), 'BWART': bwart},
                    'is_suspicious': True,
                    'suspicion_reasons': ['spend_based_estimate_needs_review'],
                })

        except Exception as e:
            errors.append({'row': row_num, 'error': str(e), 'raw': dict(row)})

    return parsed, errors
