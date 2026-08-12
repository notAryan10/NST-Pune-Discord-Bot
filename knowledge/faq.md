# NST FAQ

## What is NST?
Newton School of Technology (NST) is a technology-focused undergraduate education program offering a 4-year residential B.Tech in Computer Science & AI through partner universities.

## What degree do students receive?
Students receive the degree from the relevant university partner. NST's official FAQ states that the partner-university degrees are UGC-approved.

## How long is the program?
The undergraduate degree program is 4 years.

## Is NST residential?
Yes. NST describes the program as residential. Hostel requirements and policies can vary by campus and university.

## What is the admission process?
The standard process includes registration, NSAT where applicable, an interview, counselling/admission formalities, document verification, seat blocking, and joining the campus.

## Can I get a scholarship?
Yes. NST offers multiple scholarship categories. Scholarship eligibility and coverage depend on the specific scholarship and admission cycle.

## Is the curriculum the same across campuses?
NST's official FAQ says the curriculum is the same across campuses, while Bengaluru offers additional specialization options in areas such as AI, Robotics, and Tech Entrepreneurship.

## How does Discord verification work?
On this server, new members receive the `Unverified` role. Students can submit an eligible verification document using `!verify`. An authorized administrator reviews the submission and can approve or reject it.

## What documents can I upload for Discord verification?
The current NST-Bot accepts:
- PDF
- PNG

The actual document requirements are determined by the server administrators.

## Why am I still Unverified?
Possible reasons include:
- You have not submitted a verification request.
- Your request is still pending.
- Your submission was rejected.
- An administrator has not reviewed it yet.

For a personal status, NST-Bot can check the user's own MongoDB verification record if that feature is enabled.

## How do I check my verification status?
The current bot does not yet expose a dedicated status command. A future command such as `!status` or `/status` can be implemented.

## How do I set my batch?
After verification, use:

`!batch`

The bot asks for your full name and URN, then assigns the corresponding year role.

## Can I change my year role?
The current server implementation locks year roles after assignment. If the role is incorrect, contact an administrator.

## What year roles exist?
The current bot uses:
- Freshers
- 2nd Year
- 3rd Year
- 4th Year

## How do I join a club?
Check the current club announcements/recruitment information on the NST Discord server. Club recruitment and membership rules can vary by club.

## Where can I ask for help?
Use the server's designated help, academics, clubs, career, or general discussion channels. Replace this sentence with the actual channel names once the server structure is finalized.

## What should I do if I don't know where to ask?
Mention NST-Bot or use the server's help command. The bot should suggest the most relevant channel based on the question.

## Can NST-Bot approve my verification?
No. The AI assistant must never approve or reject users autonomously. Verification approval remains an administrator action.

## Can NST-Bot change my roles?
Only deterministic, permission-controlled bot commands should modify roles. The AI assistant should not have unrestricted role-management access.

## Can NST-Bot see another student's private information?
It should not disclose another student's verification, URN, documents, or private MongoDB data.

## Are the fees fixed?
No. Fees can vary by campus, admission cycle, scholarship, hostel selection, and university charges. Always verify current official figures.

## Are internship outcomes guaranteed?
No. NST publishes internship outcomes and case studies, but individual outcomes depend on student skills, performance, availability, and selection processes.

## How should the AI answer uncertain questions?
If the knowledge base does not contain enough information, the assistant should say so and direct the student to an official source, administrator, faculty member, or relevant Discord channel.

## Golden rule for NST-Bot
Never fabricate an NST policy, deadline, fee, academic rule, event, club announcement, contact, or personal student record.

Source: Official Newton School of Technology FAQ/admissions/student-life information and the current NST-Bot server implementation, accessed August 2026.
