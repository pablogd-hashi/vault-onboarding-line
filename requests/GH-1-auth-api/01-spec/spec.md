# Infrastructure Request Specification

| Field | Value |
|-------|-------|
| **Request** | GH-1-auth-api |
| **Issue** | #1 |
| **Author** | |
| **Date** | 2026-11-22 |

## Context

The issue, titled "Onboard auth-api to Vault", asks to onboard the `auth-api` service of the `identity` team to Vault. It gives no further reason.

## Requirements

Every value is copied from the issue. A value the issue does not give is never invented.

| # | Requirement | Source (issue field) |
|---|-------------|----------------------|
| R1 | Service name: `auth-api` | Service name |
| R2 | Team: `identity` | Team |
| R3 | Kubernetes namespace: `identity` | Kubernetes namespace |
| R4 | Service account: `auth-api` | Kubernetes service account |
| R5 | Secret paths: `secret/teams/identity/auth-api/config` | Secret paths |

## Acceptance criteria

The issue gives no acceptance criteria (`_No response_`).

## Non-goals

- Changes to any Vault other than a local one
- Secret values (paths only)
- Access to another team's or another service's paths
- Changes to the module, the platform layer or the policies

## Verification

The gate (`onboarding/bin/gate`) proves these against a throwaway Vault before merge:

- Policy `identity-auth-api` grants read and list on `secret/(data|metadata)/teams/identity/auth-api/` only
- Kubernetes auth role `identity-auth-api` is bound to `identity/auth-api` and carries only that policy
- A token with only that policy reads each path in R5 and is denied on write, delete, sibling services, other teams and `sys/`

## Assumptions

None
