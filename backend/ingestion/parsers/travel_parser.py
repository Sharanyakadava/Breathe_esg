"""
Corporate Travel Parser (Concur / Navan / TripActions style CSV exports)

Research findings (see SOURCES.md):
- Concur Travel exports via Report Admin → Standard Accounting Extract or Custom Report
- Navan (TripActions) provides CSV exports via Reporting > Trips
- Both platforms export per-trip or per-segment data

Key fields available:
- For flights: origin airport code, destination airport code, cabin class, ticket cost
  Distances are NOT always given — must compute from IATA airport coordinates
- For hotels: check-in date, check-out date, city, property name, nights, cost
- For ground: vendor name (Uber, rental car co), miles/km sometimes present

Emission factors:
- Flights: DEFRA 2023 per passenger km with uplift factor 1.891 for radiative forcing
  Short-haul (<1500km), medium-haul (1500-3500km), long-haul (>3500km) have different factors
  Cabin class multipliers: economy x1, business x2.6, first x4.0
- Hotels: DEFRA 2023 per room-night by region (~10-20 kgCO2e per night typical)
- Ground (car rental): DEFRA 2023 per km by car type; if km unknown, estimate from cost
- Taxi/rideshare: DEFRA 2023 average taxi (diesel) ~0.14895 kgCO2e/km

All are Scope 3, Category 6 (Business Travel) under GHG Protocol.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import List, Tuple, Optional, Dict
import math

# IATA airport coordinates (major airports — expand for production)
AIRPORT_COORDS: Dict[str, Tuple[float, float]] = {
    'LHR': (51.4775, -0.4614), 'LGW': (51.1481, -0.1903), 'LCY': (51.5048, 0.0495),
    'JFK': (40.6413, -73.7781), 'EWR': (40.6895, -74.1745), 'LGA': (40.7769, -73.8740),
    'ORD': (41.9742, -87.9073), 'LAX': (33.9425, -118.4081), 'SFO': (37.6213, -122.3790),
    'MIA': (25.7959, -80.2870), 'ATL': (33.6407, -84.4277), 'DFW': (32.8998, -97.0403),
    'BOS': (42.3656, -71.0096), 'SEA': (47.4502, -122.3088), 'DEN': (39.8561, -104.6737),
    'CDG': (49.0097, 2.5479), 'AMS': (52.3105, 4.7683), 'FRA': (50.0379, 8.5622),
    'MUC': (48.3538, 11.7861), 'MAD': (40.4983, -3.5676), 'BCN': (41.2971, 2.0785),
    'FCO': (41.8003, 12.2389), 'ZRH': (47.4647, 8.5492), 'VIE': (48.1103, 16.5697),
    'BRU': (50.9014, 4.4844), 'CPH': (55.6180, 12.6508), 'ARN': (59.6519, 17.9186),
    'DXB': (25.2532, 55.3657), 'SIN': (1.3644, 103.9915), 'HKG': (22.3080, 113.9185),
    'NRT': (35.7720, 140.3929), 'HND': (35.5494, 139.7798), 'PEK': (40.0799, 116.6031),
    'PVG': (31.1434, 121.8052), 'BOM': (19.0896, 72.8656), 'DEL': (28.5562, 77.1000),
    'SYD': (-33.9461, 151.1772), 'MEL': (-37.6733, 144.8430), 'JNB': (-26.1367, 28.2411),
    'GRU': (-23.4356, -46.4731), 'MEX': (19.4361, -99.0719), 'YYZ': (43.6772, -79.6306),
}

# Flight emission factors (kgCO2e per passenger km) including radiative forcing
# Source: DEFRA 2023 with uplift factor 1.891
FLIGHT_FACTORS = {
    'short_haul': {  # <1500 km
        'economy': Decimal('0.25510'),
        'business': Decimal('0.39304'),
        'first': Decimal('0.39304'),  # no first on short haul typically
    },
    'medium_haul': {  # 1500-3500 km
        'economy': Decimal('0.15553'),
        'business': Decimal('0.22829'),
        'first': Decimal('0.22829'),
    },
    'long_haul': {  # >3500 km
        'economy': Decimal('0.19085'),
        'business': Decimal('0.49621'),
        'first': Decimal('0.76341'),
    },
}

# Hotel emission factors (kgCO2e per room-night) by region - DEFRA 2023
HOTEL_FACTORS = {
    'UK': Decimal('17.00'),
    'US': Decimal('14.00'),
    'EU': Decimal('10.00'),
    'DEFAULT': Decimal('12.00'),
}

# Ground transport emission factors (kgCO2e per km) - DEFRA 2023
GROUND_FACTORS = {
    'rental_car': Decimal('0.16770'),  # average petrol car
    'taxi': Decimal('0.14895'),
    'rideshare': Decimal('0.14895'),
    'bus': Decimal('0.02732'),
    'train': Decimal('0.03549'),
    'DEFAULT': Decimal('0.14895'),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def _flight_distance_km(origin: str, destination: str) -> Optional[float]:
    origin = origin.upper().strip()
    destination = destination.upper().strip()
    if origin in AIRPORT_COORDS and destination in AIRPORT_COORDS:
        lat1, lon1 = AIRPORT_COORDS[origin]
        lat2, lon2 = AIRPORT_COORDS[destination]
        return _haversine_km(lat1, lon1, lat2, lon2)
    return None


def _get_haul_class(distance_km: float) -> str:
    if distance_km < 1500:
        return 'short_haul'
    elif distance_km < 3500:
        return 'medium_haul'
    return 'long_haul'


def _normalise_cabin(cabin_str: str) -> str:
    cabin = cabin_str.lower().strip()
    if any(t in cabin for t in ('business', 'biz', 'club', 'j', 'c')):
        return 'business'
    if any(t in cabin for t in ('first', 'f ')):
        return 'first'
    return 'economy'


def _parse_date_flex(s: str) -> Optional[date]:
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y', '%d %b %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _detect_travel_type(row: dict) -> str:
    """Heuristic to determine if row is air/hotel/ground."""
    # Normalise keys for lookup
    norm = {k.lower().strip(): v for k, v in row.items()}

    # Check expense type / category column value first (most reliable)
    type_field = (
        norm.get('expense type') or norm.get('trip type') or
        norm.get('category') or norm.get('type') or norm.get('segment type') or ''
    ).lower().strip()

    if any(t in type_field for t in ('air', 'flight', 'aviation')):
        return 'air'
    if any(t in type_field for t in ('hotel', 'lodging', 'accommodation')):
        return 'hotel'
    if any(t in type_field for t in ('car rental', 'rental', 'taxi', 'uber', 'lyft', 'rideshare', 'train', 'rail', 'bus', 'ground')):
        return 'ground'

    # Vendor / value hints
    vendor = (norm.get('vendor') or norm.get('carrier') or norm.get('airline') or norm.get('supplier') or '').lower()
    if any(t in vendor for t in ('hotel', 'inn', 'marriott', 'hilton', 'hyatt', 'sheraton', 'radisson', 'accor', 'ibis')):
        return 'hotel'
    if any(t in vendor for t in ('uber', 'lyft', 'taxi', 'hertz', 'avis', 'budget', 'enterprise', 'national', 'europcar')):
        return 'ground'
    if any(t in vendor for t in ('airlines', 'airways', 'air ', 'lufthansa', 'british', 'united', 'delta', 'american', 'klm', 'ana', 'jal')):
        return 'air'

    # Column name hints (structure of file)
    col_names = ' '.join(row.keys()).lower()
    if any(k in col_names for k in ('origin', 'departure airport', 'arrival airport')):
        return 'air'
    if any(k in col_names for k in ('check-in', 'checkin', 'check_in', 'nights', 'property')):
        return 'hotel'

    return 'air'  # default for ambiguous corporate travel rows


def parse_travel_csv(file_content: str) -> Tuple[List[dict], List[dict]]:
    """
    Parse corporate travel CSV (Concur/Navan style).

    Expected columns vary by platform. We attempt auto-detection.
    Returns: (parsed_rows, error_rows)
    """
    parsed, errors = [], []

    delimiter = ',' if file_content[:1000].count(',') >= file_content[:1000].count('\t') else '\t'
    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    if not reader.fieldnames:
        return [], [{'row': 0, 'error': 'No headers found'}]

    lower_fields = {f.lower().strip(): f for f in reader.fieldnames}

    def col(*candidates):
        for c in candidates:
            if c.lower() in lower_fields:
                return lower_fields[c.lower()]
        return None

    # Column detection
    origin_col = col('origin', 'departure airport', 'from', 'departure city', 'origin airport code')
    dest_col = col('destination', 'arrival airport', 'to', 'destination airport', 'destination airport code', 'arrival city')
    cabin_col = col('cabin', 'class', 'cabin class', 'fare class', 'booking class')
    trip_date_col = col('trip date', 'travel date', 'departure date', 'date', 'booking date', 'check-in date', 'checkin date')
    return_date_col = col('return date', 'check-out date', 'checkout date', 'arrival date')
    nights_col = col('nights', 'night count', 'duration nights')
    distance_col = col('distance', 'miles', 'km', 'kilometers', 'distance km', 'distance miles')
    distance_unit_col = col('distance unit', 'unit')
    expense_type_col = col('expense type', 'trip type', 'category', 'type', 'segment type')
    employee_col = col('employee', 'traveler', 'traveller', 'name', 'employee name')
    cost_col = col('amount', 'cost', 'total', 'total cost', 'fare', 'total amount')
    vendor_col = col('vendor', 'carrier', 'airline', 'provider', 'hotel name', 'supplier')
    hotel_country_col = col('country', 'destination country', 'hotel country')

    for i, row in enumerate(reader):
        row_num = i + 2
        try:
            if all(not v or not v.strip() for v in row.values()):
                continue

            travel_type = _detect_travel_type(row)
            trip_date = _parse_date_flex(row.get(trip_date_col) or '')
            period_date = trip_date or date.today()

            if travel_type == 'air':
                origin = (row.get(origin_col) or '').strip().upper()[:3]
                dest = (row.get(dest_col) or '').strip().upper()[:3]

                distance_km = None
                suspicion_reasons = []

                # Try explicit distance first
                if distance_col and row.get(distance_col):
                    try:
                        dist_val = Decimal(str(row.get(distance_col)).strip().replace(',', ''))
                        dist_unit = (row.get(distance_unit_col) or 'km').lower().strip()
                        distance_km = float(dist_val) * (1.60934 if 'mi' in dist_unit else 1.0)
                    except InvalidOperation:
                        pass

                # Fall back to haversine from IATA codes
                if distance_km is None:
                    distance_km = _flight_distance_km(origin, dest)
                    if distance_km is None:
                        suspicion_reasons.append(f'unknown_airport_codes_{origin}_{dest}')
                        distance_km = 1500  # fallback medium haul

                cabin = _normalise_cabin(row.get(cabin_col) or 'economy')
                haul = _get_haul_class(distance_km)
                factor = FLIGHT_FACTORS[haul][cabin]
                co2e = Decimal(str(distance_km)) * factor

                parsed.append({
                    'scope': 'scope3',
                    'category': 'business_travel_air',
                    'quantity_kg_co2e': co2e,
                    'period_start': period_date,
                    'period_end': period_date,
                    'description': f"Flight {origin}→{dest} | {cabin} | {distance_km:.0f}km",
                    'source_quantity': distance_km,
                    'source_unit': 'km',
                    'source_date_raw': row.get(trip_date_col) or '',
                    'source_row_id': f"TRAVEL-{i+1}",
                    'emission_factor_value': float(factor),
                    'emission_factor_unit': f'kgCO2e per km ({haul}, {cabin}, incl. RF)',
                    'emission_factor_source': 'DEFRA 2023 (radiative forcing uplift 1.891)',
                    'source_extra': {
                        'origin': origin, 'destination': dest, 'cabin': cabin,
                        'haul_class': haul,
                        'employee': row.get(employee_col) or '',
                        'vendor': row.get(vendor_col) or '',
                    },
                    'is_suspicious': bool(suspicion_reasons),
                    'suspicion_reasons': suspicion_reasons,
                })

            elif travel_type == 'hotel':
                checkin = _parse_date_flex(row.get(trip_date_col) or '')
                checkout = _parse_date_flex(row.get(return_date_col) or '')

                nights = 1
                if nights_col and row.get(nights_col):
                    try:
                        nights = int(row.get(nights_col))
                    except ValueError:
                        pass
                elif checkin and checkout:
                    nights = max(1, (checkout - checkin).days)

                country = (row.get(hotel_country_col) or 'DEFAULT').strip().upper()[:2]
                factor = HOTEL_FACTORS.get(country, HOTEL_FACTORS['DEFAULT'])
                co2e = factor * nights
                suspicion_reasons = []
                if nights > 30:
                    suspicion_reasons.append('unusually_long_hotel_stay')

                parsed.append({
                    'scope': 'scope3',
                    'category': 'business_travel_hotel',
                    'quantity_kg_co2e': co2e,
                    'period_start': checkin or period_date,
                    'period_end': checkout or period_date,
                    'description': f"Hotel: {row.get(vendor_col) or 'unknown'} | {nights} nights",
                    'source_quantity': float(nights),
                    'source_unit': 'room-night',
                    'source_date_raw': row.get(trip_date_col) or '',
                    'source_row_id': f"TRAVEL-{i+1}",
                    'emission_factor_value': float(factor),
                    'emission_factor_unit': 'kgCO2e per room-night',
                    'emission_factor_source': 'DEFRA 2023',
                    'source_extra': {'vendor': row.get(vendor_col) or '', 'country': country},
                    'is_suspicious': bool(suspicion_reasons),
                    'suspicion_reasons': suspicion_reasons,
                })

            else:  # ground
                vendor = (row.get(vendor_col) or '').lower()
                vtype = 'DEFAULT'
                for t in ('taxi', 'uber', 'lyft', 'rideshare', 'rental', 'car', 'train', 'rail', 'bus'):
                    if t in vendor:
                        vtype = t if t in GROUND_FACTORS else 'rideshare' if t in ('uber', 'lyft') else 'rental_car' if t == 'rental' else 'DEFAULT'
                        break

                distance_km = None
                if distance_col and row.get(distance_col):
                    try:
                        dist_val = Decimal(str(row.get(distance_col)).replace(',', ''))
                        dist_unit = (row.get(distance_unit_col) or 'km').lower()
                        distance_km = float(dist_val) * (1.60934 if 'mi' in dist_unit else 1.0)
                    except (InvalidOperation, TypeError):
                        pass

                suspicion_reasons = []
                if not distance_km:
                    # Estimate from cost: rough $1/km average
                    cost_str = (row.get(cost_col) or '0').replace(',', '').replace('$', '').replace('£', '').replace('€', '')
                    try:
                        cost = float(cost_str)
                        distance_km = max(cost * 1.0, 5.0)
                        suspicion_reasons.append('distance_estimated_from_cost')
                    except ValueError:
                        distance_km = 20.0
                        suspicion_reasons.append('distance_defaulted_to_20km')

                factor = GROUND_FACTORS.get(vtype, GROUND_FACTORS['DEFAULT'])
                co2e = Decimal(str(distance_km)) * factor

                parsed.append({
                    'scope': 'scope3',
                    'category': 'business_travel_ground',
                    'quantity_kg_co2e': co2e,
                    'period_start': period_date,
                    'period_end': period_date,
                    'description': f"Ground: {row.get(vendor_col) or vtype} | {distance_km:.1f}km",
                    'source_quantity': distance_km,
                    'source_unit': 'km',
                    'source_date_raw': row.get(trip_date_col) or '',
                    'source_row_id': f"TRAVEL-{i+1}",
                    'emission_factor_value': float(factor),
                    'emission_factor_unit': 'kgCO2e per km',
                    'emission_factor_source': 'DEFRA 2023',
                    'source_extra': {'vendor': row.get(vendor_col) or '', 'type': vtype},
                    'is_suspicious': bool(suspicion_reasons),
                    'suspicion_reasons': suspicion_reasons,
                })

        except Exception as e:
            errors.append({'row': row_num, 'error': str(e), 'raw': dict(row)})

    return parsed, errors
