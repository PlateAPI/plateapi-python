from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Vehicle:
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    year_range: Optional[str] = None
    lowest_year: Optional[int] = None
    highest_year: Optional[int] = None
    body: Optional[str] = None
    engine: Optional[str] = None
    series: Optional[str] = None
    description: Optional[str] = None
    detailed_description: Optional[str] = None


@dataclass
class RateLimit:
    limit: Optional[int] = None
    remaining: Optional[int] = None
    plan: Optional[str] = None


@dataclass
class LookupResult:
    success: bool = False
    vehicle: Optional[Vehicle] = None
    alternatives: List[Vehicle] = field(default_factory=list)
    source: Optional[str] = None
    duration_ms: Optional[float] = None
    sandbox: bool = False
    code: Optional[str] = None
    error: Optional[str] = None
    rate_limit: Optional[RateLimit] = None


@dataclass
class Usage:
    used: int = 0
    limit: int = 0
    remaining: int = 0
    plan: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    topup_credits: int = 0


@dataclass
class LogEntry:
    plate: Optional[str] = None
    state: Optional[str] = None
    success: int = 0
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    client_ip: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class LogsResult:
    logs: List["LogEntry"] = field(default_factory=list)
    count: int = 0
    total: int = 0
    limit: int = 100
    offset: int = 0


@dataclass
class RotateResult:
    new_key: Optional[str] = None
    email: Optional[str] = None


@dataclass
class HealthStatus:
    status: str = "unknown"
    version: Optional[str] = None
