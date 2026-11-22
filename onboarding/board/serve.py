#!/usr/bin/env python3
"""The local board: one page that shows every job moving down the line.

  python3 onboarding/board/serve.py [port]      then open http://127.0.0.1:8765

It only reads. Job state comes from onboarding/jobs/<id>/job.json, which
onboarding/bin/job writes. Standard library only, bound to 127.0.0.1.
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MAIN = Path(__file__).resolve().parents[2]
JOBS = MAIN / "onboarding" / "jobs"
PAGE = Path(__file__).with_name("index.html")

JOB_ID = re.compile(r"GH-[0-9]+-[a-z0-9-]+")
# The only files the page may ask for. Nothing else on disk is reachable.
STEP_FILE = re.compile(r"(issue|intake|build|decision|feedback-[0-9]+)\.md|round-[0-9]+/(gate|review)\.md|round-[0-9]+/merge/gate\.md")


def steps(job):
    """The files of a job, in the order the line produced them."""
    folder = JOBS / job["id"]
    found = [name for name in ("issue.md", "intake.md") if (folder / name).is_file()]
    if spec_path(job):
        found.append("spec.md")
    if (folder / "build.md").is_file():
        found.append("build.md")
    for rnd in sorted(folder.glob("round-*"), key=lambda p: int(p.name.split("-")[1])):
        found += ["%s/%s" % (rnd.name, f) for f in ("gate.md", "review.md", "merge/gate.md") if (rnd / f).is_file()]
    found += sorted(p.name for p in folder.glob("feedback-*.md"))
    if (folder / "decision.md").is_file():
        found.append("decision.md")
    return found


def spec_path(job):
    """The spec lives in the job's worktree until the merge, then in the main checkout."""
    for root in (Path(job.get("worktree") or "/nonexistent"), MAIN):
        path = root / "requests" / job["id"] / "01-spec" / "spec.md"
        if path.is_file():
            return path
    return None


def read_jobs():
    jobs = []
    for path in sorted(JOBS.glob("GH-*/job.json")):
        try:
            job = json.loads(path.read_text())
        except (ValueError, OSError):
            continue  # being replaced right now; it will be there on the next poll
        job["steps"] = steps(job)
        jobs.append(job)
    return jobs


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/":
            return self.reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/jobs":
            return self.reply(200, json.dumps(read_jobs()), "application/json")
        if url.path == "/api/file":
            job_id, name = query.get("job", [""])[0], query.get("name", [""])[0]
            if JOB_ID.fullmatch(job_id) and (name == "spec.md" or STEP_FILE.fullmatch(name)):
                job_file = JOBS / job_id / "job.json"
                if job_file.is_file():
                    path = spec_path(json.loads(job_file.read_text())) if name == "spec.md" else JOBS / job_id / name
                    if path and path.is_file():
                        return self.reply(200, path.read_text(), "text/plain; charset=utf-8")
        self.reply(404, "not found", "text/plain")

    def log_message(self, *args):  # a poll every two seconds would flood the terminal
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print("Onboarding board: http://127.0.0.1:%d   (Ctrl-C to stop)" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
