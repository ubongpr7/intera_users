from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import FileUploadParser
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.generics import ListAPIView 
from django.db.models import Prefetch
from rest_framework_simplejwt.views import TokenObtainPairView
from mainapps.accounts.models import User,VerificationCode
from mainapps.accounts.views import send_html_email
from mainapps.common.settings import get_company_or_profile
from mainapps.management.models import StaffRoleAssignment
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from mainapps.permit.permit import HasModelRequestPermission



class UploadProfileView(APIView):
    parser_classes=[FileUploadParser]
    def post(self, request ):
        user=request.user
        print(user)
        picture=request.data["file"]
        print(request.data["file"])
        user.picture=picture
        user.save()
        #serializer=UserPictureSerializer(picture,data=request.data)
        if user.picture==picture:
            print("saved")
            return Response("Profile picture updated Successfully",status=200)
        else:
            return Response("Error uploading picture!",status=400)

@api_view(['GET'])
def ge_route(request):
    route=['/api/token','api/token/refresh']
    return Response(route,status=201)

class VerificationAPI(APIView):
    def get(self, request):
        pk = request.query_params.get('id')
        
        if not pk:
            return Response({"error": "User ID required"}, status=status.HTTP_400_BAD_REQUEST)

        try:

            user = User.objects.get(pk=pk)
            code = VerificationCode.objects.get(slug=user.email)
            
            
            code.total_attempts += 1
            code.save()
            
            send_html_email(
                subject=f'Verification code: {code}',
                message=str(code),
                to_email=[user.email],
                html_file='accounts/verify.html'
            )
            
            return Response("Confirmation code has been resent", status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except VerificationCode.DoesNotExist:
            return Response({"error": "Verification code not found"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        pk = request.data.get('userId')
        print(pk)
        code_input = request.data.get('code')
        print(code_input)
        if not pk or not code_input:
            return Response(
                {"error": "Both user ID and code are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(pk=pk)
            verification_code = VerificationCode.objects.get(slug=user.email)
            
            if str(verification_code) == str(code_input):
                verification_code.total_attempts=0
                verification_code.save() 
                user.is_verified = True
                user.save()
                
                return Response(
                    {"message": "Authentication Successful"},
                    status=status.HTTP_200_OK
                )
                
            return Response(
                {"error": "Invalid verification code"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except VerificationCode.DoesNotExist:
            return Response({"error": "Verification code not found"}, status=status.HTTP_404_NOT_FOUND)

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    

    def get(self, request, *args, **kwargs):
        """Return details of the logged-in user"""
        user = request.user
        serializer = MyUserSerializer(user)
        return Response(serializer.data)

class TokenGenerator(TokenObtainPairView):
    def post(self, request: Request, *args, **kwargs)  :
        username=request.data.get('username')
        password=request.data.get('password')
        user=authenticate(username=username,password=password)
        if user is not None:
            response=super().post(request,*args,**kwargs)
            response.status_code=200
            return response
        else:
            return Response(status=400)

class UserProfileView(APIView):
    
    permission_classes=[permissions.IsAuthenticated]
    def get(self,request):
        serializer=MyUserSerializer
        email=request.COOKIES.get('email')
        user=User.objects.get(username=email)
        return Response({'user':user},status=200)

class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # request.user.auth_token.delete()
            token=request.data.get('refresh')
            print('refresh_token',token)
            token = RefreshToken(token)

            token.blacklist()  # Add to blacklist
            return Response({"message": "Logged out successfully"}, status=200)
        except Exception as e:
            print(e)
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
            code=VerificationCode.objects.get(slug=user.email)
            print(f'this is the code: {code}')
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

    def post(self, request):
        print(request.data)

        serializer = StaffUserCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            company=get_company_or_profile(request.user)
            user.profile=company
            user.save()
            password = serializer.validated_data.get('password')  # Get from validated data
                
            code=VerificationCode.objects.get(slug=user.email)
            print(f'this is the code: {code}')
            subject=f'Verification code: {code}. {user.first_name}'
            message= f'Code: {code}, Password: {password}'
            
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
        print(user)
        return user


