from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta

from mainapps.permit.permit import HasModelRequestPermission
from .serializers import (
    CompanyProfileListSerializer, CompanyProfileDetailSerializer,
    StaffRoleSerializer, StaffRoleListSerializer,
    StaffAssignmentSerializer, AddStaffSerializer,  
    StaffGroupSerializer, StaffGroupListSerializer,
    CompanyProfileAddressSerializer,
    ActivityLogSerializer,
    RecallPolicySerializer, ReorderStrategySerializer, InventoryPolicySerializer
)
from .models import (
    CompanyProfile, Address, CompanyProfileAddress, StaffGroup, StaffRole, StaffRoleAssignment,
    ActivityLog, RecallPolicy, ReorderStrategy, InventoryPolicy
)

class CompanyProfileViewSet( viewsets.ModelViewSet):
    """Enhanced ViewSet for company profile management"""
    queryset = CompanyProfile.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        'list': 'read_company_profile',
        'retrieve': 'read_company_profile',
        'create': 'create_company_profile',
        'update': 'update_company_profile',
        'partial_update': 'update_company_profile',
        'destroy': 'delete_company_profile',
    }
    
    filterset_fields = ['is_verified', 'industry']
    search_fields = ['name', 'description', 'tax_id']
    ordering_fields = ['name', 'created_at', 'employees_count']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
    
        return CompanyProfileDetailSerializer
    
    # def get_queryset(self):
    #     """Filter by user's accessible profiles"""
    #     # queryset = super().get_queryset()
    #     return self.request.user.profile
    
    def perform_create(self, serializer):
        """Set owner on creation"""
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['get'])
    def staff(self, request, pk=None):
        """Get all staff members for this profile"""
        profile = self.get_object()
        
        # Get all users with active role assignments
        staff_assignments = StaffRoleAssignment.objects.filter(
            profile=profile,
            is_active=True,
            start_date__lte=timezone.now()
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        ).select_related('user', 'role')
        
        serializer = StaffAssignmentSerializer(staff_assignments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_staff(self, request, pk=None):
        """Add staff member to profile"""
        profile = self.get_object()
        
        serializer = AddStaffSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create role assignment
            assignment = StaffRoleAssignment.objects.create(
                user_id=serializer.validated_data['user_id'],
                role_id=serializer.validated_data['role_id'],
                profile=profile,
                start_date=serializer.validated_data.get('start_date', timezone.now()),
                end_date=serializer.validated_data.get('end_date'),
                assigned_by=request.user
            )
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='ADD_STAFF',
                model_name='CompanyProfile',
                object_id=str(profile.id),
                details={
                    'staff_user_id': serializer.validated_data['user_id'],
                    'role_id': serializer.validated_data['role_id'],
                    'assignment_id': str(assignment.id)
                }
            )
            
            return Response(
                StaffAssignmentSerializer(assignment).data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def remove_staff(self, request, pk=None):
        """Remove staff member from profile"""
        profile = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Deactivate role assignments
            assignments = StaffRoleAssignment.objects.filter(
                profile=profile,
                user_id=user_id,
                is_active=True
            )
            
            if not assignments.exists():
                return Response(
                    {'error': 'User is not a staff member of this profile'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            assignments.update(
                is_active=False,
                end_date=timezone.now()
            )
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='REMOVE_STAFF',
                model_name='CompanyProfile',
                object_id=str(profile.id),
                details={
                    'staff_user_id': user_id,
                    'assignments_count': assignments.count()
                }
            )
            
            return Response({'message': 'Staff member removed successfully'})
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def roles(self, request, pk=None):
        """Get all roles for this profile"""
        profile = self.get_object()
        roles = profile.staff_roles.all()
        serializer = StaffRoleSerializer(roles, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def groups(self, request, pk=None):
        """Get all groups for this profile"""
        profile = self.get_object()
        groups = profile.staff_groups.all()
        serializer = StaffGroupSerializer(groups, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def addresses(self, request, pk=None):
        """Get all addresses for this profile"""
        profile = self.get_object()
        addresses = profile.addresses.all()
        serializer = CompanyProfileAddressSerializer(addresses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_address(self, request, pk=None):
        """Add address to profile"""
        profile = self.get_object()
        
        serializer = CompanyProfileAddressSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        address = serializer.save(profile=profile)
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            action='ADD_ADDRESS',
            model_name='CompanyProfile',
            object_id=str(profile.id),
            details={
                'address_id': str(address.id),
                'address_type': address.address_type
            }
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def policies(self, request, pk=None):
        """Get all policies for this profile"""
        profile = self.get_object()
        
        policies = {
            'recall_policies': RecallPolicySerializer(profile.recall_policies.all(), many=True).data,
            'reorder_strategies': ReorderStrategySerializer(profile.reorder_strategies.all(), many=True).data,
            'inventory_policies': InventoryPolicySerializer(profile.inventory_policies.all(), many=True).data,
        }
        
        return Response(policies)
    
    @action(detail=True, methods=['get'])
    def activity_logs(self, request, pk=None):
        """Get activity logs for this profile"""
        profile = self.get_object()
        
        # Filter logs related to this profile
        logs = ActivityLog.objects.filter(
            Q(model_name='CompanyProfile', object_id=str(profile.id)) |
            Q(details__profile_id=str(profile.id))
        ).order_by('-timestamp')
        
        # Apply filters
        action_filter = request.query_params.get('action')
        if action_filter:
            logs = logs.filter(action=action_filter)
        
        user_filter = request.query_params.get('user_id')
        if user_filter:
            logs = logs.filter(user_id=user_filter)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            logs = logs.filter(timestamp__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            logs = logs.filter(timestamp__lte=date_to)
        
        # Paginate
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = ActivityLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ActivityLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get analytics for this profile"""
        profile = self.get_object()
        
        # Staff analytics
        total_staff = StaffRoleAssignment.objects.filter(
            profile=profile,
            is_active=True
        ).count()
        
        active_roles = profile.staff_roles.filter(is_active=True).count()
        active_groups = profile.staff_groups.filter(is_active=True).count()
        
        # Recent activity
        recent_activity_count = ActivityLog.objects.filter(
            Q(model_name='CompanyProfile', object_id=str(profile.id)) |
            Q(details__profile_id=str(profile.id)),
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Policy analytics
        total_policies = (
            profile.recall_policies.count() +
            profile.reorder_strategies.count() +
            profile.inventory_policies.count()
        )
        
        analytics = {
            'total_staff': total_staff,
            'active_roles': active_roles,
            'active_groups': active_groups,
            'total_addresses': profile.addresses.count(),
            'total_policies': total_policies,
            'recent_activity_count': recent_activity_count,
            'verification_status': profile.is_verified,
            'profile_age_days': (timezone.now().date() - profile.created_at.date()).days,
        }
        
        return Response(analytics)

class StaffRoleViewSet( viewsets.ModelViewSet):
    """ViewSet for staff role management"""
    queryset = StaffRole.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        'list': 'read_staff_role',
        'retrieve': 'read_staff_role',
        'create': 'create_staff_role',
        'update': 'update_staff_role',
        'partial_update': 'update_staff_role',
        'destroy': 'delete_staff_role',
    }
    
    filterset_fields = ['is_active', 'profile']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return StaffRoleListSerializer
        return StaffRoleSerializer
    
    def get_queryset(self):
        """Filter by profile"""
        queryset = super().get_queryset()
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
        return queryset
    
    def perform_create(self, serializer):
        """Set profile on creation"""
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            serializer.save(profile_id=profile_id, created_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def assignments(self, request, pk=None):
        """Get all assignments for this role"""
        role = self.get_object()
        assignments = role.assignments.filter(is_active=True)
        serializer = StaffAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def assign_user(self, request, pk=None):
        """Assign user to this role"""
        role = self.get_object()
        
        serializer = AssignUserToRoleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            assignment = StaffRoleAssignment.objects.create(
                user_id=serializer.validated_data['user_id'],
                role=role,
                profile=role.profile,
                start_date=serializer.validated_data.get('start_date', timezone.now()),
                end_date=serializer.validated_data.get('end_date'),
                assigned_by=request.user
            )
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='ASSIGN_ROLE',
                model_name='StaffRole',
                object_id=str(role.id),
                details={
                    'user_id': serializer.validated_data['user_id'],
                    'assignment_id': str(assignment.id),
                    'profile_id': str(role.profile.id)
                }
            )
            
            return Response(
                StaffAssignmentSerializer(assignment).data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class StaffGroupViewSet( viewsets.ModelViewSet):
    """ViewSet for staff group management"""
    queryset = StaffGroup.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        'list': 'read_staff_group',
        'retrieve': 'read_staff_group',
        'create': 'create_staff_group',
        'update': 'update_staff_group',
        'partial_update': 'update_staff_group',
        'destroy': 'delete_staff_group',
    }
    
    filterset_fields = ['is_active', 'profile']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return StaffGroupListSerializer
        return StaffGroupSerializer
    
    def get_queryset(self):
        """Filter by profile"""
        queryset = super().get_queryset()
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
        return queryset
    
    def perform_create(self, serializer):
        """Set profile on creation"""
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            serializer.save(profile_id=profile_id, created_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in this group"""
        group = self.get_object()
        users = group.users.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_user(self, request, pk=None):
        """Add user to this group"""
        group = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            group.users.add(user)
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='ADD_USER_TO_GROUP',
                model_name='StaffGroup',
                object_id=str(group.id),
                details={
                    'user_id': user_id,
                    'profile_id': str(group.profile.id)
                }
            )
            
            return Response({'message': 'User added to group successfully'})
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def remove_user(self, request, pk=None):
        """Remove user from this group"""
        group = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            group.users.remove(user)
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='REMOVE_USER_FROM_GROUP',
                model_name='StaffGroup',
                object_id=str(group.id),
                details={
                    'user_id': user_id,
                    'profile_id': str(group.profile.id)
                }
            )
            
            return Response({'message': 'User removed from group successfully'})
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class CompanyProfileAddressViewSet( viewsets.ModelViewSet):
    """ViewSet for address management"""
    queryset = CompanyProfileAddress.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        'list': 'read_address',
        'retrieve': 'read_address',
        'create': 'create_address',
        'update': 'update_address',
        'partial_update': 'update_address',
        'destroy': 'delete_address',
    }
    
    filterset_fields = ['address_type', 'profile']
    search_fields = ['street', 'city__name', 'region__name']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    serializer_class = CompanyProfileAddressSerializer
    
    def get_queryset(self):
        """Filter by profile"""
        queryset = super().get_queryset()
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
        return queryset
    
    def perform_create(self, serializer):
        """Set profile on creation"""
        # profile_id = self.request.headers.get('X-Profile-ID')
        # if profile_id:
        serializer.save()
        address=serializer.instance
        profile=self.request.user.profile
        profile.headquarters_address=address
        profile.save()

        

class ActivityLogViewSet( viewsets.ReadOnlyModelViewSet):
    """ViewSet for activity log viewing"""
    queryset = ActivityLog.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = 'read_activity_log'
    
    filterset_fields = ['action', 'model_name', 'user']
    search_fields = ['action', 'model_name']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
    
    serializer_class = ActivityLogSerializer
    
    def get_queryset(self):
        """Filter by profile if provided"""
        queryset = super().get_queryset()
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            queryset = queryset.filter(
                Q(model_name='CompanyProfile', object_id=profile_id) |
                Q(details__profile_id=profile_id)
            )
        return queryset




























from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend


class RecallPolicyViewSet( viewsets.ModelViewSet):
    """ViewSet for recall policy management"""
    queryset = RecallPolicy.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        'list': 'read_recall_policy',
        'retrieve': 'read_recall_policy',
        'create': 'create_recall_policy',
        'update': 'update_recall_policy',
        'partial_update': 'update_recall_policy',
        'destroy': 'delete_recall_policy',
    }
    
    filterset_fields = ['is_active', 'profile']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    serializer_class = RecallPolicySerializer
    
    def get_queryset(self):
        """Filter by profile"""
        queryset = super().get_queryset()
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
        return queryset
    
    def perform_create(self, serializer):
        """Set profile and created_by on creation"""
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            serializer.save(
                profile_id=profile_id,
                created_by=self.request.user
            )
        else:
            serializer.save(created_by=self.request.user)

class ReorderStrategyViewSet( viewsets.ModelViewSet):
    """ViewSet for reorder strategy management"""
    queryset = ReorderStrategy.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        'list': 'read_reorder_strategy',
        'retrieve': 'read_reorder_strategy',
        'create': 'create_reorder_strategy',
        'update': 'update_reorder_strategy',
        'partial_update': 'update_reorder_strategy',
        'destroy': 'delete_reorder_strategy',
    }
    
    filterset_fields = ['is_active', 'profile', 'strategy_type', 'applies_to_all']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    serializer_class = ReorderStrategySerializer
    
    def get_queryset(self):
        """Filter by profile"""
        queryset = super().get_queryset()
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
        return queryset
    
    def perform_create(self, serializer):
        """Set profile and created_by on creation"""
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            serializer.save(
                profile_id=profile_id,
                created_by=self.request.user
            )
        else:
            serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get strategies by inventory category"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'category_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get strategies that apply to all or to this specific category
        strategies = self.get_queryset().filter(
            Q(applies_to_all=True) | Q(applies_to_categories__id=category_id)
        ).distinct()
        
        serializer = self.get_serializer(strategies, many=True)
        return Response(serializer.data)

class InventoryPolicyViewSet( viewsets.ModelViewSet):
    """ViewSet for inventory policy management"""
    queryset = InventoryPolicy.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        'list': 'read_inventory_policy',
        'retrieve': 'read_inventory_policy',
        'create': 'create_inventory_policy',
        'update': 'update_inventory_policy',
        'partial_update': 'update_inventory_policy',
        'destroy': 'delete_inventory_policy',
    }
    
    filterset_fields = ['is_active', 'profile', 'policy_type', 'applies_to_all']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'effective_date']
    ordering = ['-created_at']
    
    serializer_class = InventoryPolicySerializer
    
    def get_queryset(self):
        """Filter by profile"""
        queryset = super().get_queryset()
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
        
        # Filter by active status
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(
                is_active=True,
                effective_date__lte=today
            ).filter(
                Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Set profile and created_by on creation"""
        profile_id = self.request.headers.get('X-Profile-ID')
        if profile_id:
            serializer.save(
                profile_id=profile_id,
                created_by=self.request.user
            )
        else:
            serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get policies by inventory category"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'category_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get policies that apply to all or to this specific category
        policies = self.get_queryset().filter(
            Q(applies_to_all=True) | Q(applies_to_categories__id=category_id)
        ).distinct()
        
        serializer = self.get_serializer(policies, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get currently active policies"""
        today = timezone.now().date()
        
        policies = self.get_queryset().filter(
            is_active=True,
            effective_date__lte=today
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)
        )
        
        serializer = self.get_serializer(policies, many=True)
        return Response(serializer.data)
