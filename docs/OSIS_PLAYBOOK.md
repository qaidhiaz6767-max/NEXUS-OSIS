# OSIS Chief of Staff — practical operating playbook

This playbook turns a useful local tool into a consistent working habit for a student council president. Every example below uses fictional work and committee role labels, not classmates' personal records.

## 1. The three questions for every command

1. **What outcome do I need?** ("Prepare a meeting", not merely "do something".)
2. **What information do we actually know?** (Verified day/time, adviser clearance, budget and role assignments.)
3. **What may NEXUS do without asking?** (Read and draft, yes; save, send or publish, only after appropriate authorization.)

## 2. Daily rhythm

**Start of day (3–5 minutes):** open NEXUS and type `/brief`. Identify one urgent item, one important item, and one follow-up. Don't create a massive to-do list.

**After a committee discussion:** record only approved and non-sensitive decisions. Turn each next action into a task with one accountable role, a realistic deadline and an explicit confirmation step.

**End of day:** `/tasks`, mark your own completed items, verify the status of delegated items through appropriate real-world channels, prepare one short follow-up for next day.

## 3. Weekly leadership rhythm

| Moment | NEXUS output | Human check |
|---|---|---|
| Before weekly meeting | Draft agenda, priorities, delayed tasks | Are dates, facts and owners accurate? |
| During meeting | Typed notes, draft decisions (future module) | Did the group actually agree? |
| Immediately after | Proposed action items | Review/approve records |
| Midweek | Outstanding work by committee | Have owners actually acknowledged? |
| Friday | Executive weekly summary | Communicate officially through approved school channels |

## 4. Event preparation command script

In the current prototype, use explicit offline commands, e.g.:

```text
/event add OSIS creativity showcase | 2026-12-04 | 13:30 | School hall | Planning date, not yet approved
/task add Draft concept note | Program committee | 2026-11-13 | high
/task add Request venue availability | Logistics committee | 2026-11-14 | high
/task add Draft proposed budget | Treasurer role | 2026-11-17 | medium
/task add Prepare rehearsal checklist | Stage committee | 2026-12-01 | medium
/note add Event assumptions | Dates and budget must be confirmed with adviser.
```

Approving these saves them *inside NEXUS only*. No committee member is actually contacted.

**Future project charter (v0.2):**

```text
Project title:
Executive owner:
Purpose / school benefit:
Scope and exclusions:
Tentative event date:
Approval authority / adviser:
Budget estimate and funding source:
Committees / responsible roles:
Milestones and gates:
Risks and fallback:
Document links (authorized only):
Next review date:
```

## 5. Suggested committee workstreams

- Program/content: program concept, criteria, judging/rules, MC, participant experience.
- Operations/logistics: venue, seating, stage, sound, supplies, rehearsal plan.
- Creative/publication: poster, run-of-show visual, materials, final approved broadcast.
- Finance: cost plan, procurement records, school approval and reconciliation.
- Documentation: photos/video only with school policy and subject consent.
- Secretariat: meetings, minutes, permissions, official correspondence.
- Risk/safety: contingency, accessibility, crowd/venue coordination with authorized staff.

Use role labels rather than assuming named students consent to their data being stored.

## 6. Meeting agenda template

```text
MEETING: [event / weekly OSIS meeting]
Date/time/venue: [confirmed?]
Chair: [role]
Purpose: [decision required]

1. Status and important updates (5 min)
2. Decisions needed (10 min)
3. Overdue or blocked work (10 min)
4. Financial / logistical dependencies (5 min)
5. Next actions, owners and deadlines (10 min)
6. Confirm next review

Decisions actually agreed:
- ...
Action items proposed for approval:
- [role] — [specific action] — [date]
Unknowns / follow-up questions:
- ...
```

## 7. Broadcast drafting instruction (AI mode only)

Ask: "Draft a warm, energetic, professional broadcast in mostly Indonesian with some natural English. Audience: OSIS committee members. Purpose: reminder about [publicly approved event]. Facts confirmed: [date, time, venue]. Don't invent facts and don't send it."

Then review manually. Current NEXUS cannot send messages. Avoid pasting private phone numbers or chat lists.

## 8. Decision-log discipline

Write a decision only once it is actually taken by the appropriate people. Record **decision statement**, **date**, **approving body/role**, **reason**, **scope**, **review date** and **superseded?**. In a future NEXUS schema, model suggestions and committee decisions must be distinct record types. A proposed budget isn't an approved budget.

## 9. Delegation language

Use: *"Propose assigning the design draft to the publications committee with a Wednesday deadline."*  
Avoid: *"Tell everyone they must do this"* unless you have confirmed the approved message, proper channel and school authority. NEXUS is a coordination tool, not an authority over other people's accounts or decisions.

## 10. End-of-term handover

Capture lessons learned and reusable non-sensitive event workflows; separate them from private council discussions. Get adviser review before sharing materials beyond your personal workspace. A future ATLAS use case should use its own clean data store and workflows.
