#!/usr/bin/env python
"""
Seed the database with demo data.
Run after migrate: python seed.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathe_esg.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from emissions.models import Tenant, TenantMembership, FacilityLookup
from rest_framework.authtoken.models import Token

# Create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='acme-corp',
    defaults={'name': 'ACME Corporation'}
)

# Create demo analyst user
analyst, created = User.objects.get_or_create(
    username='analyst',
    defaults={
        'first_name': 'Alex',
        'last_name': 'Analyst',
        'email': 'analyst@acme.com',
        'is_staff': False,
    }
)
if created:
    analyst.set_password('demo1234')
    analyst.save()

Token.objects.get_or_create(user=analyst)
TenantMembership.objects.get_or_create(user=analyst, tenant=tenant, defaults={'role': 'analyst'})

# Create admin user
admin, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'first_name': 'Admin',
        'last_name': 'User',
        'email': 'admin@acme.com',
        'is_staff': True,
        'is_superuser': True,
    }
)
if created:
    admin.set_password('admin1234')
    admin.save()

Token.objects.get_or_create(user=admin)
TenantMembership.objects.get_or_create(user=admin, tenant=tenant, defaults={'role': 'admin'})

# Create facility lookups (SAP plant codes)
facilities = [
    {'sap_plant_code': 'P001', 'name': 'Chicago Manufacturing', 'country': 'US', 'grid_region': 'US-RFC'},
    {'sap_plant_code': 'P002', 'name': 'London HQ', 'country': 'GB', 'grid_region': 'UK'},
    {'sap_plant_code': 'P003', 'name': 'Munich Plant', 'country': 'DE', 'grid_region': 'EU'},
    {'sap_plant_code': 'P004', 'name': 'Singapore Office', 'country': 'SG', 'grid_region': 'DEFAULT'},
    {'sap_plant_code': 'WERK1', 'name': 'Hamburg Warehouse', 'country': 'DE', 'grid_region': 'EU'},
    {'sap_plant_code': 'WERK2', 'name': 'Amsterdam Distribution', 'country': 'NL', 'grid_region': 'EU'},
]

for f in facilities:
    FacilityLookup.objects.get_or_create(
        tenant=tenant,
        sap_plant_code=f['sap_plant_code'],
        defaults=f,
    )

print(f"""
=== Seed complete ===
Tenant: {tenant.name} (id={tenant.id})
Analyst login: analyst / demo1234
Admin login:   admin / admin1234
Facilities: {len(facilities)} created
""")
