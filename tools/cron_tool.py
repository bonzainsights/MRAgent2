"""
MRAgent — Cron Tool
Allows the agent to autonomously schedule, list, and manage background tasks.

Created: 2026-03-02
"""

import json
from datetime import datetime, timezone

from config.settings import DATA_DIR
from utils.cron.service import CronService
from utils.cron.types import CronSchedule
from tools.base import Tool

# We instantiate a single CronService here so the tool has access to it.
# The actual async loop will be started by the background scheduler thread.
cron_service = CronService(store_path=DATA_DIR / "cron_jobs.json")

class CronTool(Tool):
    """
    Tool for scheduling periodic tasks or reminders.
    The agent can 'add', 'list', or 'remove' jobs.
    """
    name = "cron"
    description = "Manage autonomous scheduled tasks and reminders. Use this to schedule future code execution, periodic internet searches, or set reminders for the user."
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "What to do: 'add', 'remove', or 'list'.",
                "enum": ["add", "remove", "list"]
            },
            "message": {
                "type": "string",
                "description": "The task you (the agent) want to execute when this job triggers. Required if action is 'add'. Example: 'Check the weather in Tokyo and tell the user'."
            },
            "job_id": {
                "type": "string",
                "description": "The ID of the job to remove. Required if action is 'remove'."
            },
            "every_seconds": {
                "type": "integer",
                "description": "Schedule a recurring job every N seconds. Example: 3600 for every hour."
            },
            "cron_expr": {
                "type": "string",
                "description": "Standard cron expression (e.g., '0 9 * * *' for 9 AM daily)."
            },
            "at": {
                "type": "string",
                "description": "ISO 8601 string for a one-time reminder at a specific future time (e.g. '2026-10-21T07:28:00Z')."
            },
            "tz": {
                "type": "string",
                "description": "IANA timezone string for the cron_expr (e.g. 'America/New_York'). Defaults to local server time if absent."
            }
        },
        "required": ["action"]
    }

    def execute(self, action: str, **kwargs) -> str:
        if action == "list":
            jobs = cron_service.list_jobs(include_disabled=False)
            if not jobs:
                return "No active scheduled jobs."
            
            lines = ["Active jobs:"]
            for j in jobs:
                next_run_str = "None"
                if j.state.next_run_at_ms:
                    dt = datetime.fromtimestamp(j.state.next_run_at_ms / 1000, tz=timezone.utc)
                    next_run_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                
                desc = []
                if j.schedule.kind == "every":
                    desc.append(f"every {j.schedule.every_ms // 1000}s")
                elif j.schedule.kind == "cron":
                    desc.append(f"cron '{j.schedule.expr}'")
                    if j.schedule.tz:
                        desc.append(f"tz {j.schedule.tz}")
                elif j.schedule.kind == "at":
                    desc.append(f"at {next_run_str}")
                
                sch = ", ".join(desc)
                lines.append(f"- ID: {j.id} | message: '{j.payload.message}' | schedule: [{sch}] | next run: {next_run_str}")
            return "\\n".join(lines)

        elif action == "remove":
            job_id = kwargs.get("job_id")
            if not job_id:
                return "Error: missing required argument 'job_id' for action 'remove'."
            
            removed = cron_service.remove_job(job_id)
            if removed:
                return f"Successfully removed job {job_id}"
            else:
                return f"Job {job_id} not found."

        elif action == "add":
            msg = kwargs.get("message")
            if not msg:
                return "Error: missing required argument 'message' for action 'add'."

            # Parse schedule
            every_secs = kwargs.get("every_seconds")
            cron_expr = kwargs.get("cron_expr")
            at_iso = kwargs.get("at")
            tz = kwargs.get("tz")

            if every_secs:
                try:
                    every_secs = int(every_secs)
                except ValueError:
                    return f"Error: every_seconds must be an integer, got '{every_secs}'"
                schedule = CronSchedule(kind="every", every_ms=every_secs * 1000)
                name = f"every_{every_secs}s"
            elif cron_expr:
                schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
                name = f"cron_{cron_expr.replace(' ', '_')}"
            elif at_iso:
                try:
                    dt = datetime.fromisoformat(at_iso.replace("Z", "+00:00"))
                    at_ms = int(dt.timestamp() * 1000)
                    if at_ms <= int(datetime.now().timestamp() * 1000):
                        return f"Error: The scheduled time {at_iso} is in the past."
                    schedule = CronSchedule(kind="at", at_ms=at_ms)
                    name = f"at_{dt.strftime('%H%M')}"
                except ValueError as e:
                    return f"Error parsing ISO datetime '{at_iso}': {e}"
            else:
                return "Error: You must provide one of 'every_seconds', 'cron_expr', or 'at' to schedule a task."

            try:
                job = cron_service.add_job(
                    name=name,
                    schedule=schedule,
                    message=msg,
                    delete_after_run=(schedule.kind == "at"),
                )
                
                # Format response nicely
                dt_next = "None"
                if job.state.next_run_at_ms:
                    dt_obj = datetime.fromtimestamp(job.state.next_run_at_ms / 1000, tz=timezone.utc)
                    dt_next = dt_obj.strftime("%Y-%m-%d %H:%M:%S UTC")
                
                return f"Success! Added scheduling job {job.id}. Next run scheduled at: {dt_next}"
            except Exception as e:
                return f"Failed to add job: {e}"

        else:
            return f"Unknown action: {action}"
