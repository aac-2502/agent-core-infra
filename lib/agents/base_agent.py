"""
Base agent class — agent-core-infra
All product agents inherit from BaseAgent and implement run().
"""
from abc import ABC, abstractmethod
from typing import Any

from .retry import with_retry


class BaseAgent(ABC):
    """
    Wraps a LangGraph node function in a class with built-in retry.

    Usage in a product pipeline:
        class MyAgent(BaseAgent):
            async def run(self, state: dict) -> dict:
                # process state, return only changed fields
                return {"some_field": result}

        node = MyAgent()
        graph.add_node("my_step", node)
    """

    retries: int = 3
    base_delay: float = 1.0
    name: str = "agent"

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """Process state and return a partial state update."""
        ...

    async def __call__(self, state: dict) -> dict:
        try:
            return await with_retry(
                self.run,
                state,
                retries=self.retries,
                base_delay=self.base_delay,
            )
        except Exception as exc:
            return {
                "status": "error",
                "error": f"[{self.name}] {exc}",
            }
