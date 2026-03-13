import asyncio
import dataclasses
from typing import Callable, Optional


@dataclasses.dataclass
class StreamStatus:
    stream_id: str
    total: int
    completed: int
    failed: int
    pending: int
    status: str  # "running" | "completed" | "cancelled"


@dataclasses.dataclass(order=True)
class _ScrapeJob:
    priority: int
    sequence: int
    urls: list = dataclasses.field(compare=False)
    kwargs: dict = dataclasses.field(compare=False)
    result_queue: Optional[asyncio.Queue] = dataclasses.field(compare=False)
    stream_id: str = dataclasses.field(compare=False, default="")
    on_progress: Optional[Callable] = dataclasses.field(compare=False, default=None)
