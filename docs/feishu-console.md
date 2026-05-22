# Feishu Console Setup

Create two Feishu custom apps. Keep the app secrets private.

## Mini Bot App

Purpose: receive all group messages, files, and useful context. It should use a
fast model and decide whether to reply.

Required settings:

- Add bot capability.
- Enable event subscription for receiving messages.
- Subscribe to `im.message.receive_v1`.
- Request and publish group all-message permission:
  - scope often shown as `im:message.group_msg`
  - permission name similar to "receive all messages in group chats"
- Configure data permission ranges as required by the Feishu console.
- Publish a new app version after changing scopes.

## Deep Bot App

Purpose: handle direct @ mentions with a stronger model.

Required settings:

- Add bot capability.
- Enable event subscription for receiving messages.
- Subscribe to `im.message.receive_v1`.
- Add this bot to the same group.
- Keep all-message group receive disabled for this app unless intentionally needed.

## Group Routing Model

Use two different bot apps:

- mini app: `group_reply_all = true`
- deep app: `group_reply_all = false`

Both projects should use:

- `thread_isolation = true`
- `reply_to_trigger = true`

This means different root messages/reply chains become different agent sessions,
and Feishu replies continue the correct session.
