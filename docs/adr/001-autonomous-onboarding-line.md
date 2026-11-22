# ADR-001: An autonomous onboarding line with a behavioural gate

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-22 |

## Context

The predecessor of this repository (`sdd-tf-vault`) delivered Vault onboardings through IDE skills, driven by tickets, with a person approving each phase. Its validation step did not hold:

- Conftest had never run. One policy file had no `package` line, which stopped the whole folder from loading; the other was in a package the script never evaluated.
- The policy matched string prefixes, so read, update and delete on `secret/data/teams/*` passed.
- The validation script treated every skipped check as a pass.
- Three request folders onboarded the same service.

The human approvals were covering for a gate that checked little. We wanted the opposite: no approvals, and a gate that can be trusted on its own.

## Decision

1. **GitHub issues are the only intake.** The issue's label shows the stage; every step comments on the issue or the pull request. No other tracker or chat integration.
2. **One orchestrating skill, one agent per role** (intake, spec-writer, builder, reviewer, approver). Each agent reads files, writes one file and replies with one line. Builder and reviewer use different models.
3. **Scripts own everything deterministic.** One script is the only writer of job state and enforces legal moves, evidence, a limit of three parallel jobs and three build rounds. One script merges.
4. **The gate replaces approval.** It is read from the main checkout, has no skips, requires `main.tf` to be the template with five values, runs Conftest on the plan, and proves the policy's behaviour against a throwaway Vault with a token that carries only that policy.
5. **A job may only add one request folder.** Anything else is rejected at intake.
6. **Shell rules are enforced by a hook**, not by instructions.
7. **The spec stays the centre.** R1 to R5 are copied from the issue, the builder builds from the spec only, and the reviewer checks issue, spec, plan and Terraform against each other.

## Consequences

- A person sees a job only when intake asks a question, the approver escalates, or three rounds are used up.
- The line is narrow on purpose. It cannot change the module or the policies, so it cannot widen what it is allowed to produce.
- Trust moves from reviewers to the gate. The gate, the policies and the hook are now the critical code and are changed only by people, in their own pull requests.
- Running the gate needs `terraform`, `vault` and `conftest` installed locally. There is no degraded mode.
- Job state is local to the operator's machine. GitHub labels and comments are the shared record.

## Alternatives rejected

- **Keep human approvals and fix the gate.** Safe, but the approvals add waiting and, as the old reports show, do not catch what a gate misses.
- **Static policy checks only.** A plan can look right and still grant more than intended. Asking a real Vault is cheap and removes the doubt.
- **Let jobs change the module when a request needs it.** Then a branch could change what it is judged against. Module changes stay with people.
- **A workflow engine or agent framework.** A few hundred lines of standard-library Python and one skill are easier to read, explain and audit.

## Credit

The shape (orchestrating skill, per-role agents, script-owned state, gate read from the main checkout, merge by script) follows the idea of zazencodes' software-factory-claude-code-v2. No code was taken from it.
