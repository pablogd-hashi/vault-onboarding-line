# vault-onboarding-line

A GitHub issue asking to onboard a service to Vault goes in. A merged pull request with the spec, the plan and the Terraform comes out. Nobody approves anything in between. A person is involved only when the line asks a question or escalates.

It runs in Claude Code: one skill orchestrates, five agents each do one role, and scripts do everything that must be deterministic.

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
reviewer ─CHANGES──┘        at most 3 rounds, then a human
      │ PASS
approver ── APPROVE  → merge script: sync with main, gate again, merge
         └─ ESCALATE → PR ready for you, issue labelled onboard:needs-human
```

## What you need

`git`, `gh` (logged in), `terraform`, `vault`, `conftest`, `python3` (3.9 or newer) and Claude Code. No Docker, no frameworks, no build step.

## Run it

```bash
onboarding/bin/labels            # once per repository: creates the stage labels
python3 onboarding/board/serve.py   # the board, http://127.0.0.1:8765
```

File a request with the "Onboard a service to Vault" issue form (it adds the `onboard` label). Then, in Claude Code in this repository:

| Command | What it does |
|---|---|
| `/onboard run` | Every open `onboard` issue, three at a time. Also resumes unfinished jobs. |
| `/onboard run 12` | Only issue 12. |
| `/onboard where is 12?` | Answers from the job's state and files. |
| `/onboard for 12: use namespace identity-prod` | Feedback for a job that needs you; it goes back to the builder. |
| `/onboard onboard search-api for team discovery ...` | Files a new request for you. |

## Watching a job

**On GitHub.** The issue carries one stage label at a time:
`onboard` → `onboard:intake` → `onboard:spec` → `onboard:build` → `onboard:review` → `onboard:approve`, then the issue closes when the pull request merges. Side exits are `onboard:needs-info` and `onboard:needs-human`. Every step leaves a comment: intake's decision on the issue; each round's gate report, the review and the approver's decision on the pull request.

**On the board.** One card per job, in the column of its stage, with a chip per gate and review of every round (green pass, red fail), the risk, minutes elapsed and a dot while it runs. Click a card to read every step.

## Who does what

| Role | Reads | Writes | Shell |
|---|---|---|---|
| `intake` | the issue file | `intake.md`: accepted, needs-info or rejected | none |
| `spec-writer` | issue file, intake | `01-spec/spec.md` (R1 to R5) | none |
| `builder` | the spec, last gate and review | `02-plan/plan.md`, `03-terraform/main.tf`, the draft PR | yes |
| `reviewer` | spec, plan, diff, gate report | `review.md`: PASS or CHANGES | read-only use |
| `approver` | the whole job | `decision.md`: APPROVE or ESCALATE | read-only use |

Builder and reviewer run on different models. Each agent replies with one line; the scripts read the file it wrote and decide the move.

| Script | Job |
|---|---|
| `onboarding/bin/job` | The only writer of job state. Refuses illegal moves, a fourth parallel job, and moves without evidence. Moves labels and posts comments. |
| `onboarding/bin/gate` | Judges a branch. See below. |
| `onboarding/bin/merge` | Syncs with main, runs the gate again, merges. The only thing that merges. |
| `onboarding/bin/labels` | Creates the labels. |

## The gate

The gate is the only thing between an agent and a merge, so it has no skips: a missing tool or a check that cannot run is a failure. It is read from the main checkout, never from the branch it judges.

1. Tools present; policy unit tests; module `terraform test`.
2. The branch only adds one new `requests/GH-<n>-<service>/` with its three files. The judging files are identical to `origin/main`.
3. `main.tf` is the template with only the five values changed. This is checked before Terraform runs.
4. No other folder already onboards the same team and service.
5. `terraform validate` and `plan` against a throwaway `vault server -dev`; Conftest on the plan JSON.
6. Apply to the throwaway Vault, then act as the service with a token that carries only the new policy. It must read each of its paths. It must get HTTP 403 `permission denied` on write, delete, a sibling service, another team and `sys/`. The role must have one service account, one namespace and only its own policy.

```bash
onboarding/bin/gate --request PE-001-payments-api    # the whole gate on the worked example
conftest verify -p policies/conftest                 # policy unit tests
python3 .claude/hooks/guard_test.py                  # every hook denial
```

The line never applies to a real Vault. After a merge, a person applies the request to their own local Vault if they want it there.

## Rules

They are in [CLAUDE.md](CLAUDE.md). The ones a shell command must not break are enforced by a hook, [.claude/hooks/guard.py](.claude/hooks/guard.py): no merge by an agent or a session, no push outside `onboard/*`, no force push, no `terraform apply` or Vault write to anything but 127.0.0.1, no agent edits to the gate.

## Try it without GitHub

`ONBOARD_OFFLINE=1` makes `onboarding/bin/job` skip every GitHub call and print what it would have done. With the sample issues in `onboarding/examples/`:

```bash
export ONBOARD_OFFLINE=1
onboarding/bin/job create 101 --from-file onboarding/examples/issue-101.json
onboarding/bin/job queue
```

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
docs/                          architecture and decisions
```

More: [docs/architecture.md](docs/architecture.md), [docs/adr/001-autonomous-onboarding-line.md](docs/adr/001-autonomous-onboarding-line.md).

## Licence

MIT. The approach (one orchestrating skill, one agent per role, script-owned state, a gate read from the main checkout) follows the idea of zazencodes' software-factory-claude-code-v2. No code is taken from it.
