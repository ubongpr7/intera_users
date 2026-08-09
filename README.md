# Pharmacy Inventory Management System

![Pharm-Inventory Logo](static/images/logos/logo.png)

A comprehensive Django-based inventory management system for pharmaceutical operations.

## Features
- **Inventory Management**: Track drug stock levels, batches, and expiration dates
- **Order Processing**: Manage purchase and sales orders
- **User Management**: Role-based access control
- **Reporting**: Generate inventory and sales reports
- **API**: RESTful API for integration

## Quick Start
```bash
# Clone the repository
git clone https://github.com/your-repo/intera-ims.git

# Setup environment
cp .env.example .env
docker-compose up -d
```

## JWT (RS256) setup

The API now expects RS/ES key-based JWT signing (default: `RS256`).

Generate keys:

```bash
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
```

Set env vars:

```env
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=/absolute/path/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/absolute/path/jwt_public.pem
```

## Documentation
- [API Documentation](/docs/api.md)
- [Architecture Overview](/docs/architecture.md)
- [Development Guide](/docs/development.md)

## MCP server

This repo now includes a User Service MCP server at `mcp_server.server`.

Current tools:

- `list_accessible_company_profiles`: list workspaces the authenticated caller can access
- `get_active_company_profile`: return the active workspace resolved from the caller's `profile_id` claim
- `search_company_staff`: search staff in the caller's active workspace

Transport:

- Streamable HTTP endpoint: `/mcp`
- Health endpoint: `/health`

Local Docker Compose service:

- Service name: `users_mcp`
- Container name: `users-mcp`
- Host port: `7010`

Run locally:

```bash
docker compose up users_mcp
```

Direct local run:

```bash
uv run python -m mcp_server.server
```

Relevant environment variables:

- `USERS_MCP_HOST` default `0.0.0.0`
- `USERS_MCP_PORT` default `8000`
- `USERS_MCP_MOUNT_PATH` default `/mcp`
- `USERS_MCP_LOG_LEVEL` default `info`
- `USERS_MCP_ALLOWED_HOSTS` optional comma-separated Host allowlist for FastMCP transport security
- `USERS_MCP_ALLOWED_ORIGINS` optional comma-separated Origin allowlist for FastMCP transport security

Authentication:

- The MCP server expects the same Bearer access token issued by `intera_users`.
- Authenticated tools require `user_id` and `profile_id` claims.

Recommended K-A2A config for this MCP server:

## A2A ownership

`intera_users` no longer owns agent setup, runtime configuration, or AI credential delivery.

- `intera_users` owns identity, workspace membership, roles, and permissions.
- [kafka_a2a](/Users/ubongpr7/dev/pr7/inventory/kafka_a2a) owns workspace agent setup, runtime registry, conversations, and AI service configuration.

```json
{
  "id": "users",
  "serverUrl": "http://users-mcp:8000/mcp/",
  "auth": { "mode": "forward_bearer" },
  "tools": [
    "list_accessible_company_profiles",
    "get_active_company_profile",
    "search_company_staff"
  ]
}
```

## Technology Stack
- **Backend**: Django, Django REST Framework
- **Database**: PostgreSQL
- **Cache**: Redis
- **Frontend**: HTML templates with Bootstrap
- **Deployment**: Docker

## License
MIT
