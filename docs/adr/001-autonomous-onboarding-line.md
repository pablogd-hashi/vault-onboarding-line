# ADR-001: An autonomous onboarding line with a behavioural gate

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-22 |

## Context

The repository before this one, `sdd-tf-vault`, did Vault onboardings with IDE skills. A ticket started the work and a person approved each phase. When I went back to its validation step I found four problems:

- Conftest had never run. One policy file had no `package` line, so the whole folder failed to load, and the other file was in a package the script never evaluated.
- The policy matched string prefixes, so a policy with read, update and delete on `secret/data/teams/*` passed.
- The validation script counted every skipped check as a pass.
- Three request folders onboarded the same service.

So the only real check was the person approving. I wanted to drop the approval per phase and have a gate good enough that I don't need one.

## Decision

1. GitHub issues are the only way in. The label on the issue shows the stage, and every step comments on the issue or on the pull request. No other tracker, no chat integration.
2. One skill orchestrates, with one agent per role: intake, spec-writer, builder, reviewer and approver. Each agent reads files, writes one file and answers with one line. Builder and reviewer use different models.
3. Scripts do everything that has to be deterministic. One script is the only writer of job state. It enforces the legal moves, the evidence for each move, the limit of three parallel jobs and the limit of three build rounds. One script merges.
4. The gate replaces the approval. It runs from the main checkout and has no skips. It requires `main.tf` to be the template with five values, runs Conftest on the plan, applies the request to a throwaway Vault and tests the policy with a token that has only that policy.
5. A job can only add one request folder. Anything else is rejected at intake.
6. The shell rules are enforced by a hook, not by instructions.
7. The spec stays at the centre. R1 to R5 come from the issue, the builder works from the spec only, and the reviewer checks the issue, the spec, the plan and the Terraform against each other.
8. A person applies. The line stops at the merge. The apply script shows the policy, the role and the plan, and applies after a person types yes. Agents and sessions can't run it. After the apply it checks the result on the Vault.

## Consequences

- A person sees a job when intake asks a question, when the approver escalates, when three rounds are used up, and at the apply.
- Nothing reaches Vault without a person. That costs one command per request.
- The line is narrow. It can't change the module or the policies, so it can't widen what it is allowed to produce.
- The gate, the policies and the hook are now the critical code. Only people change them, in their own pull requests.
- The gate needs `terraform`, `vault` and `conftest` installed locally. There is no reduced mode without them.
- Job state is local to the operator's machine. What is shared is the labels and comments on GitHub.

## Alternatives I rejected

**Keep the human approvals and fix the gate.** The safe choice. But approvals mean waiting, and the old validation reports show the approvals didn't catch what the gate missed.

**Static policy checks only.** A plan can look right and still grant more than intended. Testing against a real Vault takes about ten seconds, so I see no reason to skip it.

**Let a job change the module when a request needs it.** Then a branch could change the thing it is checked against. Module changes stay with people.

**A workflow engine or an agent framework.** A few Python scripts and one skill are easier to read and to audit, and I can explain every part of it.

**Apply automatically after the merge.** Then nobody looks at what gets written to Vault. One look by a person, with the policy and the plan in front of them, is cheap, and most organisations require it anyway for a change to access.

## Credit

The idea comes from zazencodes' software-factory-claude-code-v2: a skill that orchestrates, one agent per role, a script that owns the state, a gate that runs from the main checkout and a merge by script. No code was taken from it.
