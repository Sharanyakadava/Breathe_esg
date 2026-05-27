from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils.text import slugify
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from emissions.models import Tenant, TenantMembership
class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Invalid credentials'}, status=401)
        token, _ = Token.objects.get_or_create(user=user)
        memberships = TenantMembership.objects.filter(user=user).select_related('tenant')
        tenants = [
            {'id': str(m.tenant.id), 'name': m.tenant.name, 'slug': m.tenant.slug, 'role': m.role}
            for m in memberships
        ]
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name(),
                'email': user.email,
            },
            'tenants': tenants,
        })
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        memberships = TenantMembership.objects.filter(user=request.user).select_related('tenant')
        tenants = [
            {'id': str(m.tenant.id), 'name': m.tenant.name, 'slug': m.tenant.slug, 'role': m.role}
            for m in memberships
        ]
        return Response({
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'full_name': request.user.get_full_name(),
                'email': request.user.email,
            },
            'tenants': tenants,
        })
class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email', '')
        full_name = request.data.get('full_name', '')
        company_name = request.data.get('company_name', 'My Organization')
        if not username or not password:
            return Response({'error': 'Username and password are required'}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists'}, status=400)
        first_name = ''
        last_name = ''
        if full_name:
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        base_slug = slugify(company_name) or 'tenant'
        slug = base_slug
        counter = 1
        while Tenant.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        tenant = Tenant.objects.create(
            name=company_name,
            slug=slug
        )
        TenantMembership.objects.create(
            user=user,
            tenant=tenant,
            role='admin'
        )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name(),
                'email': user.email,
            },
            'tenants': [
                {'id': str(tenant.id), 'name': tenant.name, 'slug': tenant.slug, 'role': 'admin'}
            ],
        }, status=201)
