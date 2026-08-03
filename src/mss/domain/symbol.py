from dataclasses import dataclass


@dataclass
class Symbol:

    name: str
    description: str
    path: str
    digits: int
    spread: int
    trade_mode: int
    visible: bool