# Status Page

**Version:** 1.0.0
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Components](#components)
5. [Incidents](#incidents)
6. [Status Summary](#status-summary)
7. [API Endpoints](#api-endpoints)
8. [Events](#events)
9. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a status page system for tracking service component health, managing incidents, and providing a real-time status summary. Designed for public-facing status pages with admin-managed incidents and component monitoring.

- **Service components** — Track operational status of system components
- **Incidents** — Create, update, and resolve incidents with severity tracking
- **Incident updates** — Timeline updates within each incident
- **Status summary** — Aggregated view of all components and active incidents
- **Caching** — Redis-backed component and incident cache
- **Event emissions** — Full lifecycle event tracking

---

## Configuration

Status page settings in `swx_core/config/settings.py`:

```python
STATUS_ENABLED: bool = True
STATUS_DEFAULT_PAGE_SIZE: int = 50
STATUS_MAX_PAGE_SIZE: int = 200
STATUS_COMPONENT_CACHE_TTL: int = 60
STATUS_INCIDENT_CACHE_TTL: int = 30
```

---

## Database Models

### `swx_service_component`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | String(200) | Component name |
| `description` | Text | Optional description |
| `status` | String(20) | operational, degraded, partial_outage, major_outage |
| `group_name` | String(100) | Optional grouping |
| `sort_order` | Integer | Display order (default 0) |
| `uptime_percentage` | Float | Optional uptime metric |
| `metadata_` | JSONB | Arbitrary metadata |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_status_incident`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `title` | String(500) | Incident title |
| `description` | Text | Detailed description |
| `severity` | String(20) | investigating, minor, major, critical |
| `status` | String(20) | open, identified, monitoring, resolved |
| `component_id` | UUID | FK to swx_service_component (optional) |
| `started_at` | DateTime | When incident started |
| `resolved_at` | DateTime | When incident resolved |
| `metadata_` | JSONB | Arbitrary metadata |
| `created_by` | UUID | FK to swx_users (admin) |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_incident_update`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `incident_id` | UUID | FK to swx_status_incident |
| `message` | Text | Update message |
| `status` | String(20) | Current status at update time |
| `created_by` | UUID | FK to swx_users (admin) |
| `created_at` | DateTime | Update timestamp |

---

## Components

```python
from swx_core.services.status.status_component_service import (
    create_component,
    get_component,
    list_components,
    update_component,
    delete_component,
)

# Create a component
component = await create_component(session, ServiceComponentCreate(
    name="API Server",
    description="Main REST API server",
    group_name="core",
    status="operational",
))

# Update component status
component = await update_component(session, component_id, ServiceComponentUpdate(
    status="degraded",
))
```

Component statuses: `operational`, `degraded`, `partial_outage`, `major_outage`

---

## Incidents

```python
from swx_core.services.status.status_incident_service import (
    create_incident,
    get_incident,
    list_incidents,
    update_incident,
    resolve_incident,
    add_incident_update,
    get_status_summary,
)

# Create an incident
incident = await create_incident(session, admin_id, StatusIncidentCreate(
    title="API Latency Issues",
    description="Users experiencing high latency",
    severity="major",
    component_id=component_id,
))

# Add an update
update = await add_incident_update(session, incident_id, admin_id, IncidentUpdateCreate(
    message="Investigating increased response times",
    status="investigating",
))

# Resolve the incident
incident = await resolve_incident(session, incident_id)
```

---

## Status Summary

```python
# Get aggregated status
summary = await get_status_summary(session)
# Returns: {"components": [...], "active_incidents": [...]}
```

---

## API Endpoints

### Admin Endpoints (`/admin/status`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/status/components` | List all components |
| POST | `/admin/status/components` | Create component |
| GET | `/admin/status/components/{id}` | Get component |
| PUT | `/admin/status/components/{id}` | Update component |
| DELETE | `/admin/status/components/{id}` | Delete component |
| GET | `/admin/status/incidents` | List all incidents |
| POST | `/admin/status/incidents` | Create incident |
| GET | `/admin/status/incidents/{id}` | Get incident |
| PUT | `/admin/status/incidents/{id}` | Update incident |
| POST | `/admin/status/incidents/{id}/resolve` | Resolve incident |
| POST | `/admin/status/incidents/{id}/updates` | Add incident update |

### User Endpoints (`/user/status`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/status/summary` | Get status summary |
| GET | `/user/status/components` | List components |
| GET | `/user/status/components/{id}` | Get component |
| GET | `/user/status/incidents` | List active incidents |
| GET | `/user/status/incidents/{id}` | Get incident |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `status.component_created` | component_id, name | Component created |
| `status.component_updated` | component_id | Component updated |
| `status.component_deleted` | component_id | Component deleted |
| `status.incident_created` | incident_id, severity | Incident created |
| `status.incident_updated` | incident_id | Incident updated |
| `status.incident_resolved` | incident_id | Incident resolved |
| `status.incident_update_added` | incident_id, update_id | Incident update added |

---

## Best Practices

1. **Group components** — Use `group_name` to organize components (core, infrastructure, integrations)
2. **Set sort_order** — Control display order on public status pages
3. **Track uptime** — Update `uptime_percentage` from monitoring systems
4. **Use severity levels** — Reserve `critical` for complete outages, `minor` for small disruptions
5. **Add incident updates** — Keep users informed with regular `add_incident_update` calls
6. **Resolve promptly** — Always call `resolve_incident` when the issue is fixed