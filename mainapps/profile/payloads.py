from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class McpPayloadModel(BaseModel):
    """Shared MCP contract model that preserves known schema while tolerating backend extras."""

    model_config = ConfigDict(extra="allow")


class AddressResponsePayload(McpPayloadModel):
    country: str = Field("", description="Country name")
    region: str = Field("", description="Region or state")
    subregion: str = Field("", description="Subregion or province")
    city: str = Field("", description="City")
    street: str = Field("", description="Street name")
    street_number: Optional[int] = Field(None, description="Street number")
    apt_number: Optional[int] = Field(None, description="Apartment or suite number")
    postal_code: str = Field("", description="Postal code")


class CompanyProfileResponsePayload(McpPayloadModel):
    id: str = Field(..., description="Company-profile identifier")
    company_code: Optional[str] = Field(None, description="Company code")
    name: str = Field(..., description="Company name")
    industry: str = Field("", description="Industry")
    description: str = Field("", description="Company description")
    phone: str = Field("", description="Company phone")
    email: str = Field("", description="Company email")
    website: str = Field("", description="Company website")
    currency: str = Field("", description="Workspace currency")
    is_verified: Optional[bool] = Field(None, description="Whether the company is verified")
    workspace_role: Optional[str] = Field(None, description="Effective workspace role for the caller")
    is_owner: Optional[bool] = Field(None, description="Whether the caller owns the company")
    owner_user_id: Optional[str] = Field(None, description="Owner user identifier")
    member_count: int = Field(0, description="Active member count")
    role_count: int = Field(0, description="Active role count")
    group_count: int = Field(0, description="Active group count")
    agent_configured: Optional[bool] = Field(None, description="Whether an A2A agent is configured")
    subscription_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="Cached workspace subscription snapshot",
    )
    headquarters_address: Optional[AddressResponsePayload] = Field(
        None,
        description="Headquarters address",
    )


class StaffResponsePayload(McpPayloadModel):
    id: str = Field(..., description="Staff user identifier")
    full_name: str = Field("", description="Staff full name")
    first_name: str = Field("", description="First name")
    last_name: str = Field("", description="Last name")
    email: str = Field("", description="Email address")
    phone: str = Field("", description="Phone number")
    is_active: Optional[bool] = Field(None, description="Whether the user is active")
    is_verified: Optional[bool] = Field(None, description="Whether the user is verified")
    workspace_role: Optional[str] = Field(None, description="Membership role in the workspace")
    staff_roles: List[str] = Field(default_factory=list, description="Assigned staff roles")
    staff_groups: List[str] = Field(default_factory=list, description="Assigned staff groups")


class InvitationResponsePayload(McpPayloadModel):
    id: str = Field(..., description="Invitation identifier")
    invitation_code: str = Field(..., description="Invitation code")
    email: str = Field("", description="Invitee email")
    status: Optional[str] = Field(None, description="Invitation status")
    role: Optional[str] = Field(None, description="Proposed workspace role")
    profile_id: Optional[str] = Field(None, description="Company-profile identifier")
    profile_name: Optional[str] = Field(None, description="Company-profile name")
    invited_by_user_id: Optional[str] = Field(None, description="Inviter user identifier")
    invited_by_email: Optional[str] = Field(None, description="Inviter email")
    accepted_by_user_id: Optional[str] = Field(None, description="Accepting user identifier")
    created_at: Optional[str] = Field(None, description="Invitation creation timestamp")
    expires_at: Optional[str] = Field(None, description="Invitation expiry timestamp")
    accepted_at: Optional[str] = Field(None, description="Invitation acceptance timestamp")


class CompanyProfileSearchResponsePayload(McpPayloadModel):
    query: Optional[str] = Field(None, description="Applied search query")
    count: int = Field(0, description="Returned profile count")
    limit: int = Field(0, description="Applied result limit")
    active_profile_id: int = Field(..., description="Active workspace profile identifier")
    results: List[CompanyProfileResponsePayload] = Field(default_factory=list, description="Company profiles")


class ActiveCompanyProfileResponsePayload(McpPayloadModel):
    profile: CompanyProfileResponsePayload = Field(..., description="Active company profile")
    profile_id: int = Field(..., description="Active workspace profile identifier")
    company_code: Optional[str] = Field(None, description="Active company code")


class CompanyStaffSearchResponsePayload(McpPayloadModel):
    query: Optional[str] = Field(None, description="Applied search query")
    count: int = Field(0, description="Returned staff count")
    limit: int = Field(0, description="Applied result limit")
    profile_id: int = Field(..., description="Workspace profile identifier")
    results: List[StaffResponsePayload] = Field(default_factory=list, description="Staff results")


class InvitationListResponsePayload(McpPayloadModel):
    profile_id: int = Field(..., description="Workspace profile identifier")
    query: Optional[str] = Field(None, description="Applied search query")
    status: Optional[str] = Field(None, description="Applied invitation status filter")
    email: Optional[str] = Field(None, description="Invitee email filter")
    count: int = Field(0, description="Returned invitation count")
    results: List[InvitationResponsePayload] = Field(default_factory=list, description="Invitation results")


class InvitationDetailResponsePayload(McpPayloadModel):
    profile_id: int = Field(..., description="Workspace profile identifier")
    invitation: InvitationResponsePayload = Field(..., description="Invitation payload")


class StaffRoleResponsePayload(McpPayloadModel):
    id: str = Field(..., description="Role identifier")
    name: str = Field("", description="Role name")
    description: str = Field("", description="Role description")
    assignments_count: int = Field(0, description="Active assignment count")
    permission_count: int = Field(0, description="Permission count")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class StaffGroupResponsePayload(McpPayloadModel):
    id: str = Field(..., description="Group identifier")
    name: str = Field("", description="Group name")
    description: str = Field("", description="Group description")
    users_count: int = Field(0, description="User count")
    permission_count: int = Field(0, description="Permission count")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class CompanyRolesResponsePayload(McpPayloadModel):
    profile_id: int = Field(..., description="Workspace profile identifier")
    results: List[StaffRoleResponsePayload] = Field(default_factory=list, description="Role payloads")


class CompanyGroupsResponsePayload(McpPayloadModel):
    profile_id: int = Field(..., description="Workspace profile identifier")
    results: List[StaffGroupResponsePayload] = Field(default_factory=list, description="Group payloads")


class StaffPermissionsSummaryResponsePayload(McpPayloadModel):
    profile_id: int = Field(..., description="Workspace profile identifier")
    user_id: str = Field(..., description="Staff user identifier")
    email: str = Field("", description="Staff email")
    workspace_role: Optional[str] = Field(None, description="Workspace role")
    roles: List[str] = Field(default_factory=list, description="Assigned roles")
    groups: List[str] = Field(default_factory=list, description="Assigned groups")
    role_permissions: List[str] = Field(default_factory=list, description="Permissions from roles")
    group_permissions: List[str] = Field(default_factory=list, description="Permissions from groups")
    custom_permissions: List[str] = Field(default_factory=list, description="Custom permissions")
    effective_permissions: List[str] = Field(default_factory=list, description="Effective permissions")


class InvitationAcceptanceResultPayload(McpPayloadModel):
    membership_id: str = Field(..., description="Created or reused membership identifier")
    profile_id: str = Field(..., description="Company-profile identifier")
    role: str = Field(..., description="Accepted workspace role")
    status: str = Field(..., description="Invitation status after acceptance")


class BulkInvitationSkippedPayload(McpPayloadModel):
    email: str = Field(..., description="Skipped email address")
    reason: str = Field(..., description="Skip reason")


class BulkInvitationResultPayload(McpPayloadModel):
    created_count: int = Field(0, description="Created invitation count")
    existing_pending_count: int = Field(0, description="Existing pending invitation count")
    skipped_count: int = Field(0, description="Skipped invitation count")
    invalid_count: int = Field(0, description="Invalid email count")
    created: List[InvitationResponsePayload] = Field(default_factory=list, description="Created invitations")
    existing_pending: List[InvitationResponsePayload] = Field(
        default_factory=list,
        description="Existing pending invitations",
    )
    skipped: List[BulkInvitationSkippedPayload] = Field(default_factory=list, description="Skipped emails")
    invalid_emails: List[str] = Field(default_factory=list, description="Invalid emails")


class StaffRemovalResultPayload(McpPayloadModel):
    message: str = Field("", description="Removal result message")
    deactivated_assignments: int = Field(0, description="Assignments deactivated")
    deactivated_membership: bool = Field(False, description="Whether the company membership was deactivated")


class SimpleDetailResultPayload(McpPayloadModel):
    detail: str = Field("", description="Backend detail message")


class CompanyInvitationActionResultPayload(McpPayloadModel):
    profile_id: int = Field(..., description="Workspace profile identifier")
    invitation: Optional[InvitationResponsePayload] = Field(None, description="Invitation result when present")
    result: Optional[
        InvitationAcceptanceResultPayload
        | BulkInvitationResultPayload
        | StaffRemovalResultPayload
        | SimpleDetailResultPayload
    ] = Field(None, description="Backend action result payload")


class InviteCompanyStaffPayload(McpPayloadModel):
    email: str = Field(..., description="Invitee email")
    role: Optional[str] = Field(None, description="Workspace role to assign")
    invitation_message: Optional[str] = Field(None, description="Invitation message")


class BulkInviteCompanyStaffPayload(McpPayloadModel):
    emails: List[str] = Field(default_factory=list, description="Invitee email addresses")
    role: Optional[str] = Field(None, description="Workspace role to assign")
    invitation_message: Optional[str] = Field(None, description="Invitation message")


class InvitationDecisionPayload(McpPayloadModel):
    invitation_code: str = Field(..., description="Invitation code")


class RemoveCompanyStaffPayload(McpPayloadModel):
    user_id: str = Field(..., description="User identifier to remove")
