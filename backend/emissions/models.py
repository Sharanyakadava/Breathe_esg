from django.db import models
from django.contrib.auth.models import User
import uuid


class Tenant(models.Model):
    """
    Multi-tenancy root. Every piece of data belongs to a tenant (client company).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TenantMembership(models.Model):
    ROLE_CHOICES = [
        ('analyst', 'Analyst'),
        ('admin', 'Admin'),
        ('auditor', 'Auditor'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='analyst')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'tenant')


class FacilityLookup(models.Model):
    """
    SAP plant/cost center codes mapped to real-world locations.
    SAP exports use internal codes; this table resolves them.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='facilities')
    sap_plant_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=2)  # ISO 3166-1 alpha-2
    region = models.CharField(max_length=100, blank=True)
    grid_region = models.CharField(max_length=100, blank=True, help_text="For electricity emission factors")

    class Meta:
        unique_together = ('tenant', 'sap_plant_code')

    def __str__(self):
        return f"{self.sap_plant_code} → {self.name}"


class IngestionBatch(models.Model):
    """
    One upload/pull event. Tracks provenance: who ingested what, when, from where.
    """
    SOURCE_CHOICES = [
        ('sap_flat_file', 'SAP Flat File (IDoc/IDOC)'),
        ('utility_csv', 'Utility Portal CSV'),
        ('travel_csv', 'Corporate Travel CSV'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial (some rows failed)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploads')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    source_file_name = models.CharField(max_length=500, blank=True)
    source_file = models.FileField(upload_to='ingestion/%Y/%m/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    row_count_total = models.IntegerField(default=0)
    row_count_ok = models.IntegerField(default=0)
    row_count_failed = models.IntegerField(default=0)
    row_count_suspicious = models.IntegerField(default=0)
    error_log = models.JSONField(default=list, blank=True)
    processing_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.source_type} | {self.tenant.slug} | {self.uploaded_at:%Y-%m-%d %H:%M}"


class EmissionRecord(models.Model):
    """
    Normalized emission record. This is the source of truth row that goes to auditors.

    Design decisions:
    - quantity_kg_co2e is always in kg CO2e — all unit conversion happens at ingestion time
    - scope is always set, never null
    - source_of_truth_* fields preserve the raw original values before normalization
    - edit history is tracked via EmissionRecordEdit
    """
    SCOPE_CHOICES = [
        ('scope1', 'Scope 1 - Direct'),
        ('scope2_lb', 'Scope 2 - Location-Based'),
        ('scope2_mb', 'Scope 2 - Market-Based'),
        ('scope3', 'Scope 3 - Value Chain'),
    ]
    CATEGORY_CHOICES = [
        # Scope 1
        ('fuel_stationary', 'Stationary Combustion (Fuel)'),
        ('fuel_mobile', 'Mobile Combustion (Fuel)'),
        # Scope 2
        ('electricity', 'Purchased Electricity'),
        # Scope 3
        ('business_travel_air', 'Business Travel - Air'),
        ('business_travel_hotel', 'Business Travel - Hotel'),
        ('business_travel_ground', 'Business Travel - Ground Transport'),
        ('procurement', 'Procurement / Purchased Goods'),
    ]
    STATUS_CHOICES = [
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('locked', 'Locked for Audit'),
        ('flagged', 'Flagged - Needs Attention'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='records')

    # Classification
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)

    # Normalized values (always kg CO2e, always UTC period)
    quantity_kg_co2e = models.DecimalField(max_digits=18, decimal_places=4)
    period_start = models.DateField()
    period_end = models.DateField()
    facility = models.ForeignKey(
        FacilityLookup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='emission_records'
    )
    description = models.CharField(max_length=500, blank=True)

    # Source of truth — raw values before normalization
    source_quantity = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    source_unit = models.CharField(max_length=50, blank=True)
    source_date_raw = models.CharField(max_length=100, blank=True, help_text="Original date string from source")
    source_row_id = models.CharField(max_length=200, blank=True, help_text="Row identifier in source file")
    source_extra = models.JSONField(default=dict, blank=True, help_text="Additional fields from source not mapped to schema")

    # Emission factor used
    emission_factor_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    emission_factor_unit = models.CharField(max_length=100, blank=True)
    emission_factor_source = models.CharField(max_length=200, blank=True, help_text="e.g. DEFRA 2023, EPA eGRID 2022")

    # Review workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    is_suspicious = models.BooleanField(default=False)
    suspicion_reasons = models.JSONField(default=list, blank=True)

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    class Meta:
        ordering = ['-period_start', 'category']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'scope', 'period_start']),
            models.Index(fields=['batch']),
        ]

    def __str__(self):
        return f"{self.category} | {self.quantity_kg_co2e} kgCO2e | {self.period_start}"


class EmissionRecordEdit(models.Model):
    """
    Immutable log of every change to an EmissionRecord.
    Supports full audit trail: what was changed, by whom, when, and why.
    """
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='edits')
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    edited_at = models.DateTimeField(auto_now_add=True)
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-edited_at']
