# Publication failure

Configured tracker: GitHub, DoctorTangerina/Weather-Report, task #14.
Command attempted: gh issue view 14 --repo DoctorTangerina/Weather-Report --comments --json number,title,body,labels,comments
Working directory: C:/Users/ADM/Documents/Weather-Report/frontend
Execution: functions.exec -> exec_command, require_escalated.
Exit code: 1.
Result: gh is not recognized as a command. Exact execution UTC was not captured; failure occurred earlier in this same evidence turn.

Authentication presence checks: neither standard gh hosts.yml path exists, and neither GH_TOKEN nor GITHUB_TOKEN is set. No secret values were read or printed.

The task is confirmed from the issue text supplied by the user in this conversation. Remote existence and idempotency-marker lookup could not be confirmed. No external publication or duplicate-producing retry was attempted. Tracker mode remains github; this is a local recovery copy, not a reclassification to local mode.
