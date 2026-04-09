import os

from agent_registry_client.client import AgentRegistryClient


class AgentRegistryClientFactory:
    """Create an AgentRegistryClient instance based on the configuration"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.default_base_url = os.environ.get("AGENT_REGISTRY_URL", "http://127.0.0.1:5000")

    def create_client(self, base_url: str = None, timeout: int = 30) -> AgentRegistryClient:
        """Create a client instance, with parameters that can override the factory's default configuration"""
        url = base_url or self.default_base_url
        timeout_seconds = timeout or self.config.get("timeout", 30)
        return AgentRegistryClient(url, timeout_seconds)

    def create_from_env(self) -> AgentRegistryClient:
        """Create a client from environment variables"""
        return self.create_client()
