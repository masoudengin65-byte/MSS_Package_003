from dataclasses import dataclass


@dataclass
class Displacement:

    bullish: bool = False

    bearish: bool = False

    body_size: float = 0.0

    average_body: float = 0.0

    ratio: float = 0.0