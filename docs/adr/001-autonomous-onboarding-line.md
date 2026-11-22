# ADR-001: An autonomous onboarding line with a behavioural gate

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-22 |

## Context

The repository before this one, `sdd-tf-vault`, delivered Vault onboardings through IDE skills. A ticket started the work and a person approved each phase. When I went through its validation step, I found four problems:

- Conftest had never run. One policy file had no `package` line, which stopped the whole folder from loading, and the other file was in a package the script never evaluated.
- The policy matched string prefixes, so a policy with read, update and delete on `secret/data/teams/*` passed.
- The validation script counted every skipped check as a pass.
- Three request folders onboarded the same service.

In practice the approvals were the only real check. I wanted the opposite arrangement: no approval of each phase, and a gate that is enough without one.

## Decision

1. GitHub issues are the only intake. The label on the issue shows the stage, and every step comments on the issue or on the pull request. There is no other tracker and no chat integration.
2. One skill orchestrates, and there is one agent per role: intake, spec-writer, builder, reviewer and approver. Each agent reads files, writes one file and replies with one line. Builder and reviewer use different models.
3. Scripts do everything deterministic. One script is the only writer of job state, and it enforces the legal moves, the evidence for each move, the limit of three parallel jobs and the limit of three build rounds. One script merges.
4. The gate replaces the approval. It is read from the main checkout and has no skips. It requires `main.tf` to be the template with five values, runs Conftest on the plan, applies the request to a throwaway Vault and tests the policy with a token that carries only that policy.
5. A job may only add one request folder. Anything else is rejected at intake.
6. The shell rules are enforced by a hook, not by instructions.
7. The spec stays the centre. R1 to R5 are copied from the issue, the builder builds from the spec only, and the reviewer checks the issue, the spec, the plan and the Terraform against each other.
8. A person applies. The line stops at the merge. The apply script shows the policy, the role and the plan, and applies after a person types yes. Agents and sessions cannot run it, and afterwards it checks the result on the Vault.

## Consequences

- A person sees a job when intake asks a question, when the approver escalates, when three rounds are used, and at the apply.
- Nothing reaches Vault without a person. The cost of that is one command per request.
- The line is narrow. It cannot change the module or the policies, so it cannot widen what it is allowed to produce.
- The gate, the policies and the hook are now the critical code. Only people change them, in their own pull requests.
- The gate needs `terraform`, `vault` and `conftest` installed locally, and there is no reduced mode without them.
- Job state is local to the operator's machine. The shared record is the labels and comments on GitHub.

## Alternatives I rejected

**Keep the human approvals and fix the gate.** This is the safe choice, but approvals add waiting, and the old validation reports show that they did not catch what the gate missed.

**Static policy checks only.** A plan can look right and still grant more than intended. Testing against a real Vault takes about ten seconds, so there is little reason not to.

**Let a job change the module when a request needs it.** A branch could then change what it is judged against. Module changes stay with people.

**A workflow engine or an agent framework.** A few scripts in standard-library Python and one skill are easier to read and to audit, and I want to be able to explain every part of this to my team.

**Apply automatically after the merge.** Then nobody looks at what is written to Vault. One decision by a person, with the policy and the plan in front of them, is cheap, and it is what most organisations require for a change to access.

## Credit

The approach follows the idea of zazencodes' software-factory-claude-code-v2: an orchestrating skill, one agent per role, state owned by a script, a gate read from the main checkout and a merge by script. No code was taken from it.
