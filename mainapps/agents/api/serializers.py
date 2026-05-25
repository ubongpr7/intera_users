from __future__ import annotations

import json
import os

from cryptography.fernet import Fernet
from rest_framework import serializers

from mainapps.agents.models import (
    AgentInstructionPreset,
    AgentSkill,
    AgentTemplate,
    AgentTemplateSkillBinding,
    AgentTemplateToolBinding,
    AgentTool,
    ToolServer,
    WorkspaceAgent,
    WorkspaceAgentSkillBinding,
    WorkspaceAgentToolBinding,
    WorkspaceToolConnection,
)
from mainapps.profile.models import ModelVersion


def _encrypt_secret(value: str) -> str:
    raw = (value or "").strip()
    if not raw or raw.startswith("gAAAA"):
        return raw
    key = (os.getenv("FERNET_KEY") or "").strip()
    if not key:
        return raw
    return Fernet(key).encrypt(raw.encode()).decode()


def _encrypt_json_payload(value: object | None) -> str:
    if value in (None, "", {}, []):
        return ""
    return _encrypt_secret(json.dumps(value, separators=(",", ":"), ensure_ascii=True))


class ToolServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolServer
        fields = [
            "id",
            "server_id",
            "name",
            "description",
            "transport",
            "server_url",
            "tool_name_prefix",
            "auth_mode",
            "auth_config",
            "health_status",
            "metadata",
            "last_synced_at",
        ]


class WorkspaceToolConnectionReadSerializer(serializers.ModelSerializer):
    tool_server = ToolServerSerializer(read_only=True)
    owner_user_id = serializers.UUIDField(read_only=True)
    has_credential_payload = serializers.SerializerMethodField()
    has_access_token = serializers.SerializerMethodField()
    has_refresh_token = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceToolConnection
        fields = [
            "id",
            "profile",
            "tool_server",
            "name",
            "slug",
            "connection_scope",
            "owner_user_id",
            "auth_type",
            "server_url_override",
            "status",
            "token_expires_at",
            "granted_scopes",
            "resource_owner_id",
            "resource_label",
            "last_tested_at",
            "last_error",
            "metadata",
            "has_credential_payload",
            "has_access_token",
            "has_refresh_token",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_has_credential_payload(self, obj):
        return bool(obj.credential_payload_encrypted)

    def get_has_access_token(self, obj):
        return bool(obj.access_token_encrypted)

    def get_has_refresh_token(self, obj):
        return bool(obj.refresh_token_encrypted)


class AgentToolSerializer(serializers.ModelSerializer):
    tool_server = ToolServerSerializer(read_only=True)
    full_tool_name = serializers.CharField(read_only=True)

    class Meta:
        model = AgentTool
        fields = [
            "id",
            "scope",
            "profile",
            "key",
            "display_name",
            "description",
            "remote_tool_name",
            "full_tool_name",
            "auth_mode",
            "input_schema",
            "output_schema",
            "metadata",
            "is_discoverable",
            "health_status",
            "tool_server",
            "last_synced_at",
        ]
        read_only_fields = fields


class AgentSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSkill
        fields = [
            "id",
            "scope",
            "profile",
            "key",
            "name",
            "description",
            "tags",
            "examples",
            "input_modes",
            "output_modes",
            "metadata",
        ]
        read_only_fields = fields


class AgentInstructionPresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentInstructionPreset
        fields = [
            "id",
            "scope",
            "profile",
            "key",
            "title",
            "description",
            "instruction_type",
            "body",
            "tags",
            "metadata",
            "is_default",
        ]
        read_only_fields = fields


class AgentTemplateSkillBindingSerializer(serializers.ModelSerializer):
    skill = AgentSkillSerializer(read_only=True)

    class Meta:
        model = AgentTemplateSkillBinding
        fields = ["id", "order", "is_primary", "metadata", "skill"]


class AgentTemplateToolBindingSerializer(serializers.ModelSerializer):
    tool = AgentToolSerializer(read_only=True)

    class Meta:
        model = AgentTemplateToolBinding
        fields = ["id", "order", "is_required", "tool_config", "tool"]


class AgentTemplateSerializer(serializers.ModelSerializer):
    skill_bindings = AgentTemplateSkillBindingSerializer(many=True, read_only=True)
    tool_bindings = AgentTemplateToolBindingSerializer(many=True, read_only=True)
    card_payload = serializers.SerializerMethodField()

    class Meta:
        model = AgentTemplate
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "protocol_version",
            "preferred_transport",
            "url",
            "version",
            "documentation_url",
            "icon_url",
            "capabilities",
            "default_input_modes",
            "default_output_modes",
            "system_instruction",
            "developer_instruction",
            "assistant_instruction",
            "metadata",
            "is_active",
            "is_featured",
            "allow_workspace_installs",
            "sort_order",
            "skill_bindings",
            "tool_bindings",
            "card_payload",
        ]
        read_only_fields = fields

    def get_card_payload(self, obj):
        return obj.build_agent_card_payload()


class ModelVersionOptionSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="provider", read_only=True)

    class Meta:
        model = ModelVersion
        fields = ["id", "model_name", "provider"]
        read_only_fields = fields


class WorkspaceAgentSkillBindingSerializer(serializers.ModelSerializer):
    skill = AgentSkillSerializer(read_only=True)

    class Meta:
        model = WorkspaceAgentSkillBinding
        fields = ["id", "order", "is_primary", "metadata", "skill"]


class WorkspaceAgentToolBindingSerializer(serializers.ModelSerializer):
    tool = AgentToolSerializer(read_only=True)

    class Meta:
        model = WorkspaceAgentToolBinding
        fields = ["id", "order", "is_required", "tool_config", "tool"]


class WorkspaceAgentReadSerializer(serializers.ModelSerializer):
    source_template = AgentTemplateSerializer(read_only=True)
    llm_version = ModelVersionOptionSerializer(read_only=True)
    skill_bindings = WorkspaceAgentSkillBindingSerializer(many=True, read_only=True)
    tool_bindings = WorkspaceAgentToolBindingSerializer(many=True, read_only=True)
    card_payload = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceAgent
        fields = [
            "id",
            "profile",
            "source_template",
            "origin",
            "visibility",
            "routing_policy",
            "slug",
            "name",
            "description",
            "protocol_version",
            "preferred_transport",
            "url",
            "provider_organization",
            "provider_url",
            "version",
            "documentation_url",
            "icon_url",
            "additional_interfaces",
            "capabilities",
            "security_schemes",
            "security",
            "supports_authenticated_extended_card",
            "default_input_modes",
            "default_output_modes",
            "system_instruction",
            "developer_instruction",
            "assistant_instruction",
            "llm_version",
            "llm_temperature",
            "max_reasoning_steps",
            "metadata",
            "is_enabled",
            "template_version_snapshot",
            "skill_bindings",
            "tool_bindings",
            "card_payload",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_card_payload(self, obj):
        return obj.build_agent_card_payload()


class WorkspaceAgentRuntimeSummarySerializer(serializers.ModelSerializer):
    source_template_slug = serializers.CharField(source="source_template.slug", read_only=True)
    llm_version = ModelVersionOptionSerializer(read_only=True)
    card_payload = serializers.SerializerMethodField()
    tool_count = serializers.SerializerMethodField()
    skill_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceAgent
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "origin",
            "visibility",
            "routing_policy",
            "preferred_transport",
            "version",
            "icon_url",
            "documentation_url",
            "source_template_slug",
            "llm_version",
            "capabilities",
            "default_input_modes",
            "default_output_modes",
            "supports_authenticated_extended_card",
            "metadata",
            "tool_count",
            "skill_count",
            "card_payload",
        ]
        read_only_fields = fields

    def get_card_payload(self, obj):
        return obj.build_agent_card_payload()

    def get_tool_count(self, obj):
        return obj.tool_bindings.count()

    def get_skill_count(self, obj):
        return obj.skill_bindings.count()


class WorkspaceAgentRuntimeConfigSerializer(serializers.ModelSerializer):
    source_template_slug = serializers.CharField(source="source_template.slug", read_only=True)
    llm_version = ModelVersionOptionSerializer(read_only=True)
    skill_bindings = WorkspaceAgentSkillBindingSerializer(many=True, read_only=True)
    tool_bindings = WorkspaceAgentToolBindingSerializer(many=True, read_only=True)
    runtime_name = serializers.SerializerMethodField()
    runtime_config = serializers.SerializerMethodField()
    card_payload = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceAgent
        fields = [
            "id",
            "profile",
            "runtime_name",
            "source_template_slug",
            "origin",
            "visibility",
            "routing_policy",
            "slug",
            "name",
            "description",
            "protocol_version",
            "preferred_transport",
            "url",
            "provider_organization",
            "provider_url",
            "version",
            "documentation_url",
            "icon_url",
            "additional_interfaces",
            "capabilities",
            "security_schemes",
            "security",
            "supports_authenticated_extended_card",
            "default_input_modes",
            "default_output_modes",
            "system_instruction",
            "developer_instruction",
            "assistant_instruction",
            "llm_version",
            "llm_temperature",
            "max_reasoning_steps",
            "metadata",
            "runtime_config",
            "is_enabled",
            "template_version_snapshot",
            "skill_bindings",
            "tool_bindings",
            "card_payload",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_runtime_name(self, obj):
        return obj.build_runtime_name()

    def get_runtime_config(self, obj):
        return obj.build_runtime_config()

    def get_card_payload(self, obj):
        return obj.build_agent_card_payload()


class WorkspaceAgentRuntimeInternalSerializer(WorkspaceAgentRuntimeConfigSerializer):
    runtime_card_payload = serializers.SerializerMethodField()

    class Meta(WorkspaceAgentRuntimeConfigSerializer.Meta):
        fields = WorkspaceAgentRuntimeConfigSerializer.Meta.fields + [
            "runtime_card_payload",
        ]
        read_only_fields = fields

    def get_runtime_card_payload(self, obj):
        return obj.build_runtime_card_payload()


class WorkspaceAgentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceAgent
        fields = [
            "slug",
            "name",
            "description",
            "visibility",
            "routing_policy",
            "protocol_version",
            "preferred_transport",
            "url",
            "provider_organization",
            "provider_url",
            "version",
            "documentation_url",
            "icon_url",
            "additional_interfaces",
            "capabilities",
            "security_schemes",
            "security",
            "supports_authenticated_extended_card",
            "default_input_modes",
            "default_output_modes",
            "system_instruction",
            "developer_instruction",
            "assistant_instruction",
            "llm_version",
            "llm_temperature",
            "max_reasoning_steps",
            "metadata",
            "is_enabled",
        ]


class InstallAgentTemplateSerializer(serializers.Serializer):
    slug = serializers.SlugField(required=False, allow_blank=False)
    name = serializers.CharField(required=False, allow_blank=False, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=WorkspaceAgent._meta.get_field("visibility").choices, required=False)
    routing_policy = serializers.ChoiceField(
        choices=WorkspaceAgent._meta.get_field("routing_policy").choices, required=False
    )
    system_instruction = serializers.CharField(required=False, allow_blank=True)
    developer_instruction = serializers.CharField(required=False, allow_blank=True)
    assistant_instruction = serializers.CharField(required=False, allow_blank=True)
    is_enabled = serializers.BooleanField(required=False)


class WorkspaceAgentToolBindingWriteSerializer(serializers.Serializer):
    tool_id = serializers.UUIDField()
    order = serializers.IntegerField(required=False, min_value=0)
    is_required = serializers.BooleanField(required=False, default=False)
    tool_config = serializers.JSONField(required=False)


class WorkspaceAgentSkillBindingWriteSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    order = serializers.IntegerField(required=False, min_value=0)
    is_primary = serializers.BooleanField(required=False, default=False)
    metadata = serializers.JSONField(required=False)


class WorkspaceToolConnectionWriteSerializer(serializers.ModelSerializer):
    credential_payload = serializers.JSONField(required=False, write_only=True)
    access_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    refresh_token = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = WorkspaceToolConnection
        fields = [
            "tool_server",
            "name",
            "slug",
            "connection_scope",
            "owner_user",
            "auth_type",
            "server_url_override",
            "credential_payload",
            "access_token",
            "refresh_token",
            "token_expires_at",
            "granted_scopes",
            "resource_owner_id",
            "resource_label",
            "status",
            "last_tested_at",
            "last_error",
            "metadata",
        ]

    def create(self, validated_data):
        credential_payload = validated_data.pop("credential_payload", None)
        access_token = validated_data.pop("access_token", None)
        refresh_token = validated_data.pop("refresh_token", None)
        validated_data["credential_payload_encrypted"] = _encrypt_json_payload(credential_payload)
        validated_data["access_token_encrypted"] = _encrypt_secret(str(access_token or ""))
        validated_data["refresh_token_encrypted"] = _encrypt_secret(str(refresh_token or ""))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        credential_payload = validated_data.pop("credential_payload", None) if "credential_payload" in validated_data else None
        access_token = validated_data.pop("access_token", None) if "access_token" in validated_data else None
        refresh_token = validated_data.pop("refresh_token", None) if "refresh_token" in validated_data else None
        if "credential_payload" in self.initial_data:
            instance.credential_payload_encrypted = _encrypt_json_payload(credential_payload)
        if "access_token" in self.initial_data:
            instance.access_token_encrypted = _encrypt_secret(str(access_token or ""))
        if "refresh_token" in self.initial_data:
            instance.refresh_token_encrypted = _encrypt_secret(str(refresh_token or ""))
        return super().update(instance, validated_data)
