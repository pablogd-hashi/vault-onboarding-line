# vault-onboarding-line

Onboarding a service to Vault is the same change every time: a policy, a Kubernetes auth role and a few secret paths. Because it is small and repetitive, it tends to get approved without being read, and a wrong one gives a service access to another team's secrets.

I built this repository to see how much of that work I could hand to agents without losing control of it. A GitHub issue asking for an onboarding goes in, and a merged pull request with the spec, the plan and the Terraform comes out, with nobody approving the phases in between. A person comes back in at two points: when the line has a question or is not sure about a request, and at the very end, where it shows what it wants to write to Vault and waits for someone to apply it.

It runs in Claude Code. The agents do the parts that need judgement, like reading a request or reviewing a pull request. Everything that has to behave the same way every time (the state of a job, the gate, the merge and the apply) is a plain script, because I don't want a language model deciding whether a check passed.

## How a request moves

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
      │  └─ ESCALATE → PR ready for you, issue labelled onboard:needs-human
      │ merged
ready to apply → you run onboarding/bin/apply: it shows the policy, the role
                 and the plan, asks, applies, and checks the Vault
```

Intake reads the issue and decides whether the request can go down the line at all. If a value is missing it asks the author on the issue and waits for the answer. If the request asks for something this line must never grant, such as another team's secret paths, intake rejects it and explains why.

An accepted request gets a spec, written from the issue with the same R1 to R5 structure I use for spec-driven work. The builder then works from the spec only. It never reads the issue, so whatever a stranger typed into GitHub stays two steps away from the agent that has a shell. The builder writes the plan and the Terraform and opens a draft pull request.

From there a script takes over. The gate judges the branch, and if it fails the job goes back to the builder with the report. When the gate passes, a reviewer on a different model compares the issue, the spec, the plan and the Terraform, and an approver takes the final decision to merge or to hand the pull request to a person. A job gets three rounds, and after the third it goes to a person in any case.

## The gate

This repository grew out of an earlier one of mine, [sdd-tf-vault](https://github.com/pablogd-hashi/sdd-tf-vault), where a person approved every phase. When I looked closely at its validation step, I found that the policy checks had never actually run, that the script counted every skipped check as a pass, and that the one policy rule it had would have accepted update and delete on a whole team's secrets. The approvals were doing all the work, and nobody knew it.

So the gate here is built the other way round, as the one check that has to be enough without anyone looking. It has no skips, which means a missing tool or a check that cannot run is a failure. It is always read from the main checkout and never from the branch it is judging, so a branch cannot change the rules it is measured against.

What it checks, in order:

1. The tools are installed, and the policy unit tests and the module's own `terraform test` pass.
2. The branch only adds one new `requests/GH-<n>-<service>/` folder with its three files, and the files that do the judging are identical to `origin/main`.
3. `main.tf` is the template with only the five values changed. This happens before Terraform is allowed to touch the file.
4. No other folder already onboards the same team and service.
5. `terraform validate` and `plan` run against a throwaway `vault server -dev`, and Conftest reads the plan and checks every path and capability in the policy.
6. The request is applied to that throwaway Vault, and the gate then logs in as the service, with a token that carries only the new policy. It has to be able to read its own paths. It has to be refused, with a real HTTP 403 `permission denied`, on a write, on a delete, on a sibling service, on another team and on `sys/`.

The last check is the one I care about most. A plan can look right and still grant more than you meant. Asking a real Vault what the policy allows takes about ten seconds and removes the doubt.

You can run the whole thing yourself on the example request:

```bash
onboarding/bin/gate --request PE-001-payments-api
```

## The last step is yours

The line stops at the merge, and at that point nothing is in Vault yet. I want the work to be automatic, but I still want a person to look at what is about to change in Vault and be the one who releases it.

```bash
onboarding/bin/apply 12
```

The script plans the merged request against your Vault and shows you the policy in full, the role with its service account and namespace, the secret paths and the Terraform plan line. It applies only if you type `yes`, and it applies the plan it showed you, not a new one. Afterwards it checks the Vault the same way the gate does, posts the result on the issue and closes it.

An agent cannot do this for you. The script refuses to run without a terminal, the hook blocks the command for agents and for Claude Code sessions, and it only accepts a Vault on 127.0.0.1. For a shared Vault this step belongs in a pipeline with an approval and a short-lived token. There is an example of that in [docs/examples/apply-shared-vault.yml](docs/examples/apply-shared-vault.yml), which I have not run yet.

## Watching it work

I wanted to be able to follow a job without opening Claude Code, so every job is visible in two places.

On GitHub, the issue carries one label at a time that tells you the stage: `onboard`, then `onboard:intake`, `onboard:spec`, `onboard:build`, `onboard:review`, `onboard:approve` and `onboard:ready-to-apply`. Two more labels, `onboard:needs-info` and `onboard:needs-human`, mean the line is waiting for someone. Every step also leaves a comment. Intake's decision goes on the issue, and each gate report, the review and the approver's decision go on the pull request, so somebody who only looks at GitHub can still follow a job from start to end.

Locally there is a small board, which is one HTML page and a Python standard-library server.

![The board: the lanes on top, the steps of one job below](docs/img/board.png)

Each job is a card in the lane of its stage, with the gate and review result of every round, the risk and the time it has taken. The panel under the lanes shows the steps of one job and follows whichever job moved last. When a job is ready to apply, that panel shows the Terraform plan, so you can read what will be written to Vault before you run the apply script.

![The Terraform plan of a merged job, shown on the board](docs/img/step-to-apply.png)

## Run it

You need `git`, `gh` (logged in), `terraform`, `vault`, `conftest`, `python3` 3.9 or newer, and Claude Code. There is no Docker, no framework and no build step.

[docs/run.md](docs/run.md) is the full guide, from installing the tools to an applied request, with five examples to try. The short version is two commands, one to create the labels (once per repository) and one to start the board at http://127.0.0.1:8765:

```bash
onboarding/bin/labels
```

```bash
python3 onboarding/board/serve.py
```

Then file a request with the "Onboard a service to Vault" issue form, and in Claude Code, in this repository:

| Command | What it does |
|---|---|
| `/onboard run` | Runs every open `onboard` issue, three at a time, and picks up unfinished jobs. |
| `/onboard run 12` | Runs issue 12 only. |
| `/onboard where is 12?` | Answers from the job's state and files. |
| `/onboard for 12: use namespace identity-prod` | Sends your feedback to the builder, for a job that is waiting for you. |
| `/onboard onboard search-api for team discovery ...` | Files a new request for you. |

## What is in here

There is one agent per role, and each of them reads files, writes one file and replies with one line. The scripts read that file and decide what happens next, so an agent's word is never what moves a job.

| Agent | Reads | Writes | Shell |
|---|---|---|---|
| `intake` | the issue file | `intake.md`: accepted, needs-info or rejected | no |
| `spec-writer` | the issue file, intake | `01-spec/spec.md` with R1 to R5 | no |
| `builder` | the spec, the last gate and review | `02-plan/plan.md`, `03-terraform/main.tf`, the draft PR | yes |
| `reviewer` | spec, plan, diff, gate report | `review.md`: PASS or CHANGES | read-only |
| `approver` | the whole job | `decision.md`: APPROVE or ESCALATE | read-only |

| Script | What it does |
|---|---|
| `onboarding/bin/job` | The only writer of job state. It refuses illegal moves, a fourth parallel job and moves without evidence, and it moves the labels and posts the comments. |
| `onboarding/bin/gate` | Judges a branch. |
| `onboarding/bin/merge` | Syncs with main, runs the gate again and merges. Nothing else merges. |
| `onboarding/bin/apply` | The person's step: shows what will be written to Vault, asks, applies and checks. |
| `onboarding/bin/labels` | Creates the labels. |

```
requests/<id>/                 01-spec, 02-plan, 03-terraform for one service
requests/_template/            the shapes they must follow
terraform/modules/vault-service-onboard/   the only module a request may call
terraform/platform/            the Kubernetes auth mount
policies/conftest/             what a plan may contain, with unit tests
onboarding/bin/                job, gate, merge, apply, labels
onboarding/board/              the local board
.claude/                       agents, the /onboard skill, the guard hook
docs/                          how to run it, architecture, decisions
```

## The rules, and who enforces them

The rules the agents work under are in [CLAUDE.md](CLAUDE.md): never invent a value, use the module and nothing else, least privilege, one request per service, and so on. Instructions like these are easy to write and easy for a model to forget, so the ones a shell command could break are enforced by a hook, [.claude/hooks/guard.py](.claude/hooks/guard.py), which refuses the call before it runs:

- no merge by an agent or a session
- no push outside `onboard/*`, and no force push
- no `terraform apply` or Vault write to anything but 127.0.0.1
- no agent edits to the gate, the policies, the module or the hook
- no apply by an agent or a session

The hook matches the text of a command, so it stops mistakes rather than a determined attacker. The protection that does not depend on matching text is the gate reading its own files from the main checkout.

## What it does not do

The line handles one shape of request. If an onboarding needs a change to the module, to the platform layer or to the policies, intake rejects it and a person does that work. The line does not resolve merge conflicts either, it escalates them. And it has only ever applied to a local Vault. The path to a shared one is described above, not built.

## More

- [docs/run.md](docs/run.md) explains how to run it, step by step, with examples
- [docs/architecture.md](docs/architecture.md) explains how it is built and why
- [docs/adr/001-autonomous-onboarding-line.md](docs/adr/001-autonomous-onboarding-line.md) records the decision

## Credit and licence

The approach follows the idea of zazencodes' [software-factory-claude-code-v2](https://github.com/zazencodes/zazencodes-season-3/tree/main/src/software-factory-claude-code-v2): one orchestrating skill, one agent per role, state owned by a script, and a gate read from the main checkout. No code is taken from it. This repository is MIT licensed.
