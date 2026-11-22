#!/usr/bin/env python3
"""PreToolUse hook: the rules a tool call must not break.

Claude Code runs this before every Bash, Edit, Write and NotebookEdit call,
in the main session and inside every agent, in every permission mode. It
reads the call as JSON on stdin. To refuse, it prints a "deny" decision; to
allow, it prints nothing. Any crash refuses (see the bottom of the file).

Rules for everyone:
  - no merging a pull request (only onboarding/bin/merge merges)
  - no push outside onboard/*, no force push, no remote delete
  - no terraform apply/destroy and no Vault write to anything but 127.0.0.1
  - no applying a merged request (onboarding/bin/apply is a person's step)

Extra rules for agents (calls that carry an agent id):
  - file edits only inside onboarding/jobs/ and a worktree's requests/<id>/
  - no running the state or merge scripts
  - no shell command that could change the gate, the policies, the module,
    the template or this hook
"""
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}

# What judges a branch. Agents never change these.
PROTECTED = ["onboarding/bin", "onboarding/config.json", "onboarding/board", "policies/", ".claude/", "terraform/modules", "terraform/platform", "requests/_template"]

# Commands that only read. An agent command that names a protected path must be one of these.
READ_ONLY = {"cat", "ls", "head", "tail", "grep", "rg", "wc", "diff", "file", "stat", "less", "tree"}


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "onboarding guard: " + reason,
    }}))
    sys.exit(0)


def segments(command):
    """Split a shell line into its simple commands, each as a list of words."""
    out = []
    for part in re.split(r"&&|\|\||;|\||\n", command):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        if words:
            out.append(words)
    return out


def current_branch(directory):
    try:
        p = subprocess.run(["git", "-C", str(directory), "rev-parse", "--abbrev-ref", "HEAD"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


# ------------------------------------------------------------------- merging


def check_merge(command):
    lowered = command.lower()
    if re.search(r"\bgh\s+pr\s+merge\b", lowered):
        deny("agents and sessions do not merge pull requests. Only onboarding/bin/merge merges, after the gate.")
    if re.search(r"\bgh\s+api\b", lowered) and re.search(r"pulls/[^\s/]+/merge|mergepullrequest|enablepullrequestautomerge", lowered):
        deny("merging through the GitHub API is not allowed. Only onboarding/bin/merge merges.")


def check_apply(command):
    """The apply is the one step a person takes. Claude reads `apply --help` at most."""
    if re.search(r"onboarding/bin/apply\b(?!\s+(-h|--help)\b)", command):
        deny("applying to Vault is a person's step. Ask the person to run onboarding/bin/apply in their own terminal.")
    if re.search(r"onboarding/bin/job\s+applied\b", command):
        deny("only onboarding/bin/apply records a job as applied, and a person runs it.")


# ------------------------------------------------------------------- pushing


def check_push(command, cwd):
    directory = Path(cwd)
    for words in segments(command):
        if words[0] == "cd" and len(words) > 1:
            directory = (directory / words[1]).resolve()
            continue
        if words[0] != "git" or "push" not in words:
            continue
        repo = directory
        if "-C" in words[:words.index("push")]:
            repo = (directory / words[words.index("-C") + 1]).resolve()
        args = words[words.index("push") + 1:]
        flags = [a for a in args if a.startswith("-")]
        if any(f in ("-f", "-d", "--delete", "--mirror", "--all", "--prune") or f.startswith("--force") for f in flags):
            deny("force push, delete and push-everything are not allowed: " + " ".join(flags))
        refs = [a for a in args if not a.startswith("-")][1:]  # the first plain word is the remote
        if not refs:
            refs = ["HEAD"]
        for ref in refs:
            if ref.startswith("+") or ref.startswith(":"):
                deny("force push and remote delete are not allowed: " + ref)
            target = ref.split(":")[-1]
            if target == "HEAD":
                target = current_branch(repo)
            target = re.sub(r"^refs/heads/", "", target)
            if not target.startswith("onboard/"):
                deny("push is only allowed to onboard/* branches, not to %r. main changes only through merged pull requests." % (target or "an unknown branch"))


# -------------------------------------------------- Vault and Terraform writes

VAULT_WRITE = re.compile(
    r"\bvault\s+(write|delete|patch|kv\s+(put|patch|delete|destroy|undelete|metadata|rollback|enable-versioning)|"
    r"policy\s+(write|delete|fmt)|auth\s+(enable|disable|tune|move)|secrets\s+(enable|disable|tune|move)|"
    r"token\s+(create|revoke|renew)|lease|operator|namespace|plugin|login|unwrap)\b")
TERRAFORM_WRITE = re.compile(r"\bterraform\b[^|;&]*\b(apply|destroy|import)\b")
CURL_WRITE = re.compile(r"\bcurl\b[^|;&]*(-X\s*(POST|PUT|DELETE|PATCH)|--request|-d\b|--data)")


def host_of(address):
    address = address.strip("'\"")
    m = re.match(r"^(?:[a-z]+://)?(\[[^\]]+\]|[^:/\s]+)", address)
    return m.group(1).lower() if m else address


def check_vault_target(command):
    writes_vault = VAULT_WRITE.search(command) or TERRAFORM_WRITE.search(command)
    curl_vault = CURL_WRITE.search(command) and "/v1/" in command
    if not (writes_vault or curl_vault):
        return
    # Every address the command could be aimed at: named in the command, or inherited.
    found = re.findall(r"(?:VAULT_ADDR|TF_VAR_vault_addr|vault_addr|-address)\s*=\s*(\S+)", command)
    found += re.findall(r"(https?://[^\s'\"]+/v1/)", command)
    found += [os.environ[k] for k in ("VAULT_ADDR", "TF_VAR_vault_addr") if os.environ.get(k)]
    for address in found:
        if address.startswith("$"):
            deny("the Vault address is a variable the guard cannot read (%s). Name a 127.0.0.1 address explicitly." % address)
        if host_of(address) not in LOOPBACK:
            deny("writes go to a local Vault only. %r is not 127.0.0.1." % address)


# --------------------------------------------------------------- agent rules


def check_agent_shell(command):
    if re.search(r"onboarding/bin/(job|merge)\b", command):
        deny("agents do not run the state or merge scripts. Reply with your one line and stop; the orchestrator moves the job.")
    for words in segments(command):
        text = " ".join(words)
        if not any(p in text for p in PROTECTED):
            continue
        if words[0].endswith("onboarding/bin/gate"):
            continue  # running the gate is fine, changing it is not
        if words[0] == "git" and len(words) > 1 and words[1] in ("diff", "log", "show", "status"):
            continue
        if words[0] not in READ_ONLY or ">" in text:
            deny("agents may read but never change the gate, policies, module, template or hooks: " + text[:120])


def check_agent_edit(file_path):
    path = Path(os.path.realpath(file_path))  # realpath: no ../ or symlink tricks
    jobs = Path(os.path.realpath(ROOT / "onboarding" / "jobs"))
    worktrees = Path(os.path.realpath(ROOT / ".worktrees"))
    if jobs in path.parents:
        return
    if worktrees in path.parents:
        inside = path.relative_to(worktrees).parts  # (<job id>, "requests", <request id>, ...)
        if len(inside) >= 4 and inside[1] == "requests" and inside[2] == inside[0]:
            return
    deny("agents write only inside onboarding/jobs/ and their own worktree's requests/<id>/. Not: %s" % file_path)


def main():
    call = json.load(sys.stdin)
    tool = call.get("tool_name", "")
    tool_input = call.get("tool_input", {})
    is_agent = bool(call.get("agent_id") or call.get("agent_type"))

    if tool == "Bash":
        command = tool_input.get("command", "")
        check_merge(command)
        check_apply(command)
        check_push(command, call.get("cwd") or os.getcwd())
        check_vault_target(command)
        if is_agent:
            check_agent_shell(command)
    elif tool in ("Edit", "Write", "NotebookEdit") and is_agent:
        check_agent_edit(tool_input.get("file_path") or tool_input.get("notebook_path") or "")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 - a guard that cannot decide must refuse
        deny("the guard itself failed (%s: %s), so the call is refused." % (type(e).__name__, e))
