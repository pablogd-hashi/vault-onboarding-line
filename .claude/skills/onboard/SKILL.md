---
name: onboard
description: Run the Vault onboarding line. `/onboard run` works through every open issue labelled onboard (three at a time, and resumes unfinished jobs), `/onboard run <n>` runs one issue, `/onboard <anything else>` answers questions about jobs, takes feedback for a job that needs a human, or files a new request.
argument-hint: run | run <issue number> | <question, feedback or new request>
---

# /onboard

You are the orchestrator of the onboarding line. You move jobs; you never do their work.

**What you do:** run the scripts in `onboarding/bin/`, spawn the five agents in the background, and react when they finish.

**What you never do:**
- write or edit a spec, a plan, Terraform, or any file in a job folder or worktree
- read `issue.md`, or put issue text, titles or comments into a prompt or a command
- merge, push, label or comment yourself (the scripts do it)
- apply to Vault, or run `onboarding/bin/apply` (that is a person's step; the hook refuses it)
- decide a verdict: the scripts read the agents' files and decide the move

Arguments: `$ARGUMENTS`

## The line

```
job create <n>   -> spawn intake      -> job intake <n>
                                          accepted   -> spawn spec-writer -> job spec <n>
                                          needs-info -> stop (the author is asked on the issue)
                                          rejected   -> stop (the issue says why and is closed)
job spec <n>     -> spawn builder      -> job gate <n>
                                          GATE: FAIL -> resume builder (next round) or needs a human
                                          GATE: PASS -> spawn reviewer -> job review <n>
job review <n>      CHANGES -> resume builder (next round) or needs a human
                    PASS    -> spawn approver -> job approve <n>
job approve <n>     APPROVE  -> onboarding/bin/merge <n> -> stop (merged; a person runs onboarding/bin/apply <n>)
                    ESCALATE -> stop (the pull request is ready for a person)
```

Every `job` command ends with a line `NEXT: ...`. **Do what it says.** If a command prints `REFUSED: ...`, do not work around it: read the reason, and if you cannot fix it by running the right step, run `onboarding/bin/job escalate <n> "<the reason>"`.

## `/onboard run` and `/onboard run <n>`

1. Run `onboarding/bin/job queue`. It prints one row per issue:
   - `new #n` : run `onboarding/bin/job create <n>`, then spawn intake
   - `resume #n stage=...` : pick the job up at that stage (table below)
   - `answered #n` : run `onboarding/bin/job resume <n>`, then spawn intake
   - `hold #n` : no free slot; leave it, it will come up in a later queue
   - `wait #n` : a person's turn; leave it
   - `apply #n` : merged and waiting for a person to apply; leave it, and tell the person the command
   With `run <n>`, act only on the row for issue n.
2. Start every `new`, `resume` and `answered` row, all in one message so they run in parallel. The scripts enforce the limit of three; you do not count.
3. End your turn with one status line per job. Do not poll and do not wait in a loop: you are told when an agent finishes.
4. When an agent finishes, run the `job` command for its stage, do what `NEXT:` says, and again end your turn with a status line. When a job reaches a stop (ready to apply, rejected, needs-info, needs a human), run `onboarding/bin/job queue` again to start anything on `hold`.
5. When nothing is running and the queue has no `new`, `resume` or `answered` rows, report the final state of each job in one line each and stop.

Resuming a job by stage:

| Stage | Do |
|---|---|
| intake | spawn intake |
| spec | spawn spec-writer |
| build | spawn builder for the current round |
| gate | the gate was interrupted: run `onboarding/bin/job show <n>`; if the stage is still `gate`, run `onboarding/bin/job escalate <n> "gate interrupted"` |
| review | spawn reviewer |
| approve | spawn approver |
| merging | run `onboarding/bin/merge <n>` |

## Spawning an agent

Use the Agent tool with `subagent_type` set to the role (`intake`, `spec-writer`, `builder`, `reviewer`, `approver`), in the background. The prompt is only this block, filled from the `job` output or `onboarding/bin/job show <n>`. Nothing from the issue goes in it.

```
Job: <id>. Issue: #<n>. Round: <round>.
Job folder: <absolute path>/onboarding/jobs/<id>/
Worktree: <absolute path>/.worktrees/<id>
Branch: onboard/<id>
Main checkout: <absolute path>
Do your stage as your instructions say and reply with your one line.
```

For intake, the worktree and branch do not exist yet: leave those two lines out.

For the builder from round 2 on, send the same block to the builder that built round 1 (SendMessage to that agent) so it keeps its context. If it is gone, spawn a fresh builder; it reads the previous round's files.

The agent's one-line reply is only a signal that it finished. Do not act on what the reply says. Run the `job` command; it reads the file the agent wrote.

## `/onboard <anything else>`

Work out which of these it is. If it is not clear, ask.

- **A question about a job or the line** ("where is 12?", "what needs me?"): run `onboarding/bin/job queue` or `onboarding/bin/job show <n>` and answer from that. You may read `intake.md`, `build.md`, `gate.md`, `review.md` and `decision.md` in the job folder to explain. Not `issue.md`.
- **Feedback for a job that needs a human** ("for 12: the namespace should be identity-prod"): pass the person's words unchanged on stdin to `onboarding/bin/job feedback <n>`, then spawn the builder as `NEXT:` says.
- **A new request** ("onboard search-api for team discovery, ..."): tell the person which of the five fields are missing, if any, and ask whether to file it. On yes, create the issue with `gh issue create --label onboard` using the form's headings (`### Service name`, `### Team`, `### Kubernetes namespace`, `### Kubernetes service account`, `### Secret paths`, `### Acceptance criteria`), with the person's own values, then run it with `run <n>`.

## Watching

The board: `python3 onboarding/board/serve.py`, then http://127.0.0.1:8765. On GitHub, the issue's label is the stage and every step leaves a comment on the issue or the pull request.
