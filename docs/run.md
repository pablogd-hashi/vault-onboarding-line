# How to run it

This is the full path, from an empty laptop to a merged onboarding. Steps 1 to 4 are done once. Steps 5 to 9 are done for every request.

## 1. Install the tools

You need `git`, `gh`, `terraform`, `vault`, `conftest`, `python3` (3.9 or newer) and Claude Code. On a Mac:

```bash
brew install gh hashicorp/tap/terraform hashicorp/tap/vault conftest
```

Docker is not needed.

## 2. Log in to GitHub

```bash
gh auth login
```

```bash
gh auth status
```

The second command must say "Logged in". The line uses `gh` for every label, comment, pull request and merge.

## 3. Get the repository

```bash
gh repo clone <owner>/vault-onboarding-line
```

```bash
cd vault-onboarding-line
```

## 4. Check the gate and create the labels

Run the gate on the example request. It takes about 10 seconds and needs the network the first time, to download the Vault provider.

```bash
onboarding/bin/gate --request PE-001-payments-api
```

The last line must be `GATE: PASS`. If a tool is missing, the gate fails and names it.

Create the stage labels. This is needed once per repository.

```bash
onboarding/bin/labels
```

## 5. Start the board

In a second terminal:

```bash
python3 onboarding/board/serve.py
```

Open http://127.0.0.1:8765. The board is empty until a job starts. It only reads files, so you can stop and start it at any time.

## 6. File a request

On GitHub, open **Issues**, then **New issue**, then **Onboard a service to Vault**. Fill in the form:

| Field | Example |
|---|---|
| Service name | `auth-api` |
| Team | `identity` |
| Kubernetes namespace | `identity` |
| Kubernetes service account | `auth-api` |
| Secret paths | `secret/teams/identity/auth-api/config` |
| Acceptance criteria | optional |

The form adds the `onboard` label. Note the issue number.

Team names are lowercase letters and digits, with no hyphen. Service names are kebab-case. Secret paths must be under `secret/teams/<team>/<service>/`.

## 7. Start the line

Open Claude Code in the repository folder and type one of these:

| Command | What it does |
|---|---|
| `/onboard run 12` | Runs issue 12. |
| `/onboard run` | Runs every open issue labelled `onboard`, three at a time. It also picks up jobs that were interrupted. |

Leave the session open. It starts each agent in the background and moves the job when the agent finishes.

## 8. Watch it

On the board, the card moves from lane to lane. Click a card to read each step: the issue, the intake decision, the spec, every gate report, the review and the approver's decision.

On GitHub, the issue has one stage label at a time:

`onboard:intake` → `onboard:spec` → `onboard:build` → `onboard:review` → `onboard:approve`

Intake comments on the issue. The gate report, the review and the approver's decision are comments on the pull request.

## 9. When the line needs you

| Label on the issue | What happened | What you do |
|---|---|---|
| `onboard:needs-info` | Intake asked a question on the issue. | Answer in a comment on the issue. Then run `/onboard run 12` again. |
| `onboard:needs-human` | The approver escalated, or three build rounds were used. The pull request is ready for review. | Read the pull request. Merge it yourself, close it, or send it back with `/onboard for 12: <what to change>`. |
| none, issue closed, no pull request | Intake rejected the request. The reason is in a comment on the issue. | File a new request if the reason can be fixed. |

You can ask about a job at any time:

```
/onboard where is 12?
```

## 10. When it is done

The pull request is merged, the issue is closed and the card is in **Done**. The request is on `main`:

```
requests/GH-12-auth-api/
  01-spec/spec.md
  02-plan/plan.md
  03-terraform/main.tf
```

The line does not apply to any shared Vault. That step belongs to a person.

## Optional: apply a merged request to a local Vault

Start a dev Vault in one terminal:

```bash
vault server -dev -dev-root-token-id=root
```

In another terminal, create the Kubernetes auth mount. This is needed once per Vault.

```bash
cd terraform/platform && terraform init && terraform apply
```

Then apply the request:

```bash
cd requests/GH-12-auth-api/03-terraform && terraform init && terraform apply
```

Both use `http://127.0.0.1:8200` and the token `root` by default.

## Try it without GitHub

`ONBOARD_OFFLINE=1` makes the state script skip every GitHub call and print what it would have done. The sample issues are in `onboarding/examples/`.

```bash
export ONBOARD_OFFLINE=1
```

```bash
onboarding/bin/job create 101 --from-file onboarding/examples/issue-101.json
```

```bash
onboarding/bin/job queue
```

The job shows on the board. Delete `onboarding/jobs/` to clear it.
