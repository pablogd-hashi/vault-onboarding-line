# Architecture

## The problem

Onboarding a service to Vault is the same small change every time: one policy, one Kubernetes auth role and a few secret paths. A mistake in it can give a service access to another team's secrets. A person who approves these changes all day stops reading them closely.

This repository lets agents do the work and removes the human approval of each phase. The approval is replaced by a gate. The gate applies the request to a throwaway Vault and tests what the new policy can and cannot do.

One human step is left, at the end. The line merges the request and stops. A person looks at what will be written to Vault and applies it.

## The parts

| Part | What it does | What it is trusted with |
|---|---|---|
| Agents (`.claude/agents/`) | Judgement and writing. Is the request valid, what does the spec say, does the pull request match the issue. | Nothing. Each agent writes one file and a script reads it. |
| Scripts (`onboarding/bin/`) | State, labels, comments, the gate, the merge. | Every decision that moves a job. |
| The hook (`.claude/hooks/guard.py`) | Refuses tool calls that break a rule. | Stopping mistakes. |

The orchestrator is the `/onboard` skill. It runs a script, starts the agent the script names, and runs the next script when the agent finishes. It writes no spec and no code. It does not read the issue text.

## Stages

The state of a job is in `onboarding/jobs/<id>/job.json`. Only `onboarding/bin/job` writes it. These are the allowed moves:

```
intake ──→ spec ──→ build ──→ gate ──→ review ──→ approve ──→ merging ──→ ready-to-apply ──→ applied
  │                   ▲         │         │           │           │
  ├→ needs-info ──────┘(intake) └─────────┴→ build    └───────────┴→ needs-human
  └→ rejected                     (next round, or needs-human after round 3)
```

A move needs evidence. The script reads the evidence from files and from git. It does not use what the agent replied.

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

Each job has its own git worktree, `.worktrees/<id>`, and its own branch, `onboard/<id>`. Three jobs can run at the same time without touching each other. The script refuses a fourth.

## Issue text

The issue is the only input written by someone outside the line. It is treated as data.

- Only issues labelled `onboard` run. Adding a label needs triage rights on the repository.
- The script saves the issue to `issue.md` as quoted text, under a notice that says it is data. It includes only the comments of the author and of the operator.
- No prompt contains issue text. Agents are told where the file is.
- Intake reads the issue first and has no shell. The builder does not read the issue. It reads the spec.
- An agent can only produce one new request folder, and that folder must pass the gate.

## The gate

The gate is read from the main checkout. The script, the policies, the module and the template that judge a branch are the copies in the main checkout. In the line they must also be identical to `origin/main`. A branch cannot change what judges it.

The file shape is checked before Terraform runs. `main.tf` must be the template with five values changed, and each value must match a fixed pattern. Other HCL never reaches `terraform init`.

Conftest reads the plan JSON. It takes every `path` stanza out of the Vault policy and checks each path and each capability. Text it cannot parse is a failure. A missing or unknown value is a failure.

The request is then applied to a throwaway Vault. A token with only the new policy must read its own paths. It must be refused with HTTP 403 `permission denied` on write, on delete, on a sibling service, on another team and on `sys/`. The secrets it must not reach are created first, so a "not found" cannot count as a denial.

The gate has no skips. A missing tool, or a check that cannot run, fails the gate.

The gate runs twice. The merge script syncs the branch with main and runs the gate again, because another job may have merged the same service in the meantime.

## The apply

`onboarding/bin/apply` is the release step. A person runs it in a terminal.

It plans the merged request against the Vault in `apply_to`. It shows the policy in full, the role, the secret paths and the Terraform plan line, and asks for `yes`. It then applies the plan file it showed, not a new plan.

The merge gate keeps the text of its Terraform plan, and the board shows it for a job that is ready to apply. That plan was made on the gate's throwaway Vault. The apply script plans again on the target Vault, and that second plan is the one it applies.

After the apply it checks the Vault itself. The policy text must be the planned text. A token with only that policy must read its own paths and must get HTTP 403 `permission denied` on a write, on another team's path and on `sys/`. The role must have the planned service account, namespace and policy.

Three things keep this step with a person. The script stops if it has no terminal. The hook refuses the command for agents and sessions. The script refuses any address that is not on 127.0.0.1.

Terraform runs on a copy under `onboarding/.cache/apply/`, so state files stay out of the checkout. The state is local to the machine.

## The hook

The hook stops an agent or a session from doing these things:

- merging
- pushing outside `onboard/*`
- force pushing
- running Terraform or Vault writes against anything but 127.0.0.1
- running the apply script

It also stops an agent from editing anything except its job folder and its request folder. If the hook crashes, the call is refused.

The shell rules match the text of the command. They stop mistakes, but they are not a sandbox. The protection that does not depend on matching text is the gate, which reads its files from the main checkout and compares them with `origin/main`.

The main session can edit the gate. Without that, nobody could maintain it. A change to the line is made by a person, on its own branch and pull request.

## Limits

- The gate needs the network the first time it runs, to download the Vault provider. After that it uses a local cache.
- The line handles one shape of request. A request that needs a change to the module, the platform layer or the policies is rejected at intake and done by a person.
- The apply script works on a local Vault only. For a shared Vault, the apply belongs in a pipeline with an approval step, remote state and a short-lived token. `docs/examples/apply-shared-vault.yml` shows the shape and has not been run.
- The module creates the secret paths with placeholder values. For a shared Vault this should change: the team owns the values, and the onboarding only grants access.
- The line does not resolve merge conflicts. They escalate.
