import requests
import logging
from django.conf import settings
from django.core.cache import cache
from typing import Optional, Dict, Any, List
import json

logger = logging.getLogger(__name__)

class UserProfileService:
    """Enhanced service for communicating with the user/profile microservice"""
    
    BASE_URL = getattr(settings, 'USER_SERVICE_URL', 'http://localhost:8000')
    CACHE_TIMEOUT = 300  # 5 minutes
    
    @classmethod
    def get_user_details(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user details from user microservice"""
        if not user_id:
            return None
            
        # Check cache first
        cache_key = f"user_details_{user_id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            response = requests.get(
                f"{cls.BASE_URL}/account_api/users/{user_id}/",
                timeout=5
            )
            
            if response.status_code == 200:
                user_data = response.json()
                # Cache the result
                cache.set(cache_key, user_data, cls.CACHE_TIMEOUT)
                return user_data
            else:
                logger.warning(f"User service returned {response.status_code} for user {user_id}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error fetching user details for {user_id}: {str(e)}")
            return None
    
    @classmethod
    def get_company_profile(cls, profile_id: str) -> Optional[Dict[str, Any]]:
        """Fetch company profile details"""
        if not profile_id:
            return None
            
        # Check cache first
        cache_key = f"company_profile_{profile_id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            response = requests.get(
                f"{cls.BASE_URL}/account_api/profiles/{profile_id}/",
                timeout=5
            )
            
            if response.status_code == 200:
                profile_data = response.json()
                # Cache the result
                cache.set(cache_key, profile_data, cls.CACHE_TIMEOUT)
                return profile_data
            else:
                logger.warning(f"User service returned {response.status_code} for profile {profile_id}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error fetching company profile for {profile_id}: {str(e)}")
            return None
    
    @classmethod
    def get_profile_users(cls, profile_id: str) -> List[Dict[str, Any]]:
        """Fetch all users associated with a company profile"""
        if not profile_id:
            return []
            
        # Check cache first
        cache_key = f"profile_users_{profile_id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            response = requests.get(
                f"{cls.BASE_URL}/account_api/profiles/{profile_id}/users/",
                timeout=10
            )
            
            if response.status_code == 200:
                users_data = response.json()
                # Cache the result
                cache.set(cache_key, users_data, cls.CACHE_TIMEOUT)
                return users_data
            else:
                logger.warning(f"User service returned {response.status_code} for profile users {profile_id}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error fetching profile users for {profile_id}: {str(e)}")
            return []
    
    @classmethod
    def get_user_roles(cls, user_id: str, profile_id: str = None) -> List[Dict[str, Any]]:
        """Fetch user roles for a specific profile"""
        if not user_id:
            return []
            
        # Check cache first
        cache_key = f"user_roles_{user_id}_{profile_id or 'all'}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            params = {}
            if profile_id:
                params['profile_id'] = profile_id
                
            response = requests.get(
                f"{cls.BASE_URL}/account_api/users/{user_id}/roles/",
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                roles_data = response.json()
                # Cache the result
                cache.set(cache_key, roles_data, cls.CACHE_TIMEOUT)
                return roles_data
            else:
                logger.warning(f"User service returned {response.status_code} for user roles {user_id}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error fetching user roles for {user_id}: {str(e)}")
            return []
    
    @classmethod
    def get_user_groups(cls, user_id: str, profile_id: str = None) -> List[Dict[str, Any]]:
        """Fetch user groups for a specific profile"""
        if not user_id:
            return []
            
        # Check cache first
        cache_key = f"user_groups_{user_id}_{profile_id or 'all'}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            params = {}
            if profile_id:
                params['profile_id'] = profile_id
                
            response = requests.get(
                f"{cls.BASE_URL}/account_api/users/{user_id}/groups/",
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                groups_data = response.json()
                # Cache the result
                cache.set(cache_key, groups_data, cls.CACHE_TIMEOUT)
                return groups_data
            else:
                logger.warning(f"User service returned {response.status_code} for user groups {user_id}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error fetching user groups for {user_id}: {str(e)}")
            return []
    
    @classmethod
    def assign_user_role(cls, user_id: str, role_id: str, profile_id: str, 
                        start_date=None, end_date=None, auth_token=None) -> bool:
        """Assign a role to a user"""
        if not all([user_id, role_id, profile_id]):
            return False
        
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = f"Bearer {auth_token}"
                
            data = {
                'user_id': user_id,
                'role_id': role_id,
                'profile_id': profile_id
            }
            
            if start_date:
                data['start_date'] = start_date
            if end_date:
                data['end_date'] = end_date
                
            response = requests.post(
                f"{cls.BASE_URL}/account_api/roles/assign/",
                json=data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                # Invalidate relevant caches
                cls.invalidate_user_caches(user_id, profile_id)
                return True
            else:
                logger.warning(f"Failed to assign role: {response.status_code} - {response.text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Error assigning role to user {user_id}: {str(e)}")
            return False
    
    @classmethod
    def add_user_to_group(cls, user_id: str, group_id: str, profile_id: str, auth_token=None) -> bool:
        """Add a user to a group"""
        if not all([user_id, group_id, profile_id]):
            return False
        
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = f"Bearer {auth_token}"
                
            data = {
                'user_id': user_id,
                'group_id': group_id,
                'profile_id': profile_id
            }
                
            response = requests.post(
                f"{cls.BASE_URL}/account_api/groups/add_user/",
                json=data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                # Invalidate relevant caches
                cls.invalidate_user_caches(user_id, profile_id)
                return True
            else:
                logger.warning(f"Failed to add user to group: {response.status_code} - {response.text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Error adding user {user_id} to group: {str(e)}")
            return False
    
    @classmethod
    def create_company_profile(cls, profile_data: Dict[str, Any], auth_token=None) -> Optional[Dict[str, Any]]:
        """Create a new company profile"""
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = f"Bearer {auth_token}"
                
            response = requests.post(
                f"{cls.BASE_URL}/account_api/profiles/",
                json=profile_data,
                headers=headers,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.warning(f"Failed to create company profile: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error creating company profile: {str(e)}")
            return None
    
    @classmethod
    def update_company_profile(cls, profile_id: str, profile_data: Dict[str, Any], auth_token=None) -> Optional[Dict[str, Any]]:
        """Update an existing company profile"""
        if not profile_id:
            return None
            
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = f"Bearer {auth_token}"
                
            response = requests.patch(
                f"{cls.BASE_URL}/account_api/profiles/{profile_id}/",
                json=profile_data,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                # Invalidate cache
                cache.delete(f"company_profile_{profile_id}")
                return response.json()
            else:
                logger.warning(f"Failed to update company profile: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error updating company profile {profile_id}: {str(e)}")
            return None
    
    @classmethod
    def invite_user_to_profile(cls, email: str, profile_id: str, role_ids: List[str] = None, 
                              group_ids: List[str] = None, auth_token=None) -> bool:
        """Invite a user to join a company profile"""
        if not all([email, profile_id]):
            return False
        
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = f"Bearer {auth_token}"
                
            data = {
                'email': email,
                'profile_id': profile_id
            }
            
            if role_ids:
                data['role_ids'] = role_ids
            if group_ids:
                data['group_ids'] = group_ids
                
            response = requests.post(
                f"{cls.BASE_URL}/account_api/profiles/{profile_id}/invite/",
                json=data,
                headers=headers,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                # Invalidate profile users cache
                cache.delete(f"profile_users_{profile_id}")
                return True
            else:
                logger.warning(f"Failed to invite user: {response.status_code} - {response.text}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Error inviting user {email} to profile {profile_id}: {str(e)}")
            return False
    
    @classmethod
    def get_profile_activity_logs(cls, profile_id: str, page: int = 1, page_size: int = 20, 
                                 filters: Dict = None, auth_token=None) -> Optional[Dict[str, Any]]:
        """Get activity logs for a company profile"""
        if not profile_id:
            return None
        
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = f"Bearer {auth_token}"
                
            params = {
                'page': page,
                'page_size': page_size
            }
            
            if filters:
                params.update(filters)
                
            response = requests.get(
                f"{cls.BASE_URL}/account_api/profiles/{profile_id}/activity/",
                params=params,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get activity logs: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error getting activity logs for profile {profile_id}: {str(e)}")
            return None
    
    @classmethod
    def invalidate_user_caches(cls, user_id: str, profile_id: str = None):
        """Invalidate all caches related to a user"""
        cache.delete(f"user_details_{user_id}")
        cache.delete(f"user_permissions_{user_id}_{profile_id or 'default'}")
        cache.delete(f"user_roles_{user_id}_{profile_id or 'all'}")
        cache.delete(f"user_groups_{user_id}_{profile_id or 'all'}")
        
        if profile_id:
            cache.delete(f"profile_users_{profile_id}")
            cache.delete(f"user_owner_{user_id}_{profile_id}")
    
    @classmethod
    def invalidate_profile_caches(cls, profile_id: str):
        """Invalidate all caches related to a profile"""
        if not profile_id:
            return
            
        cache.delete(f"company_profile_{profile_id}")
        cache.delete(f"profile_users_{profile_id}")
