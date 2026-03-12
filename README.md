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
git clone https://github.com/your-repo/pharm-inventory.git

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

## Technology Stack
- **Backend**: Django, Django REST Framework
- **Database**: PostgreSQL
- **Cache**: Redis
- **Frontend**: HTML templates with Bootstrap
- **Deployment**: Docker

## License
MIT
