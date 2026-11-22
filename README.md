# vault-onboarding-line

A GitHub issue asking to onboard a service to Vault goes in. A merged pull request with the spec, the plan and the Terraform comes out. No person approves anything in between. A person is involved only when the line asks a question or escalates.

It runs in Claude Code. One skill orchestrates. Five agents each do one role. Scripts do everything that must give the same result every time.

## The line

```
issue labelled `onboard`
      │
intake ──── needs-info → asks on the issue      rejected → says why, closes
      │ accepted
spec-writer → requests/<id>/01-spec/spec.md
      │
builder ───→ 02-plan/plan.md, 03-terraform/main.tf, draft PR "Closes #n"
      │          ▲
gate (script) ─FAIL┤
      │ PASS       │
reviewer ─CHANGES──┘        at most 3 rounds, then a person
      │ PASS
approver ── APPROVE  → merge script: sync with main, gate again, merge
         └─ ESCALATE → PR ready for you, issue labelled onboard:needs-human
```

## What you need

`git`, `gh` (logged in), `terraform`, `vault`, `conftest`, `python3` 3.9 or newer, and Claude Code. No Docker, no framework, no build step.

## Run it

The full guide is [docs/run.md](docs/run.md). The short version:

```bash
onboarding/bin/labels
```

```bash
python3 onboarding/board/serve.py
```

The first command creates the stage labels, once per repository. The second starts the board at http://127.0.0.1:8765.

File a request with the "Onboard a service to Vault" issue form. Then, in Claude Code in this repository:

| Command | What it does |
|---|---|
| `/onboard run` | Runs every open `onboard` issue, three at a time. Also resumes unfinished jobs. |
| `/onboard run 12` | Runs issue 12 only. |
| `/onboard where is 12?` | Answers from the job's state and files. |
| `/onboard for 12: use namespace identity-prod` | Sends your feedback to the builder, for a job that is waiting for you. |
| `/onboard onboard search-api for team discovery ...` | Files a new request for you. |

## Where to watch

On GitHub, the issue has one stage label at a time:

`onboard` → `onboard:intake` → `onboard:spec` → `onboard:build` → `onboard:review` → `onboard:approve`

The issue closes when the pull request merges. The side exits are `onboard:needs-info` and `onboard:needs-human`. Every step leaves a comment. Intake's decision is on the issue. Each gate report, the review and the approver's decision are on the pull request.

On the board, there is one card per job, in the lane of its stage. A card shows the gate and review result of every round, the risk, the minutes elapsed and a dot while the job runs. Click a card to read every step.

## Agents

| Role | Reads | Writes | Shell |
|---|---|---|---|
| `intake` | the issue file | `intake.md`: accepted, needs-info or rejected | no |
| `spec-writer` | the issue file, intake | `01-spec/spec.md` with R1 to R5 | no |
| `builder` | the spec, the last gate and review | `02-plan/plan.md`, `03-terraform/main.tf`, the draft PR | yes |
| `reviewer` | spec, plan, diff, gate report | `review.md`: PASS or CHANGES | read-only |
| `approver` | the whole job | `decision.md`: APPROVE or ESCALATE | read-only |

Builder and reviewer run on different models. Each agent replies with one line. The scripts read the file the agent wrote and decide the next move.

## Scripts

| Script | What it does |
|---|---|
| `onboarding/bin/job` | The only writer of job state. It refuses illegal moves, a fourth parallel job and moves without evidence. It moves the labels and posts the comments. |
| `onboarding/bin/gate` | Judges a branch. |
| `onboarding/bin/merge` | Syncs with main, runs the gate again and merges. Nothing else merges. |
| `onboarding/bin/labels` | Creates the labels. |

## The gate

The gate is the only check between an agent and a merge. It has no skips. A missing tool, or a check that cannot run, is a failure. The gate is read from the main checkout, not from the branch it judges.

It checks, in this order:

1. The tools are present. The policy unit tests and the module's `terraform test` pass.
2. The branch only adds one new `requests/GH-<n>-<service>/` with its three files. The files that judge it are identical to `origin/main`.
3. `main.tf` is the template with only the five values changed. This runs before Terraform does.
4. No other folder onboards the same team and service.
5. `terraform validate` and `plan` work against a throwaway `vault server -dev`. Conftest passes on the plan JSON.
6. The request is applied to the throwaway Vault. A token with only the new policy must read each of its paths. It must get HTTP 403 `permission denied` on write, on delete, on a sibling service, on another team and on `sys/`. The role must have one service account, one namespace and only its own policy.

You can run the checks yourself:

```bash
onboarding/bin/gate --request PE-001-payments-api
```

```bash
conftest verify -p policies/conftest
```

```bash
python3 .claude/hooks/guard_test.py
```

The first runs the whole gate on the example request. The second runs the policy unit tests. The third tests every denial of the hook.

## Rules

The rules are in [CLAUDE.md](CLAUDE.md). A hook, [.claude/hooks/guard.py](.claude/hooks/guard.py), enforces the ones a shell command could break:

- no merge by an agent or a session
- no push outside `onboard/*`
- no force push
- no `terraform apply` or Vault write to anything but 127.0.0.1
- no agent edits to the gate

## Layout

```
requests/<id>/                 01-spec, 02-plan, 03-terraform for one service
requests/_template/            the shapes they must follow
terraform/modules/vault-service-onboard/   the only module a request may call
terraform/platform/            the Kubernetes auth mount
policies/conftest/             what a plan may contain, with unit tests
onboarding/bin/                job, gate, merge, labels
onboarding/board/              the local board
.claude/                       agents, the /onboard skill, the guard hook
docs/                          how to run it, architecture, decisions
```

## More

- [docs/run.md](docs/run.md): how to run it, step by step
- [docs/architecture.md](docs/architecture.md): how it is built and why
- [docs/adr/001-autonomous-onboarding-line.md](docs/adr/001-autonomous-onboarding-line.md): the decision

## Licence

MIT. The approach follows the idea of zazencodes' software-factory-claude-code-v2: one orchestrating skill, one agent per role, state owned by a script, a gate read from the main checkout. No code is taken from it.
