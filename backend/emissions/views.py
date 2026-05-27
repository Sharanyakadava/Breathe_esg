from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from .models import EmissionRecord, IngestionBatch, Tenant, FacilityLookup
from .serializers import (
    EmissionRecordSerializer, EmissionRecordUpdateSerializer,
    IngestionBatchSerializer, TenantSerializer, FacilityLookupSerializer
)


class TenantMixin:
    """Scopes all querysets to the user's active tenant."""

    def get_tenant(self):
        tenant_id = self.request.query_params.get('tenant') or self.request.data.get('tenant')
        if tenant_id:
            return Tenant.objects.get(id=tenant_id, memberships__user=self.request.user)
        membership = self.request.user.memberships.select_related('tenant').first()
        if membership:
            return membership.tenant
        return None


class EmissionRecordViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['scope', 'category', 'status', 'is_suspicious', 'batch']
    search_fields = ['description', 'source_row_id']
    ordering_fields = ['period_start', 'quantity_kg_co2e', 'created_at']
    ordering = ['-period_start']

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return EmissionRecord.objects.none()
        return EmissionRecord.objects.filter(tenant=tenant).select_related(
            'facility', 'batch', 'reviewed_by'
        ).prefetch_related('edits')

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update', 'review'):
            return EmissionRecordUpdateSerializer
        return EmissionRecordSerializer

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        record = self.get_object()
        if record.status == 'locked':
            return Response({'error': 'Record is locked for audit.'}, status=400)
        serializer = EmissionRecordUpdateSerializer(
            record, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        ids = request.data.get('ids', [])
        tenant = self.get_tenant()
        records = EmissionRecord.objects.filter(
            id__in=ids, tenant=tenant, status='pending_review'
        )
        count = records.count()
        records.update(
            status='approved',
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        return Response({'approved': count})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        tenant = self.get_tenant()
        if not tenant:
            return Response({})
        qs = EmissionRecord.objects.filter(tenant=tenant)
        from django.db.models import Sum, Count
        total = qs.aggregate(
            total_kg=Sum('quantity_kg_co2e'),
            count=Count('id'),
        )
        by_scope = list(qs.values('scope').annotate(total_kg=Sum('quantity_kg_co2e'), count=Count('id')))
        by_status = list(qs.values('status').annotate(count=Count('id')))
        by_category = list(qs.values('category').annotate(total_kg=Sum('quantity_kg_co2e'), count=Count('id')))
        return Response({
            'total': total,
            'by_scope': by_scope,
            'by_status': by_status,
            'by_category': by_category,
        })


class IngestionBatchViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = IngestionBatchSerializer

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return IngestionBatch.objects.none()
        return IngestionBatch.objects.filter(tenant=tenant).order_by('-uploaded_at')


class FacilityViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FacilityLookupSerializer

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return FacilityLookup.objects.none()
        return FacilityLookup.objects.filter(tenant=tenant)
