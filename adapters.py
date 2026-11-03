"""Future provider boundary. Not imported by the demo; never silently falls back to API."""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Job:
    task_id: str
    owner: str
    prompt: str
    max_usd: float = 0

@dataclass(frozen=True)
class ProviderResult:
    text: str
    actual_usd: float
    provenance: str

class Adapter(Protocol):
    def available(self) -> bool: ...
    def run(self, job: Job) -> ProviderResult: ...

class DisabledCLI:
    def __init__(self, provider: str):
        self.provider = provider

    def available(self) -> bool:
        return False

    def run(self, job: Job) -> ProviderResult:
        raise RuntimeError(f'{self.provider}: official CLI/auth/terms and command approval bridge must be verified before activation; use manual handoff.')

ADAPTERS = {name: DisabledCLI(name) for name in ('FRIDAY', 'EDITH', 'VISION')}
