# Architecture

## The problem

Onboarding a service to Vault is the same small change every time: one policy, one Kubernetes auth role and a few secret paths. A mistake in it can give a service access to another team's secrets, and a person who approves these changes all day stops reading them closely.

This repository lets agents do the work and removes the approval of each phase. What replaces it is a gate that applies the request to a throwaway Vault and tests what the new policy can and cannot do. One human step is left, at the end: the line merges the request and stops, and a person looks at what will be written to Vault and applies it.

## Who does what

There are three kinds of parts, and the difference between them is how much I trust each one.

| Part | What it does | What it is trusted with |
|---|---|---|
| Agents (`.claude/agents/`) | Judgement and writing: is the request valid, what does the spec say, does the pull request match the issue. | Nothing. Each agent writes one file and a script reads it. |
| Scripts (`onboarding/bin/`) | State, labels, comments, the gate, the merge, the apply. | Every decision that moves a job. |
| The hook (`.claude/hooks/guard.py`) | Refuses tool calls that break a rule. | Stopping mistakes. |

The `/onboard` skill is the orchestrator, and it does very little. It runs a script, starts the agent that the script names, and runs the next script when the agent finishes. It writes no spec and no code, and it never reads the issue text.

## How a job moves

The state of a job lives in `onboarding/jobs/<id>/job.json`, and `onboarding/bin/job` is the only thing that writes it. These are the moves it allows:

```
intake ──→ spec ──→ build ──→ gate ──→ review ──→ approve ──→ merging ──→ ready-to-apply ──→ applied
  │                   ▲         │         │           │           │
  ├→ needs-info ──────┘(intake) └─────────┴→ build    └───────────┴→ needs-human
  └→ rejected                     (next round, or needs-human after round 3)
```

A legal move is not enough. The script also wants evidence, and it reads that evidence from files and from git, never from what the agent replied. An agent can say whatever it likes in its one line, and the job still only moves if the file it wrote and the state of the branch agree.

| Move | Evidence |
|---|---|
| intake → spec | `intake.md` starts with `DECISION: accepted` and names a valid service |
| spec → build | the spec file exists and has R1 to R5 |
| build → gate | `build.md` says READY, the branch is pushed, there is exactly one open pull request |
| gate → review | the gate script exited 0 and wrote `GATE: PASS` |
| review → approve | `review.md` says PASS for the commit the branch is at |
| approve → merging | `decision.md` says APPROVE, and the gate and review of this round are PASS |
| merging → ready-to-apply | the merge script's own gate passed and GitHub merged the pull request |
| ready-to-apply → applied | a person ran the apply script, and `apply.md` starts with `APPLY: PASS` |

Each job works in its own git worktree, `.worktrees/<id>`, on its own branch, `onboard/<id>`, so three jobs can run at the same time without touching each other. The script refuses to start a fourth.

## Issue text is data

The issue is the only input written by someone outside the line, so I treat it the way I would treat any untrusted input.

Only issues labelled `onboard` run, and adding a label needs triage rights on the repository. The script saves the issue to `issue.md` as quoted text, under a notice that says it is data, and it includes only the comments of the author and of the operator. No prompt ever contains issue text. Agents are told where the file is and read it themselves.

Intake is the first to read it, and intake has no shell. The builder, which does have a shell, never reads the issue at all. It reads the spec. And whatever an agent might be talked into, the only thing it can produce is one new request folder, which then has to pass the gate.

## The gate

The gate is read from the main checkout. The script, the policies, the module and the template that judge a branch are the copies in the main checkout, and when a job runs they also have to be identical to `origin/main`. A branch cannot bring its own judge.

The shape of the file is checked before Terraform runs. `main.tf` has to be the template with five values changed, and each value has to match a fixed pattern. I did this because `terraform plan` on arbitrary HCL can run code, and I did not want anything an agent wrote to reach `terraform init` unless it is the template.

Conftest then reads the plan JSON, takes every `path` stanza out of the Vault policy and checks each path and each capability. Text it cannot parse is a failure, and so is a missing or unknown value.

After that the request is applied to a throwaway Vault, and the gate acts as the service, with a token that carries only the new policy. It has to read its own paths. It has to be refused with HTTP 403 `permission denied` on a write, on a delete, on a sibling service, on another team and on `sys/`. The secrets it must not reach are created first, so a "not found" cannot pass for a denial.

There are no skips. A missing tool, or a check that cannot run, fails the gate. The earlier version of this project counted skipped checks as passes, and that is how its policy checks went so long without ever running.

The gate also runs twice. The merge script brings the branch up to date with main and runs the gate again, because another job may have merged the same service in the meantime.

## The apply

`onboarding/bin/apply` is the release step, and a person runs it in a terminal.

The merge gate keeps the text of its Terraform plan, and the board shows it for a job that is ready to apply, so you can read it before you do anything. That plan was made on the gate's throwaway Vault. The apply script plans again on the target Vault, shows the policy in full, the role, the secret paths and the plan line, and asks for `yes`. What it applies is the plan file it just showed, not a new plan.

After the apply it checks the Vault itself. The policy text has to be the planned text. A token with only that policy has to read its own paths and get HTTP 403 `permission denied` on a write, on another team's path and on `sys/`. The role has to have the planned service account, namespace and policy.

Three things keep this step with a person. The script stops if it has no terminal, the hook refuses the command for agents and sessions, and the script refuses any address that is not on 127.0.0.1.

Terraform runs on a copy under `onboarding/.cache/apply/`, so state files stay out of the checkout. That state is local to the machine, which is fine for a laptop and is one of the things that has to change for a shared Vault.

## The hook

The hook stops an agent or a session from doing these things:

- merging
- pushing outside `onboard/*`
- force pushing
- running Terraform or Vault writes against anything but 127.0.0.1
- running the apply script

It also stops an agent from editing anything except its job folder and its request folder. If the hook itself crashes, the call is refused.

I don't want to oversell it. The shell rules match the text of a command, so they stop mistakes and they are not a sandbox. The protection that does not depend on matching text is the gate, which reads its files from the main checkout and compares them with `origin/main`.

The main session can still edit the gate, because otherwise nobody could maintain it. A change to the line itself is made by a person, on its own branch and pull request.

## Limits

- The gate needs the network the first time it runs, to download the Vault provider. After that it uses a local cache.
- The line handles one shape of request. A request that needs a change to the module, the platform layer or the policies is rejected at intake and done by a person.
- The apply script works on a local Vault only. For a shared Vault, the apply belongs in a pipeline with an approval step, remote state and a short-lived token. `docs/examples/apply-shared-vault.yml` shows the shape, and I have not run it.
- The module creates the secret paths with placeholder values. For a shared Vault this should change, because the team owns the values and the onboarding should only grant access.
- The line does not resolve merge conflicts. It escalates them.
