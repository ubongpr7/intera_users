from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from rest_framework import status, generics, permissions, viewsets, pagination
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView


from django_filters import rest_framework as filters

from mainapps.common.models import User
from mainapps.common.settings import get_company_or_profile
from mainapps.management.models import CompanyProfile
from mainapps.management.models_activity.activity_logger import log_user_activity
from mainapps.permit.permit import HasModelRequestPermission

from ..models import ActivityLog, StaffGroup, StaffRole, StaffRoleAssignment
from .serializers import (
    CompanyProfileSerializer, 
    CompanyAddressSerializer, 
    ActivityLogSerializer,
    StaffGroupSerializer,
    StaffRoleSerializer
)

User=get_user_model()
class CreateCompanyAddressView(APIView):
    permission_classes = [IsAuthenticated,]

    def post(self, request, *args, **kwargs):
        company_id = request.data.pop('company', None)
        try:
            company = get_company_or_profile(request.user)
        except :
            return Response(
                {"detail": "Company not found or you do not have permission to add an address for this company."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CompanyAddressSerializer(data=request.data)
        if serializer.is_valid():
            if  company:
                serializer.save()
                instance = serializer.instance
                company.headquarters_address = serializer.instance
                company.save()
                log_user_activity(
                    user=request.user,
                    action='CREATE',
                    instance=instance,
                    details={
                        'initial_data': request.data,
                        'created_data': serializer.data,
                        'ip_address': request.META.get('REMOTE_ADDR'),
                        'user_agent': request.META.get('HTTP_USER_AGENT')
                    },
                    async_log=True
                )


            else:
                return Response({'detail':'Company not found'},status=status.HTTP_404_NOT_FOUND)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CreateCompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        print(request.data)
        print(request.user.is_main)
        if not request.user.is_main:
            return Response(
                {"detail": "Only main users can create a company profile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # request.data['owner'] = request.user.id
        serializer = CompanyProfileSerializer(data=request.data)
        try:

            if serializer.is_valid():
                user= request.user
                serializer.save()
                company= serializer.instance
                company.owner = request.user
                company.save()
                user.profile=company
                user.save()
                log_user_activity(
                    user=request.user,
                    action='CREATE',
                    instance=company,
                    details={
                        'initial_data': request.data,
                        'created_data': serializer.data,
                        'ip_address': request.META.get('REMOTE_ADDR'),
                        'user_agent': request.META.get('HTTP_USER_AGENT')
                    },
                    async_log=True
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(e)
        print(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class OwnerCompanyProfileDetailView(generics.RetrieveAPIView):
    serializer_class = CompanyProfileSerializer
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]

    def get_object(self):
        print(self.request.user)
        return get_object_or_404(CompanyProfile, owner=self.request.user)



class CreateGroupView(APIView):
    permission_classes = [IsAuthenticated]
        
    def post(self, request, *args, **kwargs):
        
        if not request.user.is_main:
            return Response(
                {"detail": "Only main users can create a company profile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = StaffGroupSerializer(data=request.data)
        try:

            if serializer.is_valid():
                user= request.user
                serializer.save()
                group = serializer.instance
                group.profile = request.user.profile
                group.save()
                log_user_activity(
                    user=request.user,
                    action='CREATE',
                    instance=group,
                    details={
                        'initial_data': request.data,
                        'created_data': serializer.data,
                        'ip_address': request.META.get('REMOTE_ADDR'),
                        'user_agent': request.META.get('HTTP_USER_AGENT')
                    },
                    async_log=True
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(e)
        print(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

class GroupDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = StaffGroupSerializer
    queryset=StaffGroup.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    lookup_field= 'id'


class StaffGroupView(APIView):
    permission_classes=[IsAuthenticated,HasModelRequestPermission]
    def get(self,request):
        profile = self.request.user.profile
        groups= StaffGroup.objects.filter(
            profile=profile
        )
        serializer=StaffGroupSerializer(groups,many=True)
        return Response(serializer.data)
        

class CreateRoleView(APIView):
    permission_classes = [IsAuthenticated,HasModelRequestPermission]

    def post(self, request, *args, **kwargs):
        
        if not request.user.is_main:
            return Response(
                {"detail": "Only main users can create a company profile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = StaffRoleSerializer(data=request.data)
        try:

            if serializer.is_valid():
                user= request.user
                serializer.save()
                role = serializer.instance
                role.profile = request.user.profile
                role.save()
                log_user_activity(
                    user=request.user,
                    action='CREATE',
                    instance=role,
                    details={
                        'initial_data': request.data,
                        'created_data': serializer.data,
                        'ip_address': request.META.get('REMOTE_ADDR'),
                        'user_agent': request.META.get('HTTP_USER_AGENT')
                    },
                    async_log=True
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(e)
        print(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    
class StaffRoleView(APIView):
    permission_classes=[IsAuthenticated,HasModelRequestPermission]
    def get(self,request):
        profile = self.request.user.profile
        roles= StaffRole.objects.filter(
            profile=profile
        )
        serializer=StaffRoleSerializer(roles,many=True)
        return Response(serializer.data)
    
    


class RoleDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = StaffRoleSerializer
    queryset=StaffRole.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    lookup_field= 'id'



class UserActivityLogsAPIView(APIView):
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        logs = ActivityLog.objects.filter(user=user).select_related('user').order_by('-timestamp')
        serializer = ActivityLogSerializer(logs, many=True)
        return Response(serializer.data)

class RoleDeactivateView(APIView):
    permission_classes=[IsAuthenticated,HasModelRequestPermission]
    def post(self,request,role_id):
        role= get_object_or_404(StaffRoleAssignment,id=role_id).delete()
        return Response({'detail':'Role deleted successfully'},status=status.HTTP_200_OK)