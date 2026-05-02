# Glossary

**Version:** 1.0.0  
**Last Updated:** 2026-01-26

---

## Table of Contents

1. [A](#a)
2. [B](#b)
3. [C](#c)
4. [D](#d)
5. [E](#e)
6. [F](#f)
7. [G](#g)
8. [H](#h)
9. [I](#i)
10. [J](#j)
11. [K](#k)
12. [L](#l)
13. [M](#m)
14. [N](#n)
15. [O](#o)
16. [P](#p)
17. [Q](#q)
18. [R](#r)
19. [S](#s)
20. [T](#t)
21. [U](#u)
22. [V](#v)
23. [W](#w)
24. [X](#x)
25. [Y](#y)
26. [Z](#z)

---

## A

### ABAC (Attribute-Based Access Control)

Policy-based authorization system that evaluates conditions on actors, actions, resources, and context to make authorization decisions.

### Access Token

Short-lived JWT token used for API authentication. Default expiration: 7 days.

### Actor

Entity performing an action (User, Admin, System).

### Admin Domain

Security domain for administrative operations. Separate from User domain.

### Alembic

Database migration tool used by SwX-API.

### Alert

Structured event requiring attention, dispatched via multiple channels (Slack, Email, SMS, Logs).

### Alert Channel

Delivery mechanism for alerts (Slack, Email, SMS, Logs).

### Alert Severity

Level of alert importance: INFO, WARNING, ERROR, CRITICAL.

### API

Application Programming Interface. RESTful API provided by SwX-API.

### Async

Asynchronous programming model using asyncio and async/await.

### Audit Log

Immutable record of security and business events.

### Authentication

Process of verifying user identity (login, token validation).

### Authorization

Process of determining if user can perform an action (permissions, policies).

---

## B

### Base Model

Base class for all database models (`swx_core.models.base.Base`).

### Billing Account

Account associated with a user or team for billing purposes.

### Billing Plan

Subscription tier (Free, Pro, Team, Enterprise).

### Boolean Feature

On/off feature type (enabled/disabled).

### Burst Limit

Rate limit for short-term spikes (1 minute window).

---

## C

### Caddy

Reverse proxy and TLS termination server used in production.

### Cache

In-memory storage for frequently accessed data (Redis).

### Condition

Attribute-based check in a policy (e.g., `actor.team_id == resource.team_id`).

### Controller

Request handling layer (Routes → Controllers → Services → Repositories).

### CRUD

Create, Read, Update, Delete operations.

---

## D

### Daily Limit

Rate limit for 24-hour window.

### Database

PostgreSQL database with TimescaleDB extension.

### Dead Letter Queue

Queue for jobs that failed after max retry attempts.

### Defense in Depth

Multiple security layers protecting resources.

### Domain Separation

Complete isolation between Admin, User, and System domains.

---

## E

### Entitlement

Plan's access to a feature (e.g., "free" plan has "api_requests: 1000").

### Entitlement Resolver

Service that resolves if an actor has access to a feature.

### Environment Variable

Configuration value stored in `.env` file or environment.

### Error Handling

Process of handling and responding to errors gracefully.

---

## F

### Fail-Closed

Security failures deny access by default.

### Feature

Capability or resource (e.g., "api_requests", "export_data").

### Feature Registry

Central registry for all gateable features.

### FastAPI

Modern Python web framework used by SwX-API.

### Foreign Key

Database constraint ensuring referential integrity.

---

## G

### Getting Started

Initial setup and installation guide.

---

## H

### Health Check

Endpoint for checking service health (`/api/utils/health-check`).

### HTTPS

Secure HTTP protocol (required in production).

---

## I

### Idempotent

Operation that can be repeated without changing the result.

### Index

Database index for faster queries.

### Infrastructure

Server, database, Redis, and other supporting services.

---

## J

### Job

Background task for asynchronous processing.

### JWT (JSON Web Token)

Token format used for authentication.

---

## K

### Key

Unique identifier for settings, features, or policies.

---

## L

### Limit

Rate limit value (burst, sustained, daily).

### Logging

Process of recording events and errors.

---

## M

### Metered Feature

Pay-per-use feature type (billed per usage).

### Middleware

Request processing layer (CORS, logging, rate limiting, etc.).

### Migration

Database schema change (Alembic migration).

### Model

Database model (SQLModel class).

---

## N

### Network

Docker network for service communication.

---

## O

### OAuth

OAuth2 authentication protocol.

### OpenAPI

API specification format (Swagger/OpenAPI).

### Orphan Record

Database record with invalid foreign key reference.

---

## P

### Pagination

Process of dividing results into pages (skip, limit).

### Permission

Atomic action (e.g., `"user:read"`, `"user:write"`).

### Persona

Predefined user role for testing (System Operator, Admin, Team Owner, Team Member).

### Plan

Billing subscription tier (Free, Pro, Team, Enterprise).

### Policy

Authorization rule with conditions (ABAC).

### Policy Engine

Service that evaluates policies for authorization decisions.

### PostgreSQL

Relational database used by SwX-API.

---

## Q

### Quota Feature

Limited quantity feature type (e.g., "api_requests: 1000").

---

## R

### Rate Limiting

Process of limiting request frequency to prevent abuse.

### RBAC (Role-Based Access Control)

Permission-based authorization system.

### Redis

In-memory data store used for caching and rate limiting.

### Refresh Token

Long-lived token for obtaining new access tokens. Default expiration: 30 days.

### Repository

Database access layer (data access).

### Role

Collection of permissions (e.g., "admin", "editor").

### Route

API endpoint (FastAPI route).

---

## S

### Secret Key

Cryptographic key for signing JWT tokens.

### Seed

Process of populating database with initial data.

### Service

Business logic layer (between controller and repository).

### Settings

Runtime configuration stored in database (`SystemConfig`).

### Simulation

End-to-end user workflow testing.

### Skip Paths

API paths that bypass rate limiting.

### SQLModel

ORM combining SQLAlchemy and Pydantic.

### State Validation

Process of verifying database integrity.

### Sustained Limit

Rate limit for sustained usage (1 hour window).

### System Domain

Security domain for internal system operations.

---

## T

### Team

Group of users with shared resources.

### Team-Scoped

Permission or role scoped to a specific team.

### Token

JWT token for authentication (access, refresh, reset).

### TimescaleDB

PostgreSQL extension for time-series data.

---

## U

### Usage Record

Record of feature usage for quota/metered features.

### User Domain

Security domain for regular application users.

---

## V

### Validation

Process of verifying data correctness (Pydantic validation).

---

## W

### Webhook

HTTP callback for external service notifications.

### Worker

Background job processor.

---

## X

### XSS (Cross-Site Scripting)

Security vulnerability prevented by input validation and output encoding.

---

## Y

### YAML

Configuration file format (docker-compose.yml).

---

## Z

### Zero-Downtime

Deployment strategy with no service interruption.

---

## Next Steps

- Read [Migration Guide](./MIGRATION_GUIDE.md) for upgrade procedures
- Read [Changelog](./CHANGELOG.md) for version history
- Read [Overview](../01-overview/OVERVIEW.md) for framework introduction

---

**Status:** Glossary documented, ready for implementation.
