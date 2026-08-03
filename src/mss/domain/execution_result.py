"""
MSS Execution Result
Version : 1.0
Sprint : 11.0
Compatible : v0.22
"""

from dataclasses import dataclass


@dataclass
class ExecutionResult:

    success: bool = False

    retcode: int = 0

    order: int = 0

    deal: int = 0

    volume: float = 0.0

    price: float = 0.0

    comment: str = ""

    request_id: int = 0

    raw_result = None