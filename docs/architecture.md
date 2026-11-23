# Architecture

## What this is for

Onboarding a service to Vault is a small change that is always the same: one policy, one Kubernetes auth role and a few secret paths. If it's wrong, a service can end up reading another team's secrets. And people who approve the same change all day stop reading it.

Here agents do the work and nobody approves the phases. A gate does the checking: it applies the request to a throwaway Vault and tests what the new policy can and can't do. One step stays with a person. After the merge, someone looks at what will be written to Vault and applies it.

## Agents, scripts and a hook

| Part | What it does | Do I trust it? |
|---|---|---|
| Agents (`.claude/agents/`) | Read the request, write the spec, the plan and the Terraform, review the pull request. | No. Each agent writes one file and a script reads it. |
| Scripts (`onboarding/bin/`) | State, labels, comments, the gate, the merge, the apply. | Yes. Every decision that moves a job is made here. |
| The hook (`.claude/hooks/guard.py`) | Blocks tool calls that break a rule. | To stop mistakes, yes. |

The `/onboard` skill connects them and does very little itself. It runs a script, starts the agent the script names, and runs the next script when the agent is done. It doesn't write specs or code, and it never reads the issue text.

## How a job moves

The state of a job is in `onboarding/jobs/<id>/job.json`. Only `onboarding/bin/job` writes it. These are the moves it allows:

```
intake ──→ spec ──→ build ──→ gate ──→ review ──→ approve ──→ merging ──→ ready-to-apply ──→ applied
  │                   ▲         │         │           │           │
  ├→ needs-info ──────┘(intake) └─────────┴→ build    └───────────┴→ needs-human
  └→ rejected                     (next round, or needs-human after round 3)
```

An agent saying "done" doesn't move a job. Before each move the script looks at a file or at git:

| Move | What the script checks |
|---|---|
| intake → spec | `intake.md` starts with `DECISION: accepted` and names a valid service |
| spec → build | the spec file exists and has R1 to R5 |
| build → gate | `build.md` says READY, the branch is pushed, there is exactly one open pull request |
| gate → review | the gate script exited 0 and wrote `GATE: PASS` |
| review → approve | `review.md` says PASS for the commit the branch is at |
| approve → merging | `decision.md` says APPROVE, and the gate and the review of this round are PASS |
| merging → ready-to-apply | the merge script's own gate passed and GitHub merged the pull request |
| ready-to-apply → applied | a person ran the apply script and `apply.md` starts with `APPLY: PASS` |

Each job has its own git worktree (`.worktrees/<id>`) and its own branch (`onboard/<id>`), so three jobs can run at once without getting in each other's way. The script won't start a fourth.

## The issue is untrusted input

Anyone who can open an issue can type whatever they want into it, so I treat the issue text like any other untrusted input.

Only issues with the `onboard` label run, and you need triage rights on the repository to add a label. The script saves the issue to `issue.md` as quoted text, with a note on top saying it is data. Only comments from the author and from the operator are included. The issue text is never pasted into a prompt. An agent is told where the file is and reads it.

Intake reads it first, and intake has no shell. The builder has a shell, but it only reads the spec, never the issue. And even if an agent gets talked into something, all it can produce is one new request folder, and that folder still has to pass the gate.

## The gate

The gate runs from the main checkout. The script, the policies, the module and the template it uses are the ones on `main`, and during a job they also have to match `origin/main`. A branch can't bring its own version of the rules.

It checks the shape of `main.tf` before running Terraform on it. The file has to be the template with five values changed, and each value has to match a fixed pattern. I did it this way because `terraform plan` on arbitrary HCL can run code, and I don't want Terraform to touch anything an agent wrote unless it is the template.

Conftest then reads the plan JSON, takes every `path` block out of the Vault policy and checks each path and capability. If it can't parse something, that is a failure too.

After that the request is applied to a throwaway Vault, and the gate logs in with a token that has only the new policy. It must be able to read its own paths. It must get HTTP 403 `permission denied` on a write, a delete, another service of the same team, another team and `sys/`. The secrets it shouldn't reach are created first, otherwise a "not found" could look like a denial.

There are no skips. If a tool is missing or a check can't run, the gate fails. The previous version of this project counted skipped checks as passes, and that's how its policy checks went unnoticed without ever running.

The gate runs twice per job. The merge script updates the branch with `main` and runs it again, because another job may have merged the same service in the meantime.

## The apply

`onboarding/bin/apply` is the step a person runs, in a terminal.

The merge gate saves the text of its Terraform plan, and the board shows it when a job is ready to apply, so you can read it first. That plan was made against the gate's throwaway Vault. The apply script plans again against the real target, shows the full policy, the role, the secret paths and the plan line, and asks for `yes`. It applies the plan file it just showed, not a new one.

Then it checks the Vault. The policy text has to be what was planned. A token with only that policy has to read its own paths and get `permission denied` on a write, on another team's path and on `sys/`. The role has to have the planned service account, namespace and policy.

Three things keep this step with a person: the script stops if there is no terminal, the hook blocks the command for agents and sessions, and the script refuses any address that isn't 127.0.0.1.

Terraform runs on a copy under `onboarding/.cache/apply/`, so the state files stay out of the checkout. That state is local to the machine. It's fine for a laptop and it has to change for a shared Vault.

## The hook

The hook blocks these for agents and for the session:

- merging
- pushing outside `onboard/*`
- force pushing
- Terraform or Vault writes to anything but 127.0.0.1
- running the apply script

It also stops an agent from editing anything outside its job folder and its request folder. If the hook crashes, the call is refused.

The hook matches the text of a command. That stops mistakes, but it is not a sandbox and I wouldn't rely on it against someone who is really trying. The part that doesn't depend on matching text is the gate, which uses the files on `main` and compares them with `origin/main`.

The main session can still edit the gate, because somebody has to maintain it. Changes to the line itself are made by a person, in a separate branch and pull request.

## Limits

- The gate needs the network the first time, to download the Vault provider. After that it uses a local cache.
- The line handles one kind of request. If it needs a change to the module, the platform layer or the policies, intake rejects it and a person does it.
- The apply script only works on a local Vault. For a shared Vault the apply should be a pipeline with an approval, remote state and a short-lived token. `docs/examples/apply-shared-vault.yml` shows how that could look. I haven't run it.
- The module creates the secret paths with placeholder values. For a shared Vault I would change that, because the team owns the values and the onboarding should only give access.
- The line doesn't fix merge conflicts. It escalates them.
