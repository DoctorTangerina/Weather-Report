# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in Esduard/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Domain labels

Separate from the triage roles, every issue carries one or more domain labels saying which part of the project it touches. An issue that spans domains gets each label that applies.

| Label      | Meaning                                                        |
| ---------- | -------------------------------------------------------------- |
| `Data`     | Data domain: acquisition, catalogs, statistics and the analysis engine |
| `Frontend` | Frontend domain: UI screens and user experience                |
| `Backend`  | Backend domain: API, results service and server-side logic     |
