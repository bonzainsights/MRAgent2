"""
MRAgent — Skills Base
Defines the base Skill class for modular capabilities.
"""

from abc import ABC, abstractmethod
from typing import List

from tools.base import Tool
from utils.logger import get_logger


class Skill(ABC):
    """
    Base class for a Skill.
    A Skill is a collection of Tools that provide a specific capability.
    """

    name: str = ""
    description: str = ""

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__
        self.logger = get_logger(f"skills.{self.name}")

    @abstractmethod
    def get_tools(self) -> List[Tool]:
        """Return the list of tools provided by this skill."""
        pass
