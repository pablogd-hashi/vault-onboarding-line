# Infrastructure Request Specification

| Field | Value |
|-------|-------|
| **Request** | GH-NNN-SERVICE_NAME |
| **Issue** | #NNN |
| **Author** | |
| **Date** | |

## Context

<!-- Why the service needs Vault access, in the requester's words. Do not add facts the issue does not state. -->

## Requirements

Every value is copied from the issue. A value the issue does not give is never invented.

| # | Requirement | Source (issue field) |
|---|-------------|----------------------|
| R1 | Service name: `` | Service name |
| R2 | Team: `` | Team |
| R3 | Kubernetes namespace: `` | Kubernetes namespace |
| R4 | Service account: `` | Kubernetes service account |
| R5 | Secret paths: `` | Secret paths |

## Acceptance criteria

<!-- From the issue's acceptance criteria. -->

## Non-goals

- Changes to any Vault other than a local one
- Secret values (paths only)
- Access to another team's or another service's paths
- Changes to the module, the platform layer or the policies

## Verification

The gate (`onboarding/bin/gate`) proves these against a throwaway Vault before merge:

- Policy `{team}-{service_name}` grants read and list on `secret/(data|metadata)/teams/{team}/{service_name}/` only
- Kubernetes auth role `{team}-{service_name}` is bound to `{namespace}/{service_account}` and carries only that policy
- A token with only that policy reads each path in R5 and is denied on write, delete, sibling services, other teams and `sys/`

## Assumptions

<!-- Anything the spec-writer had to assume. The approver escalates assumptions that are really decisions. Write "None" if there are none. -->
