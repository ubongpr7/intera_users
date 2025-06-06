# permissions/views.py
from rest_framework import permissions, status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Exists, OuterRef

from mainapps.management.models import StaffGroup,StaffRole, StaffRoleAssignment
from mainapps.permit.permit import HasModelRequestPermission

from .serializers import (PermissionDetailSerializer, RoleAssignmentSerializer,
    RolePermissionUpdateSerializer, 
    UserPermissionUpdateSerializer,
    GroupPermissionUpdateSerializer,
    UserGroupUpdateSerializer,
    GroupDetailSerializer
    )
from mainapps.accounts.models import User  
from mainapps.permit.models import CustomUserPermission
from rest_framework.viewsets import ModelViewSet

class UserPermissionManager(RetrieveUpdateAPIView):
    queryset = User.objects.all() 
    permission_classes = [permissions.IsAuthenticated,HasModelRequestPermission]

    def get_serializer_class(self):
        user = self.get_object()

        if user.profile != self.request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if self.request.method == 'GET':
            return PermissionDetailSerializer
        return UserPermissionUpdateSerializer

    def get(self, request, *args, **kwargs):
        """Get all permissions with current user's access status"""
        if getattr(self, 'swagger_fake_view', False):
            return PermissionDetailSerializer

        user = self.get_object()
        if user.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        permissions = CustomUserPermission.objects.annotate(
            has_permission=Exists(
                User.custom_permissions.through.objects.filter(
                    user_id=user.id,  
                    customuserpermission_id=OuterRef('id')
                )
            )
        ).select_related('category')
        serializer = self.get_serializer(permissions, many=True)
        return Response({'permissions': serializer.data})

    def put(self, request, *args, **kwargs):

        """Update user permissions with complete list"""
        user = self.get_object()
        
        if user.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validate all permission codenames exist
        codenames = serializer.validated_data['permissions']
        valid_perms = CustomUserPermission.objects.filter(codename__in=codenames)
        
        # Check for invalid permissions
        received_perms = set(codenames)
        valid_codenames = set(valid_perms.values_list('codename', flat=True))
        if invalid := received_perms - valid_codenames:
            return Response(
                {"detail": f"Invalid permissions: {', '.join(invalid)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Atomic permission update
        with transaction.atomic():
            user.custom_permissions.set(valid_perms)
        
        return Response({'status': 'permissions updated'}, status=status.HTTP_200_OK)
    
    
class GroupPermissionManager(RetrieveUpdateAPIView):
    queryset = StaffGroup.objects.all() 
    permission_classes = [permissions.IsAuthenticated,HasModelRequestPermission]

    def get_serializer_class(self):
        if getattr(self, 'swagger_fake_view', False):
            return PermissionDetailSerializer
        group = self.get_object()

        if group.profile != self.request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if self.request.method == 'GET':
            return PermissionDetailSerializer
        return GroupPermissionUpdateSerializer

    def get(self, request, *args, **kwargs):
        """Get all permissions with current groups's access status"""
        group = self.get_object()
        if group.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        permissions = CustomUserPermission.objects.annotate(
            has_permission=Exists(
                StaffGroup.permissions.through.objects.filter(
                    staffgroup_id=group.id,  
                    customuserpermission_id=OuterRef('id')
                )
            )
        ).select_related('category')
        serializer = self.get_serializer(permissions, many=True)
        return Response({'permissions': serializer.data})

    def put(self, request, *args, **kwargs):

        """Update group permissions with complete list"""
        group = self.get_object()
        
        if group.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validate all permission codenames exist
        codenames = serializer.validated_data['permissions']
        valid_perms = CustomUserPermission.objects.filter(codename__in=codenames)
        
        # Check for invalid permissions
        received_perms = set(codenames)
        valid_codenames = set(valid_perms.values_list('codename', flat=True))
        if invalid := received_perms - valid_codenames:
            return Response(
                {"detail": f"Invalid permissions: {', '.join(invalid)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            group.permissions.set(valid_perms)
        
        return Response({'status': 'permissions updated'}, status=status.HTTP_200_OK)
    
class RolePermissionManager(RetrieveUpdateAPIView):
    queryset = StaffRole.objects.all() 
    permission_classes = [permissions.IsAuthenticated,HasModelRequestPermission]

    def get_serializer_class(self):
        if getattr(self, 'swagger_fake_view', False):
            return PermissionDetailSerializer
        role = self.get_object()

        if role.profile != self.request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if self.request.method == 'GET':
            return PermissionDetailSerializer
        return RolePermissionUpdateSerializer

    def get(self, request, *args, **kwargs):
        """Get all permissions with current role's access status"""
        role = self.get_object()
        if role.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        permissions = CustomUserPermission.objects.annotate(
            has_permission=Exists(
                StaffRole.permissions.through.objects.filter(
                    staffrole_id=role.id,  
                    customuserpermission_id=OuterRef('id')
                )
            )
        ).select_related('category')
        serializer = self.get_serializer(permissions, many=True)
        return Response({'permissions': serializer.data})

    def put(self, request, *args, **kwargs):

        """Update group permissions with complete list"""
        role = self.get_object()
        
        if role.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validate all permission codenames exist
        codenames = serializer.validated_data['permissions']
        valid_perms = CustomUserPermission.objects.filter(codename__in=codenames)
        
        # Check for invalid permissions
        received_perms = set(codenames)
        valid_codenames = set(valid_perms.values_list('codename', flat=True))
        if invalid := received_perms - valid_codenames:
            return Response(
                {"detail": f"Invalid permissions: {', '.join(invalid)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            role.permissions.set(valid_perms)
        
        return Response({'status': 'permissions updated'}, status=status.HTTP_200_OK)
    




class UserGroupManager(RetrieveUpdateAPIView):
    queryset = User.objects.all() 
    permission_classes = [permissions.IsAuthenticated,HasModelRequestPermission]

    def get_serializer_class(self):
        user = self.get_object()

        if user.profile != self.request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if self.request.method == 'GET':
            return GroupDetailSerializer
        return UserGroupUpdateSerializer

    def get(self, request, *args, **kwargs):
        """Get all permissions with current user's access status"""
        if getattr(self, 'swagger_fake_view', False):
            return GroupDetailSerializer

        user = self.get_object()
        if user.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        groups = StaffGroup.objects.annotate(
            belongs_to=Exists(
                User.staff_groups.through.objects.filter(
                    user_id=user.id,  
                    staffgroup_id=OuterRef('id')
                )
            )
        )
        serializer = self.get_serializer(groups, many=True)
        print(serializer.data)
        return Response({'groups': serializer.data})

    def put(self, request, *args, **kwargs):

        """Update user permissions with complete list"""
        user = self.get_object()
        
        if user.profile != request.user.profile:
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validate all permission codenames exist
        ids = serializer.validated_data['groups']
        valid_groups = StaffGroup.objects.filter(id__in=ids)
        with transaction.atomic():
    
            user.staff_groups.set(valid_groups)
        return Response({'status': 'permissions updated'}, status=status.HTTP_200_OK)
    
class RoleAssignmentManager(ModelViewSet):
    queryset = StaffRoleAssignment.objects.all() 
    permission_classes = [permissions.IsAuthenticated,HasModelRequestPermission]
    serializer_class = RoleAssignmentSerializer
