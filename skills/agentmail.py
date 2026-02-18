"""
MRAgent — AgentMail Skill
Provides email capabilities via agentmail.to API.
"""

import os
import requests
import json
from typing import List

from skills.base import Skill
from tools.base import Tool


class AgentMailSkill(Skill):
    name = "agentmail"
    description = "Email capabilities via AgentMail.to"

    def get_tools(self) -> List[Tool]:
        return [
            CheckInboxTool(),
            SendEmailTool(),
        ]


class AgentMailTool(Tool):
    """Base tool for AgentMail operations."""
    
    def _get_api_key(self) -> str:
        key = os.getenv("AGENTMAIL_API_KEY")
        if not key:
            raise ValueError("Missing AGENTMAIL_API_KEY in .env")
        return key

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        api_key = self._get_api_key()
        url = f"https://api.agentmail.to/v0{endpoint}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, params=data, timeout=10)
            else:
                resp = requests.post(url, headers=headers, json=data, timeout=10)
            
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            return {"error": f"HTTP Error: {e.response.text if e.response else str(e)}"}
        except Exception as e:
            return {"error": str(e)}

    def _get_inbox_id(self) -> str:
        """Fetch the default inbox ID (email address)."""
        # 1. Check if we already have it cached
        if hasattr(self, "_cached_inbox_id"):
            return self._cached_inbox_id

        # 2. Fetch from API
        result = self._request("GET", "/inboxes")
        if "error" in result:
            raise ValueError(f"Could not fetch inbox ID: {result['error']}")
            
        inboxes = result.get("inboxes", [])
        if not inboxes:
            raise ValueError("No inboxes found for this API key.")
            
        # 3. Use the first inbox's email address as the ID
        self._cached_inbox_id = inboxes[0]["inbox_id"]
        return self._cached_inbox_id


class CheckInboxTool(AgentMailTool):
    name = "check_email"
    description = "Check recent emails in the inbox. Returns sender, subject, and snippet."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of emails to retrieve (default: 5)",
            },
        },
        "required": [],
    }

    def execute(self, limit: int = 5) -> str:
        try:
            inbox_id = self._get_inbox_id()
        except Exception as e:
            return f"❌ Error: {str(e)}"

        # Endpoint: GET /v0/inboxes/{inbox_id}/messages
        result = self._request("GET", f"/inboxes/{inbox_id}/messages", {"limit": limit})
        
        if "error" in result:
            return f"❌ Error checking inbox: {result['error']}"
            
        msgs = result.get("messages", [])
        if not msgs:
            return "📭 Inbox is empty."
            
        output = [f"📬 **Inbox ({inbox_id}):**"]
        for msg in msgs:
            sender = msg.get("from_address", "Unknown")
            subject = msg.get("subject", "No Subject")
            snippet = msg.get("snippet", "")
            msg_id = msg.get("message_id", "")
            output.append(f"- **From:** {sender} | **Subj:** {subject}\n  _{snippet}_")
            
        return "\n".join(output)


class SendEmailTool(AgentMailTool):
    name = "send_email"
    description = "Send an email to a recipient."
    parameters = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address",
            },
            "subject": {
                "type": "string",
                "description": "Email subject",
            },
            "body": {
                "type": "string",
                "description": "Email body content (text)",
            },
        },
        "required": ["to", "subject", "body"],
    }

    def execute(self, to: str, subject: str, body: str) -> str:
        try:
            inbox_id = self._get_inbox_id()
        except Exception as e:
            return f"❌ Error: {str(e)}"

        payload = {
            "to": [to], # API expects a list of strings
            "subject": subject,
            "text": body,  # API uses 'text' or 'html'
        }
        
        # Endpoint: POST /v0/inboxes/{inbox_id}/messages/send
        result = self._request("POST", f"/inboxes/{inbox_id}/messages/send", payload)
        
        if "error" in result:
            return f"❌ Failed to send email: {result['error']}"
            
        return f"✅ Email sent to {to}!"
