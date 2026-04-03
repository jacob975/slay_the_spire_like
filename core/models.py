from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Card:
    key: str
    name: str
    type: str
    cost: int
    description: str = ""
    damage: int = 0
    block: int = 0
    heal: int = 0
    vulnerable: int = 0
    weak: int = 0
    target: str = "single_enemy"
    hp_cost: int = 0
    draw: int = 0
    discard: int = 0
    draw_until_non_attack: bool = False
    copy_to_discard: bool = False


@dataclass
class Action:
    type: str
    damage: int = 0
    block: int = 0
    heal: int = 0
    target: str = "player"


@dataclass
class Entity:
    name: str
    max_hp: int
    hp: int
    block: int = 0
    statuses: Dict[str, int] = field(default_factory=dict)

    def is_dead(self) -> bool:
        return self.hp <= 0


@dataclass
class Enemy(Entity):
    action_pattern: List[List[Action]] = field(default_factory=list)
    ability: str = ""


@dataclass
class Player(Entity):
    energy: int = 0
    deck: List[str] = field(default_factory=list)
    draw_pile: List[str] = field(default_factory=list)
    discard_pile: List[str] = field(default_factory=list)
    hand: List[str] = field(default_factory=list)
