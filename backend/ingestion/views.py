from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from decimal import Decimal
import traceback

from emissions.models import IngestionBatch, EmissionRecord, Tenant, FacilityLookup
from .parsers import parse_sap_flat_file, parse_utility_csv, parse_travel_csv


class IngestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        source_type = request.data.get('source_type')
        tenant_id = request.data.get('tenant')
        uploaded_file = request.FILES.get('file')

        if not source_type or source_type not in ('sap_flat_file', 'utility_csv', 'travel_csv'):
            return Response({'error': 'Invalid source_type'}, status=400)

        if not uploaded_file:
            return Response({'error': 'No file provided'}, status=400)

        # Tenant auth check
        try:
            tenant = Tenant.objects.get(id=tenant_id, memberships__user=request.user)
        except Tenant.DoesNotExist:
            return Response({'error': 'Tenant not found or access denied'}, status=403)

        # Read file
        try:
            file_content = uploaded_file.read().decode('utf-8-sig', errors='replace')
        except Exception as e:
            return Response({'error': f'Cannot read file: {e}'}, status=400)

        # Create batch record
        batch = IngestionBatch.objects.create(
            tenant=tenant,
            source_type=source_type,
            uploaded_by=request.user,
            source_file_name=uploaded_file.name,
            status='processing',
        )

        try:
            # Parse
            if source_type == 'sap_flat_file':
                facilities = {
                    f.sap_plant_code: f.id
                    for f in FacilityLookup.objects.filter(tenant=tenant)
                }
                parsed_rows, error_rows = parse_sap_flat_file(file_content, facilities)

            elif source_type == 'utility_csv':
                grid_region = request.data.get('grid_region', 'DEFAULT')
                market_based = request.data.get('market_based', 'false').lower() == 'true'
                parsed_rows, error_rows = parse_utility_csv(file_content, grid_region, market_based)

            elif source_type == 'travel_csv':
                parsed_rows, error_rows = parse_travel_csv(file_content)

            # Persist records
            with transaction.atomic():
                created_records = []
                for row in parsed_rows:
                    co2e = row.get('quantity_kg_co2e')
                    if co2e is None:
                        error_rows.append({'error': 'co2e_not_calculated', 'raw': row})
                        continue
                    try:
                        from datetime import date as _date
                        ps = row['period_start']
                        pe = row['period_end']
                        if isinstance(ps, _date): ps = ps.isoformat()
                        if isinstance(pe, _date): pe = pe.isoformat()
                        record = EmissionRecord(
                            tenant=tenant,
                            batch=batch,
                            scope=row['scope'],
                            category=row['category'],
                            quantity_kg_co2e=Decimal(str(co2e)),
                            period_start=ps,
                            period_end=pe,
                            description=row.get('description', ''),
                            source_quantity=row.get('source_quantity'),
                            source_unit=row.get('source_unit', ''),
                            source_date_raw=row.get('source_date_raw', ''),
                            source_row_id=row.get('source_row_id', ''),
                            source_extra=row.get('source_extra', {}),
                            emission_factor_value=row.get('emission_factor_value'),
                            emission_factor_unit=row.get('emission_factor_unit', ''),
                            emission_factor_source=row.get('emission_factor_source', ''),
                            is_suspicious=row.get('is_suspicious', False),
                            suspicion_reasons=row.get('suspicion_reasons', []),
                            status='pending_review',
                        )
                        if row.get('facility_id'):
                            record.facility_id = row['facility_id']
                        created_records.append(record)
                    except Exception as e:
                        error_rows.append({'error': str(e), 'raw': row})

                EmissionRecord.objects.bulk_create(created_records)

                batch.status = 'completed' if not error_rows else 'partial'
                batch.row_count_total = len(parsed_rows) + len(error_rows)
                batch.row_count_ok = len(created_records)
                batch.row_count_failed = len(error_rows)
                batch.row_count_suspicious = sum(1 for r in created_records if r.is_suspicious)
                batch.error_log = error_rows[:100]  # cap stored errors
                batch.save()

        except Exception as e:
            batch.status = 'failed'
            batch.error_log = [{'error': str(e), 'traceback': traceback.format_exc()}]
            batch.save()
            return Response({'error': str(e), 'batch_id': str(batch.id)}, status=500)

        return Response({
            'batch_id': str(batch.id),
            'status': batch.status,
            'rows_ingested': batch.row_count_ok,
            'rows_failed': batch.row_count_failed,
            'rows_suspicious': batch.row_count_suspicious,
        }, status=201)
