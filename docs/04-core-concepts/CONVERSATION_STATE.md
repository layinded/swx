# Conversation State

**Version:** 1.0.0
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Conversation Management](#conversation-management)
5. [Message Management](#message-management)
6. [API Endpoints](#api-endpoints)
7. [Events](#events)
8. [Best Practices](#best-practices)

---

## Overview

SwX-API includes a conversation state system for managing persistent chat conversations with messages, metadata, and lifecycle management.

- **Conversation lifecycle** — Create, update, archive, and soft-delete conversations
- **Message management** — Add, update, and list messages within conversations
- **Ownership scoping** — Users can only access their own conversations
- **Metadata support** — JSONB metadata on conversations and messages
- **Event emissions** — Full event lifecycle tracking
- **Caching** — Redis-backed conversation cache with configurable TTL

---

## Configuration

Conversation state settings in `swx_core/config/settings.py`:

```python
CONVERSATION_ENABLED: bool = True
CONVERSATION_DEFAULT_PAGE_SIZE: int = 50
CONVERSATION_MAX_PAGE_SIZE: int = 200
CONVERSATION_CACHE_TTL: int = 60
CONVERSATION_MESSAGE_CACHE_TTL: int = 30
```

---

## Database Models

### `swx_conversation`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `title` | String(500) | Optional conversation title |
| `status` | String(20) | active, archived, deleted |
| `metadata_` | JSONB | Arbitrary metadata |
| `user_id` | UUID | FK to swx_users |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `swx_conversation_message`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `conversation_id` | UUID | FK to swx_conversation |
| `role` | String(20) | user, assistant, system |
| `content` | Text | Message content |
| `token_count` | Integer | Optional token count |
| `model` | String(100) | Optional model identifier |
| `metadata_` | JSONB | Arbitrary metadata |
| `parent_message_id` | UUID | FK to swx_conversation_message (threading) |
| `created_at` | DateTime | Creation timestamp |

---

## Conversation Management

```python
from swx_core.services.conversation.conversation_service import (
    create_conversation,
    get_conversation,
    list_conversations,
    update_conversation,
    archive_conversation,
    delete_conversation,
)

# Create a conversation
conversation = await create_conversation(session, user_id, ConversationCreate(title="Support Chat"))

# Archive a conversation
conversation = await archive_conversation(session, conversation_id, user_id)

# Soft-delete a conversation
conversation = await delete_conversation(session, conversation_id, user_id)
```

Conversation statuses: `active` → `archived` → `deleted`

---

## Message Management

```python
from swx_core.services.conversation.conversation_message_service import (
    add_message,
    get_message,
    list_messages,
    update_message,
)

# Add a message to a conversation
message = await add_message(session, conversation_id, ConversationMessageCreate(
    role="user",
    content="Hello, I need help!"
), user_id=user_id)

# List messages in a conversation
messages = await list_messages(session, conversation_id, user_id=user_id, skip=0, limit=50)
```

Messages support threading via `parent_message_id` for multi-turn conversations.

---

## API Endpoints

### Admin Endpoints (`/admin/conversations`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/conversations` | List all conversations |
| GET | `/admin/conversations/{id}` | Get conversation detail |
| GET | `/admin/conversations/{id}/messages` | List conversation messages |

### User Endpoints (`/user/conversations`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/conversations` | List own conversations |
| POST | `/user/conversations` | Create conversation |
| GET | `/user/conversations/{id}` | Get own conversation |
| PUT | `/user/conversations/{id}` | Update conversation |
| DELETE | `/user/conversations/{id}` | Soft-delete conversation |
| POST | `/user/conversations/{id}/archive` | Archive conversation |
| GET | `/user/conversations/{id}/messages` | List messages |
| POST | `/user/conversations/{id}/messages` | Add message |
| PUT | `/user/conversations/{id}/messages/{msg_id}` | Update message |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `conversation.created` | conversation_id, user_id | Conversation created |
| `conversation.updated` | conversation_id, user_id | Conversation updated |
| `conversation.archived` | conversation_id, user_id | Conversation archived |
| `conversation.deleted` | conversation_id, user_id | Conversation soft-deleted |
| `conversation.message_created` | conversation_id, message_id, role | Message added |
| `conversation.message_updated` | conversation_id, message_id | Message updated |

---

## Best Practices

1. **Use metadata for context** — Store LLM context, system prompts, and user preferences in `metadata_`
2. **Archive instead of delete** — Use `archive_conversation` before `delete_conversation` for audit trails
3. **Set appropriate page sizes** — Use `CONVERSATION_DEFAULT_PAGE_SIZE` for listing
4. **Use parent_message_id for threading** — Link assistant responses to user queries for context chains
5. **Monitor token counts** — Track `token_count` on messages to manage LLM context windows