"""
MRAgent — Web Skill
Exposes web searching and webpage fetching capabilities to the agent.
"""

from typing import List
from skills.base import Skill
from tools.base import Tool
from tools.web import WebSearchTool, WebFetchTool


class WebSkill(Skill):
    """
    Skill for browsing the Internet, retrieving search results and reading
    full articles via HTTP fetch.
    """

    name = "web"
    description = "Core internet searching and URL reading capabilities."

    def get_tools(self) -> List[Tool]:
        return [
            WebSearchTool(),
            WebFetchTool(),
        ]
