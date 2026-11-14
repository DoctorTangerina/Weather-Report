# Autonomous Discovery Engine

A tool that analyzes NASA Earth science time series, finds notable contrasts between regions by itself, and turns them into investigations that teach students about trends and statistical evidence. The original challenge text is in `docs/challenge-brief.md`.

## Language

**Region**:
A named geographic area from a curated catalog, with a short plain-language description.
_Avoid_: Area, zone, location, cell

**Region catalog**:
The fixed list of Regions the engine and the user can choose from. Users cannot define a Region outside it.
_Avoid_: Region list, atlas

**Variable**:
A measured or modeled Earth science quantity (e.g. temperature, precipitation) with a plain-language definition.
_Avoid_: Metric, parameter, indicator

**Variable catalog**:
The fixed list of Variables the engine and the user can choose from, each with its NASA source, units and plain-language definition. Users cannot add a Variable outside it.
_Avoid_: Variable list, dataset list

**Trend**:
The direction and rate of change of one Variable over one Region across a period, together with its uncertainty and statistical significance.
_Avoid_: Slope, change, tendency

**Evidence label**:
The plain-language rating of how strongly the data support a Trend or Discovery: Strong evidence, Some evidence, or Not enough evidence yet. Shown to students.
_Avoid_: Confidence level, grade, p-value badge

**Mirror**:
Two Region–Variable series, possibly of different Variables in different Regions, that move together or in opposite directions month to month beyond what chance explains.
_Avoid_: Correlation pair, teleconnection

**Discovery**:
A pair of Regions whose Trends or Mirrors, on one or more Variables, contrast in a way the engine scores as notable.
_Avoid_: Finding, insight, result

**Candidate Discovery**:
A Discovery the engine has found and scored but not yet selected for presentation to a user.
_Avoid_: Proposal, lead

## Experiences

**Weather Detective Hub**:
The community and learning experience where users share findings made with the app, discuss them, and work through educational tasks.

**Community post**:
A registered user's publication about results, patterns, or dependencies found using the app's features, including questions seeking scientific explanations. The author chooses which charts and explanations to include; a post is distinct from an engine-selected Discovery and can receive discussion, likes, and dislikes.

**Community leaderboard**:
A ranking of users based on likes and dislikes received on their published Community posts, with dislikes subtracting from the score. Deleting a post removes its votes from the author's score.

**Educational leaderboard**:
A separate ranking of users by points earned for solving Educational tasks. Each task has a moderator-defined point value and a difficulty of Easy, Medium, or Difficult.

**Answer submission**:
A registered learner's answers to task-author-defined structured fields, checked against accepted values and numeric tolerances, with optional explanation and charts. A submission awaiting Alternative solution review earns no points until accepted; acceptance also triggers grading of other matching submissions.

**Accepted answer rule**:
The accepted values or numeric tolerances used to check structured answers for an Educational task. Accepting an Alternative solution can extend these rules and trigger automatic rechecking; submissions requiring scientific interpretation remain subject to human review.

**Practice completion**:
Completion of an Educational task after revealing its full solution, which earns no educational leaderboard points. Hints do not reduce points.

**Task family**:
An Educational task and its revisions, sharing a single base-point award per learner. A genuinely different problem is a new task rather than a revision.

**Submission eligibility**:
A learner's eligibility for base task points and a Novelty bonus, recorded when an answer or Alternative solution is submitted. Subsequent solution reveals do not invalidate that submission's eligibility.

**Novelty bonus**:
Additional points awarded to learners whose submissions demonstrate the same new Alternative solution and arrive before its official acceptance. These learners receive both base task points and the bonus; later matching submissions receive base points only. Task point amounts and bonus amounts remain to be defined.

**Solution spoiler**:
Hidden solution content in a Community post linked to an Educational task, requiring sign-in to reveal. Revealing it removes Novelty bonus eligibility for subsequent submissions to that task, while revealing the official Verified solution removes all point eligibility for subsequent submissions.

**Post discussion**:
A chronological group-chat-style conversation attached to one Community post, with messages and replies to specific messages.

**Educational task**:
A learning problem created by a dedicated team that registered users investigate at their own pace and submit answers to for checking. Tasks use only implemented app features, require no coding, and provide hints and a verified solution on request at any time.
_Avoid_: Challenge, issue, competition

**Hint**:
Guidance available on request at any time during an Educational task that suggests an investigative action, such as building a correlation map, comparing two series, or scaling data.

**Verified solution**:
A team-verified solution prepared for an Educational task, including an explanation of how to reach it and available whenever the learner requests it.
_Avoid_: Best solution, competitive baseline

**Alternative solution**:
A learner's proposed solution that differs from an Educational task's existing verified solutions and is submitted with a full explanation for the Validation team to judge. The learner may also share it in a Community post.

**Validation team**:
The educational reviewers who assess Alternative solutions for acceptance as valid solutions to Educational tasks, with their own permissions independent of community content moderation. The team's implementation is deferred to the far future.

**Surprise Me!**:
The experience where the engine selects a Discovery automatically and presents it to the user with the two Regions highlighted on a map and a thought-provoking question.

**Become a Detective**:
The experience where the user investigates a Discovery by comparing charts, answering hypothesis questions, and reading explanations of what the data indicate.

**How do we know?**:
The part of an investigation that shows the NASA source, the period analyzed, and the statistical assessment in plain language.

**Explore My World**:
A later experience where the user freely chooses any region of the planet, beyond the Region catalog. Not part of the MVP.
