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
    APIStaffGroupSerializer,
    APIStaffRoleSerializer
)


User=get_user_model()


class CreateGroupView(APIView):
    permission_classes = [IsAuthenticated]
        
    def post(self, request, *args, **kwargs):
        
        if not request.user.is_main:
            return Response(
                {"detail": "Only main users can create a company profile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = APIStaffGroupSerializer(data=request.data)
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
    serializer_class = APIStaffGroupSerializer
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
        serializer=APIStaffGroupSerializer(groups,many=True)
        return Response(serializer.data)
        

class CreateRoleView(APIView):
    permission_classes = [IsAuthenticated,HasModelRequestPermission]

    def post(self, request, *args, **kwargs):
        
        if not request.user.is_main:
            return Response(
                {"detail": "Only main users can create a company profile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = APIStaffRoleSerializer(data=request.data)
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
        serializer=APIStaffRoleSerializer(roles,many=True)
        return Response(serializer.data)
    
    


class RoleDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = APIStaffRoleSerializer
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
