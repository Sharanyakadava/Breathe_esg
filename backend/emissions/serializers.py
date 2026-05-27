from rest_framework import serializers
from .models import EmissionRecord, IngestionBatch, Tenant, FacilityLookup, EmissionRecordEdit


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug', 'created_at']


class FacilityLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityLookup
        fields = ['id', 'sap_plant_code', 'name', 'country', 'region', 'grid_region']


class EmissionRecordEditSerializer(serializers.ModelSerializer):
    edited_by_name = serializers.CharField(source='edited_by.get_full_name', read_only=True)

    class Meta:
        model = EmissionRecordEdit
        fields = ['id', 'edited_by_name', 'edited_at', 'field_name', 'old_value', 'new_value', 'reason']


class EmissionRecordSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    batch_source = serializers.CharField(source='batch.source_type', read_only=True)
    edits = EmissionRecordEditSerializer(many=True, read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'category', 'quantity_kg_co2e',
            'period_start', 'period_end', 'facility', 'facility_name',
            'description', 'source_quantity', 'source_unit',
            'source_date_raw', 'source_row_id', 'source_extra',
            'emission_factor_value', 'emission_factor_unit', 'emission_factor_source',
            'status', 'reviewed_by', 'reviewed_at', 'review_notes',
            'is_suspicious', 'suspicion_reasons',
            'created_at', 'updated_at', 'is_edited',
            'batch', 'batch_source', 'edits',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'batch', 'is_edited']


class EmissionRecordUpdateSerializer(serializers.ModelSerializer):
    """Used for analyst review actions."""
    reason = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = EmissionRecord
        fields = ['status', 'review_notes', 'quantity_kg_co2e', 'reason']

    def update(self, instance, validated_data):
        reason = validated_data.pop('reason', '')
        user = self.context['request'].user
        from django.utils import timezone

        for field, new_value in validated_data.items():
            old_value = getattr(instance, field)
            if str(old_value) != str(new_value):
                EmissionRecordEdit.objects.create(
                    record=instance,
                    edited_by=user,
                    field_name=field,
                    old_value=str(old_value),
                    new_value=str(new_value),
                    reason=reason,
                )
                setattr(instance, field, new_value)
                instance.is_edited = True

        if validated_data.get('status') in ('approved', 'rejected'):
            instance.reviewed_by = user
            instance.reviewed_at = timezone.now()

        instance.save()
        return instance


class IngestionBatchSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'source_type', 'source_type_display', 'uploaded_by', 'uploaded_by_name',
            'uploaded_at', 'source_file_name', 'status',
            'row_count_total', 'row_count_ok', 'row_count_failed', 'row_count_suspicious',
            'error_log', 'processing_notes',
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']
