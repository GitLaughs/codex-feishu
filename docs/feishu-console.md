# Feishu Console Setup

Create two Feishu custom apps. Keep the app secrets private.

## Mini Bot App

Purpose: receive all group messages, files, and useful context. It should use a
fast model and decide whether to reply.

Import the permission template:

```text
templates/feishu-mini-scopes.json
```

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

Import the permission template:

```text
templates/feishu-deep-scopes.json
```

Required settings:

- Add bot capability.
- Enable event subscription for receiving messages.
- Subscribe to `im.message.receive_v1`.
- Add this bot to the same group.
- Keep all-message group receive disabled for this app unless intentionally needed.

## Permission Template Notes

Open the app console directly with:

```text
https://open.feishu.cn/app/<app_id>
```

Then go to Permissions, import the matching JSON template, configure any data
permission range requested by the console, and publish a new version.

The templates include common group features:

- send and read bot messages
- download message files and images
- read and update chat metadata
- read and manage chat members
- read and write classic chat announcements
- upload and download Drive files used by group workflows

The mini template also includes `im:message.group_msg`. The deep template does
not include it, so deep stays @-only by default.

Feishu may return `Unable to operate docx type chat announcement` for newer
Docx-style group announcements. That means scope is granted, but the current
announcement format is not supported by the classic announcement OpenAPI.

## Group Routing Model

Use two different bot apps:

- mini app: `group_reply_all = true`
- deep app: `group_reply_all = false`

Both projects should use:

- `thread_isolation = true`
- `reply_to_trigger = true`

This means different root messages/reply chains become different agent sessions,
and Feishu replies continue the correct session.
