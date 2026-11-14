# Weather Detective Hub — agreed design

Status: design decisions recorded; awaiting final shared-understanding confirmation. This describes the future system; no implementation phase has been selected. Community posting and management, educational review tooling, and community content moderation are deferred. Educational review and content moderation are independent responsibilities with separate permissions.

## Community

Registered users may publish results, patterns, dependencies, and questions found using the app's features. Authors choose whether to include charts and explanations; reproducible analysis is not mandatory. Visitors may read; all participation, including solving tasks, requires registration.

Each post has a chronological group-chat-style discussion with replies to specific messages. There are no competitive challenges or coding submissions.

The community leaderboard ranks users by likes minus dislikes on their posts, rather than ranking posts or counting comment votes. Deleting a post removes its votes from the author's score.

Posts may link to educational tasks and hide solution content behind a spoiler reveal. Visitors must sign in to reveal linked task solution spoilers. Revealing a linked solution spoiler removes eligibility for that task's novelty bonus, but not its base points. Revealing the official task solution removes eligibility for all task points. Eligibility is recorded at submission time: subsequent reveals do not invalidate an already submitted solution's eligibility.

## Educational tasks

A dedicated team prepares tasks, hints, verified solutions, and explanations of how to reach them. Tasks may use any implemented app feature as soon as it becomes available, but may not depend on unimplemented features. Learners investigate at their own pace without writing code.

Task authors define structured answer fields, accepted values, and numeric tolerances. Ordinary submissions may include optional explanations and charts. Learners may submit unlimited attempts without point deductions. Hints are available at any time and do not reduce points. The full solution and explanation are also available on request; revealing them turns the task into practice with no leaderboard points.

The educational leaderboard is separate from the community leaderboard. Tasks are Easy, Medium, or Difficult, with moderator-defined point values. Actual point and bonus amounts will be decided later. Base points are awarded at most once per learner per task family, including all revisions. Points are fixed at publication; substantial changes to answers, difficulty, or scoring require a revised task rather than altering earlier achievements. Revisions do not award base points again; a genuinely different problem is a new task.

## Alternative solutions

Learners can submit an alternative solution with a full explanation for educational reviewers to judge, and independently choose to publish it in the hub. Pending review, submissions earn zero points.

Acceptance awards eligible learners task points and a novelty bonus. All learners whose submissions demonstrate the same new solution and arrive before official acceptance qualify for the bonus, subject to spoiler and official-solution eligibility rules. Later matching submissions earn base points only.

Reviewers extend accepted answer values or tolerances where possible, triggering automatic rechecking of matching submissions. Submissions requiring scientific interpretation remain in manual review. Educational reviewers have permissions independent of community content moderation; their tooling is deferred to future development.

## Deferred work

Implementation phases and exact point and bonus amounts will be defined later. Final confirmation of this shared design is required before implementation planning.
