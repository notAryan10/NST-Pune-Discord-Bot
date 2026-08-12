# NST Discord Verification

## Purpose
This document describes the verification workflow implemented by NST-Bot for the NST Discord server.

## New member
When a member joins the server, NST-Bot attempts to assign the `Unverified` role.

A member with the `Unverified` role is not considered a confirmed student on the server.

## Document verification
A user can submit a verification document using:

`!verify`

The command expects an attachment.

### Accepted formats
- PDF (`.pdf`)
- PNG (`.png`)

The bot checks:
- The user is not already `Confirmed Student`.
- The user currently has the `Unverified` role.
- The user does not already have a pending verification request.
- The submitted file has an allowed extension.
- The verification queue channel exists.

The submission is posted to the configured `verification-queue` channel and stored in MongoDB.

The `verification-queue` channel is **admin-only**. Students cannot see it and cannot check their status there. After submitting, a student simply waits for the DM telling them whether they were approved or rejected.

## Verification statuses
A verification record can have statuses such as:
- `pending`
- `approved`
- `rejected`

## Approval
Authorized moderators can use:

`!approve @user`

On approval:
- `Confirmed Student` is assigned.
- `Unverified` is removed.
- The MongoDB record is marked approved.
- The reviewer and review time are recorded.
- The user receives a confirmation DM when possible.

## Rejection
Authorized moderators can use:

`!reject @user [reason]`

On rejection:
- The MongoDB record is marked rejected.
- The reviewer, review time, and reason are stored.
- The user receives a DM when possible.

## Important privacy rule
Verification documents and personal information are sensitive. NST-Bot should not expose another student's submitted document, URN, or verification record through the AI assistant.

If a student asks about their own verification status, the bot may use their Discord ID to check their own record.

If a student asks about somebody else's verification, the bot should refuse and direct them to an administrator.

## AI assistant behavior
The AI assistant must never approve or reject a verification request on its own. Approval and rejection remain explicit administrator commands.

Source: NST-Bot implementation and server workflow.
