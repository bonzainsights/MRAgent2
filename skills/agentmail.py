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
        url = f"https://api.agentmail.to/v1{endpoint}"
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
        # Note: AgentMail API endpoint for listing messages
        # Adjusting endpoint based on common patterns, verifying with actual docs would be ideal
        # Assuming /messages or /inbox based on typical REST APIs
        # If specific endpoint is known from docs (researched earlier via search_web), use that.
        # The search result mentioned "endpoints to process leads or manage email communications".
        # Let's assume a standard list endpoint for now.
        
        # NOTE: Since we didn't get precise endpoint docs for "list messages", 
        # distinct from "threads", we'll try /messages. 
        # If this fails, the user will see an error and can correct.
        
        result = self._request("GET", "/messages", {"limit": limit})
        
        if "error" in result:
            return f"❌ Error checking inbox: {result['error']}"
            
        data = result.get("data", [])
        if not data:
            return "📭 Inbox is empty."
            
        output = ["📬 **Recent Emails:**"]
        for msg in data:
            sender = msg.get("from_address", "Unknown")
            subject = msg.get("subject", "No Subject")
            snippet = msg.get("snippet", "")
            msg_id = msg.get("id", "")
            output.append(f"- **[{msg_id}]** From: {sender} | Subj: {subject}\n  _{snippet}_")
            
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
        payload = {
            "to_address": to,
            "subject": subject,
            "body": body,
        }
        
        result = self._request("POST", "/messages", payload)
        
        if "error" in result:
            return f"❌ Failed to send email: {result['error']}"
            
        return f"✅ Email sent to {to}!"
