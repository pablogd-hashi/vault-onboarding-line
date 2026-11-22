#!/usr/bin/env python3
"""Tests for guard.py: every denial must deny, ordinary work must pass.

Run: python3 .claude/hooks/guard_test.py
Each case feeds the guard the same JSON Claude Code would send it.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).with_name("guard.py")
ROOT = GUARD.resolve().parents[2]

# A scratch repository sitting on an onboard/* branch, and one on main.
scratch = Path(tempfile.mkdtemp(prefix="guard-test-"))
for name, branch in (("job", "onboard/GH-1-demo"), ("main", "main")):
    repo = scratch / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                    "--allow-empty", "-m", "init"], check=True)
ON_JOB, ON_MAIN = str(scratch / "job"), str(scratch / "main")

AGENT = {"agent_id": "a1", "agent_type": "builder"}
WT = str(ROOT / ".worktrees" / "GH-1-demo")


def bash(command, cwd=ON_JOB, **extra):
    return dict({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}, **extra)


def edit(path, **extra):
    return dict({"tool_name": "Write", "tool_input": {"file_path": path}, "cwd": str(ROOT)}, **extra)


DENY, ALLOW = True, False
CASES = [
    # --- merging
    (DENY, "gh pr merge", bash("gh pr merge 12 --squash")),
    (DENY, "gh pr merge by an agent", bash("cd /tmp && gh pr merge 12", **AGENT)),
    (DENY, "merge through the API", bash("gh api -X PUT repos/o/r/pulls/12/merge")),
    (ALLOW, "open a draft PR", bash("gh pr create --draft --base main --head onboard/GH-1-demo --title t --body 'Closes #1'")),
    (ALLOW, "comment on a PR", bash("gh pr comment 12 --body-file x.md")),
    # --- pushing
    (ALLOW, "push own onboard branch", bash("git push origin onboard/GH-1-demo")),
    (ALLOW, "push -u HEAD on an onboard branch", bash("git push -u origin HEAD")),
    (ALLOW, "bare push on an onboard branch", bash("git push")),
    (DENY, "bare push on main", bash("git push", cwd=ON_MAIN)),
    (DENY, "push main", bash("git push origin main")),
    (DENY, "push HEAD to main", bash("git push origin HEAD:main")),
    (DENY, "push onboard branch onto main", bash("git push origin onboard/GH-1-demo:refs/heads/main")),
    (DENY, "push after cd to main checkout", bash("cd %s && git push" % ON_MAIN)),
    (DENY, "git -C main push", bash("git -C %s push origin HEAD" % ON_MAIN)),
    (DENY, "force push", bash("git push --force origin onboard/GH-1-demo")),
    (DENY, "force push short flag", bash("git push -f origin onboard/GH-1-demo")),
    (DENY, "force with lease", bash("git push --force-with-lease origin onboard/GH-1-demo")),
    (DENY, "force by plus refspec", bash("git push origin +onboard/GH-1-demo")),
    (DENY, "delete a remote branch", bash("git push origin --delete onboard/GH-1-demo")),
    (DENY, "delete by empty refspec", bash("git push origin :onboard/GH-1-demo")),
    (ALLOW, "commit", bash("git add -A && git commit -m 'request'")),
    # --- Vault and Terraform targets
    (ALLOW, "terraform apply, default local address", bash("terraform -chdir=requests/x/03-terraform apply -auto-approve")),
    (ALLOW, "terraform apply to 127.0.0.1", bash("TF_VAR_vault_addr=http://127.0.0.1:8200 terraform apply")),
    (DENY, "terraform apply to a real Vault", bash("TF_VAR_vault_addr=https://vault.corp.example:8200 terraform apply")),
    (DENY, "terraform apply -var real Vault", bash("terraform apply -var vault_addr=https://vault.corp.example:8200")),
    (DENY, "terraform destroy on a real Vault", bash("VAULT_ADDR=https://10.0.0.5:8200 terraform destroy")),
    (ALLOW, "terraform plan anywhere", bash("VAULT_ADDR=https://vault.corp.example:8200 terraform plan")),
    (ALLOW, "vault kv put local", bash("VAULT_ADDR=http://127.0.0.1:8200 vault kv put secret/x a=b")),
    (DENY, "vault kv put remote", bash("VAULT_ADDR=https://vault.corp.example:8200 vault kv put secret/x a=b")),
    (DENY, "vault policy write remote by flag", bash("vault policy write -address=https://vault.corp.example:8200 p p.hcl")),
    (DENY, "vault write, address hidden in a variable", bash("VAULT_ADDR=$PROD vault write secret/x a=b")),
    (ALLOW, "vault read remote", bash("VAULT_ADDR=https://vault.corp.example:8200 vault kv get secret/x")),
    (DENY, "curl write to a real Vault", bash("curl -X POST https://vault.corp.example:8200/v1/secret/data/x -d '{}'")),
    # --- agents: scripts and protected files
    (DENY, "agent runs the state script", bash("onboarding/bin/job approve 12", **AGENT)),
    (DENY, "agent runs the merge script", bash("%s/onboarding/bin/merge 12" % ROOT, **AGENT)),
    (ALLOW, "agent runs the gate", bash("%s/onboarding/bin/gate" % ROOT, **AGENT)),
    (ALLOW, "agent formats its own Terraform", bash("cd %s && terraform fmt requests/GH-1-demo/03-terraform/main.tf" % WT, **AGENT)),
    (ALLOW, "agent commits its request", bash("git -C %s add requests/GH-1-demo && git -C %s commit -m 'GH-1-demo: onboard demo'" % (WT, WT), **AGENT)),
    (ALLOW, "agent reads the policy", bash("cat %s/policies/conftest/onboard.rego" % ROOT, **AGENT)),
    (DENY, "agent overwrites the gate", bash("echo 'exit 0' > %s/onboarding/bin/gate" % ROOT, **AGENT)),
    (DENY, "agent seds the policy", bash("sed -i '' 's/read/update/' policies/conftest/onboard.rego", **AGENT)),
    (DENY, "agent removes the hook", bash("rm .claude/hooks/guard.py", **AGENT)),
    (DENY, "agent edits the module by script", bash("python3 -c \"open('terraform/modules/vault-service-onboard/main.tf','w')\"", **AGENT)),
    (DENY, "agent checks out an old template", bash("git checkout HEAD~3 -- requests/_template", **AGENT)),
    (ALLOW, "main session edits the gate", bash("sed -i '' 's/a/b/' onboarding/bin/gate")),
    # --- agents: file edits
    (ALLOW, "agent writes into its job folder", edit(str(ROOT / "onboarding/jobs/GH-1-demo/intake.md"), **AGENT)),
    (ALLOW, "agent writes its request", edit(WT + "/requests/GH-1-demo/01-spec/spec.md", **AGENT)),
    (DENY, "agent writes another request in its worktree", edit(WT + "/requests/PE-001-payments-api/03-terraform/main.tf", **AGENT)),
    (DENY, "agent writes the template in its worktree", edit(WT + "/requests/_template/03-terraform/main.tf", **AGENT)),
    (DENY, "agent writes the gate", edit(str(ROOT / "onboarding/bin/gate"), **AGENT)),
    (DENY, "agent writes the policy", edit(str(ROOT / "policies/conftest/onboard.rego"), **AGENT)),
    (DENY, "agent writes the hook settings", edit(str(ROOT / ".claude/settings.json"), **AGENT)),
    (DENY, "agent writes a request in the main checkout", edit(str(ROOT / "requests/GH-1-demo/01-spec/spec.md"), **AGENT)),
    (DENY, "agent escapes with ../", edit(str(ROOT / "onboarding/jobs/../bin/gate"), **AGENT)),
    (ALLOW, "main session writes the gate", edit(str(ROOT / "onboarding/bin/gate"))),
]


def decide(payload, raw=None):
    env = {k: v for k, v in os.environ.items() if k not in ("VAULT_ADDR", "TF_VAR_vault_addr")}
    p = subprocess.run([sys.executable, str(GUARD)], input=raw if raw is not None else json.dumps(payload),
                       stdout=subprocess.PIPE, text=True, env=env)
    return '"permissionDecision": "deny"' in p.stdout


failed = 0
for expected, name, payload in CASES:
    got = decide(payload)
    failed += got != expected
    print("%s  %-5s %s" % ("ok  " if got == expected else "FAIL", "deny" if got else "allow", name))

# A guard that cannot read its input must refuse, not wave the call through.
got = decide(None, raw="not json")
failed += not got
print("%s  %-5s %s" % ("ok  " if got else "FAIL", "deny" if got else "allow", "broken input is refused"))

print("\n%d cases, %d failed" % (len(CASES) + 1, failed))
sys.exit(1 if failed else 0)
