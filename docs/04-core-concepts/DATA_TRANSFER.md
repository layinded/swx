# Data Export/Import

**Version:** 1.0.0
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Export Service](#export-service)
5. [Import Service](#import-service)
6. [API Endpoints](#api-endpoints)
7. [Events](#events)
8. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a data export/import system for user data portability, GDPR compliance, and bulk data operations. Supports JSON and CSV formats with full lifecycle tracking.

- **Export requests** — Create, track, cancel, and download data exports
- **Import requests** — Create, track, cancel, and monitor data imports
- **User scoping** — Users can only access their own exports/imports
- **Status tracking** — Full lifecycle: pending → processing → completed / failed / cancelled
- **Event emissions** — Full export/import lifecycle events
- **Admin oversight** — Admins can view all exports and imports

---

## Configuration

Data transfer settings in `swx_core/config/settings.py`:

```python
DATA_TRANSFER_ENABLED: bool = True
DATA_TRANSFER_DEFAULT_PAGE_SIZE: int = 50
DATA_TRANSFER_MAX_PAGE_SIZE: int = 200
DATA_TRANSFER_EXPORT_CACHE_TTL: int = 60
DATA_TRANSFER_IMPORT_CACHE_TTL: int = 60
```

---

## Database Models

### `swx_data_export`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK to swx_users |
| `export_type` | String(50) | full, user_data, audit_logs |
| `format` | String(20) | json, csv |
| `status` | String(20) | pending, processing, completed, failed, cancelled |
| `file_path` | String(500) | Storage path |
| `file_size` | Integer | File size in bytes |
| `record_count` | Integer | Number of records exported |
| `error_message` | String(1000) | Error message if failed |
| `expires_at` | DateTime | Download expiration |
| `metadata_` | JSONB | Arbitrary metadata |
| `started_at` | DateTime | Processing start |
| `completed_at` | DateTime | Completion timestamp |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_data_import`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK to swx_users |
| `import_type` | String(50) | full, user_data |
| `format` | String(20) | json, csv |
| `status` | String(20) | pending, processing, completed, failed, cancelled |
| `file_path` | String(500) | Source file path |
| `file_size` | Integer | File size in bytes |
| `record_count` | Integer | Total records |
| `records_succeeded` | Integer | Successfully imported |
| `records_failed` | Integer | Failed records |
| `error_message` | String(1000) | Error message if failed |
| `metadata_` | JSONB | Arbitrary metadata |
| `started_at` | DateTime | Processing start |
| `completed_at` | DateTime | Completion timestamp |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

---

## Export Service

```python
from swx_core.services.data_transfer.data_export_service import (
    create_export,
    get_export,
    list_exports,
    update_export,
    cancel_export,
    get_user_exports,
)

# Create an export request
export = await create_export(session, user_id, DataExportCreate(
    export_type="user_data",
    format="json",
))

# Cancel an export
export = await cancel_export(session, export_id)

# Get user's exports
exports = await get_user_exports(session, user_id)
```

---

## Import Service

```python
from swx_core.services.data_transfer.data_import_service import (
    create_import,
    get_import,
    list_imports,
    update_import,
    cancel_import,
    get_user_imports,
)

# Create an import request
imp = await create_import(session, user_id, DataImportCreate(
    import_type="user_data",
))

# Cancel an import
imp = await cancel_import(session, import_id)

# Get user's imports
imports = await get_user_imports(session, user_id)
```

---

## API Endpoints

### Admin Endpoints (`/admin/data-transfer`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/data-transfer/exports` | List all exports |
| GET | `/admin/data-transfer/exports/{id}` | Get export detail |
| GET | `/admin/data-transfer/imports` | List all imports |
| GET | `/admin/data-transfer/imports/{id}` | Get import detail |

### User Endpoints (`/user/data-transfer`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/data-transfer/exports` | List own exports |
| POST | `/user/data-transfer/exports` | Create export request |
| GET | `/user/data-transfer/exports/{id}` | Get own export |
| PUT | `/user/data-transfer/exports/{id}` | Update export |
| DELETE | `/user/data-transfer/exports/{id}` | Cancel export |
| GET | `/user/data-transfer/imports` | List own imports |
| POST | `/user/data-transfer/imports` | Create import request |
| GET | `/user/data-transfer/imports/{id}` | Get own import |
| PUT | `/user/data-transfer/imports/{id}` | Update import |
| DELETE | `/user/data-transfer/imports/{id}` | Cancel import |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `data_transfer.export_created` | export_id, user_id | Export request created |
| `data_transfer.export_updated` | export_id | Export status updated |
| `data_transfer.export_cancelled` | export_id | Export cancelled |
| `data_transfer.import_created` | import_id, user_id | Import request created |
| `data_transfer.import_updated` | import_id | Import status updated |
| `data_transfer.import_cancelled` | import_id | Import cancelled |

---

## Best Practices

1. **Set expiration on exports** — Use `expires_at` to auto-expire download links
2. **Track record counts** — Update `record_count`/`records_succeeded`/`records_failed` during processing
3. **Use metadata for context** — Store source info, options, and processing params in `metadata_`
4. **Handle failures gracefully** — Store error details in `error_message` for debugging
5. **Respect user scoping** — Always pass `user_id` when fetching user-specific data
6. **Process asynchronously** — Use background jobs for large export/import operations