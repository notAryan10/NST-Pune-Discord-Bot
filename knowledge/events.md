# NST Events

## Overview
NST conducts technical, career, founder, community, and student-life events.

Examples of event types include:
- Technical workshops
- Coding sessions
- Founder talks
- Career sessions
- Hackathons
- Community events
- Club events
- Guest lectures

## Current event information
Event dates, times, venues, registration links, and eligibility are dynamic.

NST-Bot should prefer current Discord announcements or an official NST event source when answering questions about a specific event.

## Event questions
For questions such as:
- "What events are happening this week?"
- "When is the next hackathon?"
- "Where is today's workshop?"
- "How do I register?"

the bot should retrieve current event information if it has access to it.

If no current event data is available, it should say that it cannot verify the latest schedule rather than guessing.

## Event reminders
The server may maintain event channels such as:
- `#events`
- `#announcements`
- Club-specific event channels

Replace these placeholders with the actual channel names used by the server.

## Bot behavior
The AI assistant may summarize an event announcement but should preserve:
- Date
- Time
- Venue
- Registration requirement
- Eligibility
- Organizer
- Important links

It must not fabricate any of these details.

Source: Official Newton School of Technology events/student-life information and the NST Discord server configuration.
