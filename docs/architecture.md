# Architecture

## The problem

Onboarding a service to Vault is the same small change every time: one policy, one Kubernetes auth role, a few secret paths. It is easy to do and easy to get subtly wrong, and a wrong one hands a service someone else's secrets. That makes it a good job for a machine and a bad job to approve by skimming.

This repository lets agents do the work and removes the human approval. That is only acceptable because approval is replaced by something stricter than a skim: a gate that proves, on a real Vault, what the new policy can and cannot do.

## Three kinds of parts

| Part | Does | Trusted to |
|---|---|---|
| Agents (`.claude/agents/`) | Judgement and writing: is this request sane, what does the spec say, does the PR match the issue | Nothing. Each writes one file; a script reads it. |
| Scripts (`onboarding/bin/`) | Everything deterministic: state, labels, comments, the gate, the merge | Everything that matters. |
| The hook (`.claude/hooks/guard.py`) | Refuses tool calls that break a rule | Stopping mistakes and casual misuse. |

The orchestrator (the `/onboard` skill) only connects them: it runs a script, spawns the agent the script names, and runs the next script when the agent finishes. It writes no spec and no code, and it never reads the issue text.

## A job, stage by stage

State lives in `onboarding/jobs/<id>/job.json`. Only `onboarding/bin/job` writes it. Allowed moves:

```
intake ──→ spec ──→ build ──→ gate ──→ review ──→ approve ──→ merging ──→ merged
  │                   ▲         │         │           │           │
  ├→ needs-info ──────┘(intake) └─────────┴→ build    └───────────┴→ needs-human
  └→ rejected                     (next round, or needs-human after round 3)
```

A move also needs evidence, read from files and from git, not from what an agent says:

| Move | Evidence |
|---|---|
| intake → spec | `intake.md` starts with `DECISION: accepted` and names a valid service |
| spec → build | the spec file exists and has R1 to R5 |
| build → gate | `build.md` says READY, the branch is pushed, exactly one open PR |
| gate → review | the gate script exited 0 and wrote `GATE: PASS` |
| review → approve | `review.md` says PASS for the commit the branch is at |
| approve → merging | `decision.md` says APPROVE and the round's gate and review are PASS |
| merging → merged | the merge script's own gate passed and GitHub merged the PR |

Each job has its own git worktree (`.worktrees/<id>`) and branch (`onboard/<id>`), so three jobs run side by side without touching each other. The script refuses a fourth.

## The trust boundary

The issue text is the only thing in the system written by a stranger.

- Only issues labelled `onboard` run. Adding a label needs triage rights on the repository.
- The script saves the issue to `issue.md` as quoted text under a notice that it is data. Only the author's and the operator's comments are included.
- Nothing pastes issue text into a prompt. Agents are told where the file is.
- Intake, the first reader, has no shell. The builder never reads the issue, only the spec.
- Whatever an agent is talked into, it can only produce one new request folder, and that folder must pass the gate.

## Why the gate cannot be argued with

- **Read from the main checkout.** The script, the policies, the module and the template that judge a branch are the main checkout's copies, and in line mode they must be identical to `origin/main`. A branch cannot bring its own judge.
- **Shape before execution.** `main.tf` must be the template with five values changed, and the values must match fixed patterns. Only then does Terraform run. Arbitrary HCL never reaches `terraform init`.
- **Policy as parsed text.** Conftest reads the plan JSON, pulls every `path` stanza out of the Vault policy, and judges each path and each capability. Unparsed leftovers fail. Missing or unknown values fail.
- **Behaviour, not belief.** The request is applied to a throwaway Vault. A token with only the new policy must read its own paths and must be refused, with a real HTTP 403 `permission denied`, on write, delete, a sibling service, another team and `sys/`. The secrets it must not reach are created first, so "not found" cannot pass for "denied".
- **No skips.** A tool that is missing or a check that cannot run fails the gate.
- **Twice.** The merge script syncs the branch with main and runs the gate again, because another job may have merged the same service in the meantime.

## What the hook does and does not do

The hook stops an agent or a session from merging, pushing outside `onboard/*`, force pushing, aiming Terraform or Vault writes at anything but 127.0.0.1, and (for agents) editing anything except its job folder and its request folder. A crash in the hook refuses the call.

Its shell rules match command text, so they are a strong guard against mistakes, not a sandbox. The defence that does not depend on pattern matching is the gate reading its judges from the main checkout and comparing them with `origin/main`.

The main session is deliberately not restricted from editing the gate, otherwise nobody could maintain it. Changes to the line go through their own branch and pull request, made by a person.

## Limits

- The gate needs the network the first time it runs, to download the Vault provider. After that it uses a local cache.
- The line handles one shape of request. Anything that needs a change to the module, the platform layer or the policies is rejected at intake and done by a person.
- The line never applies to a shared Vault. Getting a merged request into a real environment is a separate, human step.
- Merge conflicts are not resolved by the line; they escalate.
