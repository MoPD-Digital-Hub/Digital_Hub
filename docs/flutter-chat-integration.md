# Digital Hub Chat — Flutter Integration Guide

How to integrate the user-to-user chat module: REST API, live updates over WebSocket, and FCM push notifications with server-side suppression.

## 1. Architecture at a glance

- **Send over REST.** Messages are created with `POST /api/chat/conversations/<id>/messages/`. The response contains the persisted message (with its id) — treat that as the source of truth.
- **Receive over WebSocket.** One socket per logged-in user at `ws/dm/` carries events for *all* of the user's conversations: new messages, read receipts, typing.
- **Push via FCM.** When a recipient isn't looking at the conversation, the backend pushes to every device token the app has registered. If the recipient's socket says they're focused on that conversation, **the server skips the push** — the message still arrives instantly on the socket.

```
Flutter app ── POST message ──▶ Django ──▶ channel layer ──▶ recipient's socket
                                  │
                                  └─▶ Celery ──(recipient not focused?)──▶ FCM push
```

## 2. Authentication

All REST calls use the existing JWT auth: `Authorization: Bearer <access_token>` (obtained via the existing OTP login flow under `/api/user/auth/`, refreshed at `POST /api/auth/token/refresh/`).

Every chat endpoint responds with the standard envelope:

```json
{ "result": "SUCCESS", "message": "SUCCESS", "request_id": "…", "data": … }
```

Failures use `"result": "FAILURE"` with `error: { code, message, details }`. Machine-readable codes you will encounter: `USER_ID_REQUIRED`, `USER_ID_INVALID`, `SELF_CONVERSATION`, `USER_NOT_FOUND`, `CONVERSATION_NOT_FOUND`, `EMPTY_MESSAGE`, `BEFORE_INVALID`, and for groups: `TITLE_REQUIRED`, `USER_IDS_REQUIRED`, `USER_IDS_INVALID`, `NOT_GROUP`, `NOT_ADMIN`, `PARTICIPANT_NOT_FOUND`, `TOO_MANY_MEMBERS`.

## 3. Device registration (required for push)

Register the FCM token after login **and** whenever `FirebaseMessaging.onTokenRefresh` fires. Remove it on logout, before discarding the JWT.

| Method | Endpoint | Body |
|---|---|---|
| POST | `/api/notification/devices` | `{ "token": "<fcm_token>", "platform": "android" \| "ios" \| "web" }` |
| DELETE | `/api/notification/devices` | `{ "token": "<fcm_token>" }` |

Registration is idempotent — re-posting the same token just re-binds it to the current user. Tokens FCM reports as dead are pruned server-side automatically.

> The old broadcast notifications still use the `all_devices` topic; chat pushes are targeted per device token and need this registration.

## 4. REST API

Base path: `/api/chat/`

### List chat users

`GET /api/chat/users/?search=<query>`

All active users except yourself — the "start a new chat" picker. Optional `search` filters by first name, last name, or email (case-insensitive contains). Each item is the standard user shape:

```json
{ "id": 7, "first_name": "Abebe", "last_name": "Bekele", "email": "…", "photo": "…", "excellence": "Mr" }
```

### List conversations

`GET /api/chat/conversations/`

Returns conversations sorted by most recent activity. Each item:

```json
{
  "id": 12,
  "type": "direct",
  "title": null,
  "created_by": null,
  "other_participants": [
    { "id": 7, "first_name": "Abebe", "last_name": "Bekele", "email": "…", "photo": "…", "excellence": "Mr" }
  ],
  "last_message": { "id": 90, "sender": { … }, "body": "See you then", "attachment": null, "created_at": "…", "edited_at": null },
  "unread_count": 3,
  "is_muted": false,
  "my_role": "member",
  "participant_count": 2,
  "created_at": "…",
  "updated_at": "…"
}
```

For a group conversation, `type` is `"group"`, `title` is the group name, `created_by` is the creator's user id, `other_participants` lists everyone but you, and `my_role` is `"admin"` or `"member"`. Display name for the UI: `title` for groups, the other participant's name for direct chats.

### Start (or fetch) a direct conversation

`POST /api/chat/conversations/` with `{ "user_id": 7 }`

Returns the conversation in the same shape. `201` if newly created, `200` if it already existed — a DM pair is never duplicated, so this call is safe to make every time the user taps a person.

### Create a group

`POST /api/chat/conversations/` with `{ "type": "group", "title": "Team Alpha", "user_ids": [7, 9, 12] }`

The creator becomes the group's **admin**; everyone in `user_ids` joins as a member (your own id is ignored if included). At least one other member is required; max 100 members. Returns `201` with the conversation.

### Group management

| Method | Endpoint | Who | Effect |
|---|---|---|---|
| GET | `/conversations/<id>/` | any member | Fetch one conversation |
| PATCH | `/conversations/<id>/` with `{ "title": "…" }` | admin | Rename the group |
| POST | `/conversations/<id>/participants/` with `{ "user_ids": [...] }` | admin | Add members (already-present ids are ignored) |
| DELETE | `/conversations/<id>/participants/` with `{ "user_id": N }` | admin, or yourself | Remove a member / leave the group (`message: "LEFT_GROUP"`) |

Rules: non-admins get `NOT_ADMIN`; these endpoints return `NOT_GROUP` on direct conversations; if the last admin leaves, the longest-standing member is auto-promoted. Every change broadcasts a `conversation.updated` socket event (see below) to all affected users — including a removed user, so their client can drop the conversation.

### Message history (cursor pagination)

`GET /api/chat/conversations/<id>/messages/?limit=30&before=<message_id>`

Newest first. Response data:

```json
{ "messages": [ … ], "has_more": true, "next_before": 61 }
```

Load the first page with no `before`; pass `next_before` to fetch older messages when the user scrolls up. `limit` maxes out at 100.

### Send a message

`POST /api/chat/conversations/<id>/messages/`

- JSON: `{ "body": "Hello" }`
- or multipart with an optional `attachment` file (body may be empty if an attachment is present).

Returns `201` with the serialized message. Your own message is **also** echoed to your socket (`message.new`) — dedupe by message `id` so it isn't shown twice.

### Mark read

`POST /api/chat/conversations/<id>/read/` → `{ "last_read_at": "…" }`

You rarely need this: opening a conversation (`conversation.focus` on the socket) marks it read automatically. Use the REST call as a fallback (e.g. marking read from the conversation list without opening the chat).

## 5. WebSocket

**URL:** `wss://<host>/ws/dm/?token=<access_token>`
(Alternative for clients that must avoid query strings: pass WebSocket subprotocols `["bearer", "<access_token>"]`.)

- Missing/invalid/expired token → the server closes with code **4401**. On 4401, refresh the JWT and reconnect; don't retry blindly.
- Keep exactly **one** socket for the whole session (open it after login, close on logout). All conversations flow through it.
- Reconnect with exponential backoff on network loss; on reconnect, refetch the conversation list (and the open conversation's latest messages) to fill any gap.

All frames are JSON with a `type` field.

### Client → server

| Event | Payload | When |
|---|---|---|
| `conversation.focus` | `{ "type": "conversation.focus", "conversation_id": 12 }` | User opens a chat page |
| `conversation.heartbeat` | `{ "type": "conversation.heartbeat" }` | Every **~25 s** while the chat page stays open |
| `conversation.blur` | `{ "type": "conversation.blur" }` | User leaves the chat page (back, tab switch, app backgrounded) |
| `typing` | `{ "type": "typing", "conversation_id": 12, "is_typing": true }` | Throttled while the user types; send `false` on stop |

### Server → client

| Event | Payload |
|---|---|
| `message.new` | `{ "type": "message.new", "conversation_id": 12, "sender_id": 7, "message": { …full message… } }` |
| `message.read` | `{ "type": "message.read", "conversation_id": 12, "user_id": 7, "last_read_at": "…" }` |
| `typing` | `{ "type": "typing", "conversation_id": 12, "user_id": 7, "is_typing": true }` |
| `conversation.updated` | `{ "type": "conversation.updated", "conversation_id": 12, "action": "created" \| "renamed" \| "members_added" \| "member_removed" \| "member_left", … }` |

`message.read` means: that user has read everything up to `last_read_at` — use it to flip your sent-message ticks. In groups it fires per member, keyed by `user_id`.

`conversation.updated` means the conversation changed shape — refetch it (`GET /conversations/<id>/`) or the whole list. `renamed` carries `title`; `members_added` carries `user_ids`; `member_removed`/`member_left` carry `user_id`. If *you* are the removed `user_id`, drop the conversation locally (subsequent API calls for it will 404).

## 6. Focus lifecycle & push suppression

The focus events are what stop users getting a push for a conversation they're already looking at:

1. `conversation.focus` writes a 60-second presence key on the server (and marks the conversation read, emitting `message.read` to the other side).
2. Heartbeats every ~25 s keep it alive. Typing events refresh it too.
3. `conversation.blur` (or a socket disconnect) clears it. If the app is killed and nothing is sent, the key simply **expires within 60 s** — a stale focus can never permanently swallow notifications.
4. While focused, incoming messages on that conversation are auto-marked read — live read receipts with no extra client work.

Flutter specifics:

- Wire `AppLifecycleState`: on `paused`/`inactive` send `conversation.blur`; on `resumed` with a chat page on top, re-send `conversation.focus`.
- Suppression is server-side, but keep the cheap client-side guard as belt-and-braces: if a push arrives whose `conversation_id` equals the currently open chat, don't display a local notification.

## 7. Push payload

Chat pushes carry both a `notification` block (background display) and `data` (always delivered). All data values are strings:

```json
{
  "route": "/chat",
  "conversation_id": "12",
  "message_id": "90",
  "sender_id": "7",
  "title": "Abebe Bekele",
  "body": "See you then",
  "click_action": "FLUTTER_NOTIFICATION_CLICK"
}
```

On tap, deep-link to the conversation via `conversation_id`. Muted conversations (`is_muted`) never generate pushes; socket events still arrive.

For **group** messages the notification reads as `title` = group name, `body` = `"Sender Name: message preview"` — direct messages keep `title` = sender name, `body` = preview. The data payload shape is identical for both, so tap handling doesn't branch.

## 8. Suggested client skeleton

```dart
class ChatSocket {
  WebSocketChannel? _channel;
  int? _focusedConversationId;
  Timer? _heartbeat;

  void connect(String accessToken) {
    _channel = WebSocketChannel.connect(
      Uri.parse('wss://$host/ws/dm/?token=$accessToken'),
    );
    _channel!.stream.listen(_onEvent, onDone: _onClosed);
  }

  void focus(int conversationId) {
    _focusedConversationId = conversationId;
    _send({'type': 'conversation.focus', 'conversation_id': conversationId});
    _heartbeat?.cancel();
    _heartbeat = Timer.periodic(const Duration(seconds: 25),
        (_) => _send({'type': 'conversation.heartbeat'}));
  }

  void blur() {
    _heartbeat?.cancel();
    _focusedConversationId = null;
    _send({'type': 'conversation.blur'});
  }

  void _send(Map<String, dynamic> frame) =>
      _channel?.sink.add(jsonEncode(frame));
}
```

Checklist for a complete integration:

- [ ] Register FCM token on login + `onTokenRefresh`; DELETE on logout
- [ ] Open the socket after login; handle close code 4401 by refreshing the JWT
- [ ] `focus` / heartbeat / `blur` wired to chat page navigation **and** app lifecycle
- [ ] Dedupe `message.new` for your own sends by message id
- [ ] Cursor pagination with `next_before` on scroll-up
- [ ] Deep-link push taps via `data.conversation_id`
- [ ] Client-side push guard for the currently open conversation
