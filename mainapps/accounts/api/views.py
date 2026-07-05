from django.contrib.auth import authenticate
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.generics import ListAPIView 
from django.db.models import Prefetch
from rest_framework_simplejwt.views import TokenObtainPairView
from mainapps.accounts.models import User,VerificationCode
from mainapps.common.settings import get_company_or_profile
from subapps.email_system.emails import send_html_email
from mainapps.profile.models import StaffRoleAssignment
from mainapps.permit.api.serializers import PermissionDetailSerializer
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from mainapps.permit.permit import HasModelRequestPermission
from rest_framework.throttling import AnonRateThrottle



@api_view(['GET'])
def ge_route(request):
    route=['/api/token','api/token/refresh']
    return Response(route,status=201)

class VerificationAPI(APIView):
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        """Handle both sending verification code and verifying code submission (POST)"""
        action = request.data.get('action')

        if action == 'send_code':
            return self.send_verification_code(request)
        elif action == 'verify_code':
            return self.verify_code(request)
        else:
            return Response(
                {"error": "Invalid action. Use 'send_code' or 'verify_code'."},
                status=status.HTTP_400_BAD_REQUEST
            )

    def send_verification_code(self, request):
        """Send verification code via email"""
        email = request.data.get('email')

        if not email:
            return Response(
                {"error": "Email parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = User.objects.filter(email=email).first()
        if user:
            code, _ = VerificationCode.objects.get_or_create(user=user)
            code.regenerate()
            send_html_email(
                subject=f'Your Verification Code: {code.code}',
                message=f'Use this code to verify your login: {code.code}',
                to_email=[user.email],
                html_file='accounts/verify.html'
            )

        return Response(
            {"message": "If the account exists, a verification code has been sent."},
            status=status.HTTP_200_OK
        )

    def verify_code(self, request):
        """Verify code submission"""
        email = request.data.get('email')
        code_input = request.data.get('code')
        
        if not email or not code_input:
            return Response(
                {"error": "Both email and code are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)

        verification_code = VerificationCode.objects.filter(user=user).first()
        if not verification_code or not verification_code.is_valid():
            return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)

        if str(verification_code.code) != code_input.strip():
            verification_code.mark_failed_attempt()
            return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)

        verification_code.mark_successful_attempt()
        verification_code.regenerate()
        return Response(
            {
                "message": "Verification successful",
                "user_id": user.id,
                "email": user.email
            },
            status=status.HTTP_200_OK
        )


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    

    def get(self, request, *args, **kwargs):
        """Return details of the logged-in user"""
        user = request.user
        serializer = MyUserSerializer(user)
        return Response(serializer.data)

class UserReadOnlyView(viewsets.ReadOnlyModelViewSet):
    serializer_class=MyUserSerializer
    queryset= User.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = "manage_company_settings"

    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()

        company = get_company_or_profile(self.request.user)
        if company:
            return User.objects.filter(profile=company)
        return User.objects.filter(id=self.request.user.id)

    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        if getattr(self, 'swagger_fake_view', False):
            return PermissionDetailSerializer
        user_perms=set()
        user = self.get_object()
        try:
            from django.utils import timezone
            current_time = timezone.now()
            for role in user.roles.all().iterator():
                if role.start_date and role.end_date:
                  
                    if role.end_date < current_time:
                        role.delete()
                    else:
                        perms = role.role.permissions.all().values_list('codename', flat=True)
                        user_perms.update(perms)
        except Exception as e:
            return Response({"error": "Unable to resolve role permissions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            groups=user.staff_groups.all()
            for group in groups:
                user_perms.update(group.permissions.all().values_list('codename', flat=True))
        except Exception:
            pass
        return Response(user_perms)    
    


class TokenGenerator(TokenObtainPairView):
    def post(self, request: Request, *args, **kwargs)  :
        email = request.data.get('email') or request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=email, password=password)
        if user is not None:
            response=super().post(request,*args,**kwargs)
            response.status_code=200
            return response
        else:
            return Response(status=400)

class UserProfileView(APIView):
    
    permission_classes=[permissions.IsAuthenticated]
    def get(self,request):
        serializer = MyUserSerializer(request.user)
        return Response(serializer.data, status=200)

from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken,OutstandingToken

def logout_user_everywhere(user):
    tokens= OutstandingToken.objects.filter(user=user)
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)

def logout_user_in_current_device(token):
    tokens= OutstandingToken.objects.filter(token=token)
    for token in tokens:
        obj,created=BlacklistedToken.objects.get_or_create(token=token)
    

class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            token=request.data.get('refresh')
            logout_user_in_current_device(token)
            return Response({"message": "Logged out successfully"}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        

class RootUserRegistrationAPIView(APIView):
    """
    Create new user with first name, email and password
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RootUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user =serializer.instance
            code, _ = VerificationCode.objects.get_or_create(user=user)
            code.regenerate()
            subject=f'Verification code: {code}. {user.first_name} {user.last_name}'
            message= code
            html_file='accounts/verify.html'
            to_email=user.email
            send_html_email(subject, message, [to_email],html_file)
            return Response({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StaffUserRegistrationAPIView(APIView):
    """
    Create new user with first name, email and password
    """
    # authentication_classes = []
    permission_classes = [IsAuthenticated,HasModelRequestPermission]
    required_permission = "manage_company_settings"

    def post(self, request):
        from mainapps.profile.views import _enforce_staff_limit
        company = get_company_or_profile(request.user)
        _enforce_staff_limit(company)
        serializer = StaffUserCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            user.profile=company
            user.save()
            code, _ = VerificationCode.objects.get_or_create(user=user)
            code.regenerate()
            subject=f'Verification code: {code}. {user.first_name}'
            message= f'Code: {code}'
            
            html_file='accounts/verify.html'
            to_email=user.email
            send_html_email(subject, message, [to_email],html_file)
            return Response({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StaffUsersView(ListAPIView):
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = "manage_company_settings"
    serializer_class = MyUserSerializer
    
    def get_queryset(self):
        company = get_company_or_profile(self.request.user)
        user= User.objects.filter(profile=company).prefetch_related(
            Prefetch(
                'roles',
                queryset=StaffRoleAssignment.objects.select_related('role'),
                to_attr='active_roles'
            )
        )
        return user
