# NST Discord Verification

## Purpose
This document describes the verification workflow implemented by NST-Bot for the NST Discord server.

## New member
When a member joins the server, NST-Bot assigns the `Unverified` role. A member with the `Unverified` role is not yet a confirmed student.

## How a student verifies
A student runs this command in the server:

`!verify`

NST-Bot then continues the conversation **in DMs**, because a URN contains the student's date of birth and should not be typed into a public channel.

In DMs the bot asks for two things:
1. The student's **URN** (for example `2024-B-13072005B`)
2. The student's **full name**, as the college has it

The bot checks both against the official student list imported from the college roster.

If the bot cannot DM the student, verification cannot proceed. The student needs to enable **Settings → Privacy → Direct Messages** for this server and run `!verify` again.

## What happens next
- **Name matches the roster** — the student is verified immediately. `Confirmed Student` is assigned, `Unverified` is removed, and the correct year role is assigned automatically.
- **Name is close but not certain** — the request goes to admins for review. The student gets a DM once it is decided.
- **Name does not match** — the student is asked to check their spelling and try again.
- **URN is not on the roster** — the student should check their ID card, and contact an admin if the URN is definitely correct.

Because the year role is assigned from the roster, a verified student does **not** need to run `!batch` afterwards.

## One account per student
Each URN can only ever verify one Discord account. If a URN has already been used, the bot refuses and notifies an admin. A student who has genuinely lost access to their old account should contact an admin.

## Attempt limits
Repeated failed attempts temporarily lock a student out of verification. This protects other students, since URNs follow a predictable pattern. A locked-out student can try again later or contact an admin.

## Verification statuses
A verification record can have these statuses:
- `pending` — waiting for an admin to review
- `approved`
- `rejected`

## Admin commands
Authorized moderators review anything the bot was not confident about:

`!approve @user`

`!reject @user [reason]`

On approval the student gets their roles and a confirmation DM. On rejection the reason is stored and DMed to the student. The reviewer and the review time are recorded either way.

The `verification-queue` channel is **admin-only**. Students cannot see it and cannot check their status there — they simply wait for the DM.

## Important privacy rule
Verification documents and personal information are sensitive. NST-Bot must not expose another student's URN, name, or verification record through the AI assistant.

If a student asks about their own verification status, the bot may use their Discord ID to check their own record.

If a student asks about somebody else's verification, the bot should refuse and direct them to an administrator.

The bot must never reveal the name attached to a URN. A student who submits a URN that is not theirs is told only that the name did not match.

## AI assistant behavior
The AI assistant must never approve or reject a verification request on its own. Approval and rejection remain explicit administrator commands.

Source: NST-Bot implementation and server workflow.
