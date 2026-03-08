from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


BASE_DIR = Path(__file__).resolve().parent


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


@dataclass
class Action:
    type: str
    damage: int = 0
    block: int = 0
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


class Game:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.cards = self._load_cards(root / "cards.yaml")
        self.characters = self._load_characters(root / "characters.yaml")
        self.enemies = self._load_enemies(root / "enemies.yaml")
        self.status_defs = self._load_statuses(root / "statuses.yaml")

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_cards(self, path: Path) -> Dict[str, Card]:
        raw = self._load_yaml(path)
        cards: Dict[str, Card] = {}
        for key, value in raw.items():
            ctype = str(value.get("type", "Skill")).lower()
            explicit_target = value.get("target")
            if explicit_target == "all_enemies":
                target = "all_enemies"
            elif ctype == "attack":
                target = "single_enemy"
            else:
                target = "self"
            cards[key] = Card(
                key=key,
                name=str(value.get("name", key)),
                type=str(value.get("type", "Skill")),
                cost=int(value.get("cost", 0)),
                description=str(value.get("description", "")),
                damage=int(value.get("damage", 0)),
                block=int(value.get("block", 0)),
                heal=int(value.get("heal", 0)),
                vulnerable=int(value.get("vulnerable", 0)),
                weak=int(value.get("weak", 0)),
                target=target,
                hp_cost=int(value.get("hp_cost", 0)),
            )
        return cards

    def _load_characters(self, path: Path) -> Dict[str, dict]:
        return self._load_yaml(path)

    def _normalize_pattern(self, raw_pattern: object) -> List[List[Action]]:
        pattern: List[List[Action]] = []
        if not isinstance(raw_pattern, list):
            return pattern

        # Supports both [[{...}], [{...}]] and legacy [{...}, {...}] formats.
        if raw_pattern and isinstance(raw_pattern[0], dict):
            raw_pattern = [[x] for x in raw_pattern]

        for turn_actions in raw_pattern:
            if not isinstance(turn_actions, list):
                continue
            actions: List[Action] = []
            for item in turn_actions:
                if not isinstance(item, dict):
                    continue
                actions.append(
                    Action(
                        type=str(item.get("type", "attack")).lower(),
                        damage=int(item.get("damage", 0)),
                        block=int(item.get("block", 0)),
                        target=str(item.get("target", "player")),
                    )
                )
            if actions:
                pattern.append(actions)
        return pattern

    def _load_enemies(self, path: Path) -> Dict[str, Enemy]:
        raw = self._load_yaml(path)
        enemies: Dict[str, Enemy] = {}
        for key, value in raw.items():
            hp = int(value.get("health", 30))
            enemies[key] = Enemy(
                name=str(value.get("name", key)),
                max_hp=hp,
                hp=hp,
                ability=str(value.get("ability", "")),
                action_pattern=self._normalize_pattern(value.get("action_pattern", [])),
            )
        return enemies

    def _load_statuses(self, path: Path) -> Dict[str, dict]:
        return self._load_yaml(path)

    def choose_character(self) -> Player:
        keys = list(self.characters.keys())
        print("Choose your character:")
        for i, key in enumerate(keys, start=1):
            data = self.characters[key]
            print(f"  {i}. {data.get('name', key)} - {data.get('ability', '')}")

        while True:
            raw = input("Enter number: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(keys):
                chosen = self.characters[keys[int(raw) - 1]]
                deck_key = "inital_deck" if "inital_deck" in chosen else "initial_deck"
                deck = list(chosen.get(deck_key, []))
                hp = int(chosen.get("health", 80))
                player = Player(
                    name=str(chosen.get("name", "Player")),
                    max_hp=int(chosen.get("health_cap", hp)),
                    hp=hp,
                    deck=deck,
                )
                return player
            print("Invalid choice.")

    @staticmethod
    def _shuffle(cards: List[str]) -> None:
        random.shuffle(cards)

    def _refill_draw_pile(self, player: Player) -> None:
        if not player.draw_pile and player.discard_pile:
            player.draw_pile = player.discard_pile[:]
            player.discard_pile.clear()
            self._shuffle(player.draw_pile)

    def draw_cards(self, player: Player, count: int) -> None:
        for _ in range(count):
            self._refill_draw_pile(player)
            if not player.draw_pile:
                return
            player.hand.append(player.draw_pile.pop())

    @staticmethod
    def apply_damage(target: Entity, amount: int) -> int:
        if amount <= 0:
            return 0
        absorbed = min(target.block, amount)
        target.block -= absorbed
        dealt = amount - absorbed
        target.hp = max(0, target.hp - dealt)
        return dealt

    def _damage_multiplier_on_receive(self, target: Entity) -> float:
        if target.statuses.get("vulnerable", 0) > 0:
            ratio = self.status_defs.get("vulnerable", {}).get("ratio", 1.5)
            return float(ratio)
        return 1.0

    def _damage_multiplier_on_deal(self, source: Entity) -> float:
        if source.statuses.get("weak", 0) > 0:
            ratio = self.status_defs.get("weak", {}).get("ratio", 0.75)
            return float(ratio)
        return 1.0

    def deal_damage(self, source: Entity, target: Entity, base: int) -> int:
        dmg = int(round(base * self._damage_multiplier_on_deal(source)))
        dmg = int(round(dmg * self._damage_multiplier_on_receive(target)))
        return self.apply_damage(target, dmg)

    @staticmethod
    def heal(target: Entity, amount: int) -> int:
        if amount <= 0:
            return 0
        old = target.hp
        target.hp = min(target.max_hp, target.hp + amount)
        return target.hp - old

    def apply_status(self, target: Entity, status: str, turns: int) -> None:
        if turns <= 0:
            return
        target.statuses[status] = target.statuses.get(status, 0) + turns

    def process_status_start(self, target: Entity, turn_owner: str) -> None:
        # Applies trigger effects at turn start, then decreases duration by 1.
        for status, turns in list(target.statuses.items()):
            if turns <= 0:
                target.statuses.pop(status, None)
                continue

            definition = self.status_defs.get(status, {})
            timing = str(definition.get("timing", ""))
            should_trigger = (
                (turn_owner == "player" and "玩家" in timing)
                or (turn_owner == "enemy" and "敵人" in timing)
            )

            if should_trigger:
                if "damage" in definition:
                    dmg = int(definition.get("damage", 0))
                    dealt = self.apply_damage(target, dmg)
                    if dealt > 0:
                        print(f"  {target.name} suffers {dealt} from {status}.")
                if "heal" in definition:
                    healed = self.heal(target, int(definition.get("heal", 0)))
                    if healed > 0:
                        print(f"  {target.name} heals {healed} from {status}.")
                target.statuses[status] -= 1

            if target.statuses.get(status, 0) <= 0:
                target.statuses.pop(status, None)

    def show_battle_state(self, player: Player, enemies: List[Enemy], enemy_turn_counter: int) -> None:
        print("\n=== Battle State ===")
        print(f"Player: {player.name} HP {player.hp}/{player.max_hp} | Block {player.block} | Energy {player.energy}")
        if player.statuses:
            print(f"Player statuses: {player.statuses}")
        for idx, enemy in enumerate(enemies, start=1):
            status = "DEAD" if enemy.is_dead() else "ALIVE"
            print(f"[{idx}] {enemy.name} HP {enemy.hp}/{enemy.max_hp} | Block {enemy.block} | {status}")
            if enemy.statuses:
                print(f"    statuses: {enemy.statuses}")
            if not enemy.is_dead() and enemy.action_pattern:
                next_actions = enemy.action_pattern[enemy_turn_counter % len(enemy.action_pattern)]
                intent = ", ".join(
                    f"{a.type}(dmg={a.damage}, block={a.block})" for a in next_actions
                )
                print(f"    next intent: {intent}")

    def choose_target(self, enemies: List[Enemy]) -> Optional[Enemy]:
        alive = [e for e in enemies if not e.is_dead()]
        if not alive:
            return None
        while True:
            raw = input("Choose target enemy index: ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(enemies) and not enemies[idx].is_dead():
                    return enemies[idx]
            print("Invalid target.")

    def play_player_turn(self, player: Player, enemies: List[Enemy]) -> bool:
        # Returns True if battle should continue, False if battle ended.
        player.block = 0
        self.process_status_start(player, "player")
        if player.is_dead():
            return False

        player.energy = 3
        self.draw_cards(player, 5)

        while True:
            if player.is_dead():
                return False
            if all(e.is_dead() for e in enemies):
                return False

            self.show_battle_state(player, enemies, enemy_turn_counter=0)
            print("\nHand:")
            for i, card_key in enumerate(player.hand, start=1):
                card = self.cards[card_key]
                print(f"  {i}. {card.name} (cost {card.cost}) - {card.description}")
            print("  0. End turn")

            raw = input("Play card index: ").strip()
            if raw == "0":
                break
            if not raw.isdigit() or not (1 <= int(raw) <= len(player.hand)):
                print("Invalid card index.")
                continue

            hand_idx = int(raw) - 1
            card_key = player.hand[hand_idx]
            card = self.cards[card_key]

            if player.energy < card.cost:
                print("Not enough energy.")
                continue

            # Cost payment order follows README: pay first, then resolve effects.
            player.energy -= card.cost
            if card.hp_cost > 0:
                player.hp = max(0, player.hp - card.hp_cost)

            player.hand.pop(hand_idx)
            player.discard_pile.append(card_key)

            if player.is_dead():
                print("You died from card cost.")
                return False

            if card.target == "all_enemies":
                for enemy in enemies:
                    if enemy.is_dead():
                        continue
                    dealt = self.deal_damage(player, enemy, card.damage)
                    if dealt > 0:
                        print(f"{card.name} deals {dealt} to {enemy.name}.")
                    if card.vulnerable > 0 and not enemy.is_dead():
                        self.apply_status(enemy, "vulnerable", card.vulnerable)
                        print(f"{enemy.name} gains vulnerable x{card.vulnerable}.")
            elif card.target == "single_enemy":
                target = self.choose_target(enemies)
                if target is None:
                    return False
                dealt = self.deal_damage(player, target, card.damage)
                if dealt > 0:
                    print(f"{card.name} deals {dealt} to {target.name}.")
                if card.vulnerable > 0 and not target.is_dead():
                    self.apply_status(target, "vulnerable", card.vulnerable)
                    print(f"{target.name} gains vulnerable x{card.vulnerable}.")
                if card.weak > 0 and not target.is_dead():
                    self.apply_status(target, "weak", card.weak)
                    print(f"{target.name} gains weak x{card.weak}.")
            else:
                # Self-target skill/ability card.
                if card.damage > 0:
                    self.deal_damage(player, player, card.damage)
                if card.block > 0:
                    player.block += card.block
                    print(f"{player.name} gains {card.block} block.")
                if card.heal > 0:
                    healed = self.heal(player, card.heal)
                    print(f"{player.name} heals {healed} HP.")
                if card.vulnerable > 0:
                    self.apply_status(player, "vulnerable", card.vulnerable)
                if card.weak > 0:
                    self.apply_status(player, "weak", card.weak)

            # Generic effects also apply if present.
            if card.block > 0 and card.target != "self":
                player.block += card.block
                print(f"{player.name} gains {card.block} block.")
            if card.heal > 0 and card.target != "self":
                healed = self.heal(player, card.heal)
                print(f"{player.name} heals {healed} HP.")

        # End of player turn: discard remaining hand.
        player.discard_pile.extend(player.hand)
        player.hand.clear()
        return True

    def play_enemy_turn(self, player: Player, enemies: List[Enemy], enemy_turn_counter: int) -> bool:
        # Returns True if battle should continue, False if battle ended.
        for enemy in enemies:
            if enemy.is_dead():
                continue
            enemy.block = 0
            self.process_status_start(enemy, "enemy")

        for enemy in enemies:
            if enemy.is_dead():
                continue
            if not enemy.action_pattern:
                continue

            turn_actions = enemy.action_pattern[enemy_turn_counter % len(enemy.action_pattern)]
            print(f"\n{enemy.name} acts:")
            for action in turn_actions:
                if enemy.is_dead():
                    break
                atype = action.type.lower()
                if atype == "attack":
                    dealt = self.deal_damage(enemy, player, action.damage)
                    print(f"  attack for {dealt} damage.")
                elif atype == "defend":
                    enemy.block += action.block
                    print(f"  gains {action.block} block.")
                else:
                    # Unknown actions are ignored in this PoC.
                    print(f"  unknown action '{action.type}' skipped.")

                if player.is_dead():
                    return False

        if all(e.is_dead() for e in enemies):
            return False
        return True

    def clone_enemy(self, source: Enemy, hp_scale: float = 1.0, dmg_scale: float = 1.0) -> Enemy:
        pattern: List[List[Action]] = []
        for turn in source.action_pattern:
            copied_turn: List[Action] = []
            for a in turn:
                copied_turn.append(
                    Action(
                        type=a.type,
                        damage=max(0, int(round(a.damage * dmg_scale))),
                        block=max(0, int(round(a.block * dmg_scale))),
                        target=a.target,
                    )
                )
            pattern.append(copied_turn)

        hp = max(1, int(round(source.max_hp * hp_scale)))
        return Enemy(
            name=source.name,
            max_hp=hp,
            hp=hp,
            action_pattern=pattern,
            ability=source.ability,
        )

    def build_battle(self, battle_index: int, is_boss: bool) -> List[Enemy]:
        templates = list(self.enemies.values())
        if not templates:
            raise RuntimeError("No enemies loaded from enemies.yaml")

        if is_boss:
            template = max(templates, key=lambda e: e.max_hp)
            boss = self.clone_enemy(template, hp_scale=2.3, dmg_scale=1.5)
            boss.name = f"Boss {boss.name}"
            return [boss]

        count = random.choice([1, 2])
        picks = random.sample(templates, k=min(count, len(templates)))
        return [self.clone_enemy(p, hp_scale=1.0 + battle_index * 0.08, dmg_scale=1.0 + battle_index * 0.05) for p in picks]

    def run_battle(self, player: Player, enemies: List[Enemy], battle_no: int, total: int) -> bool:
        print(f"\n{'=' * 30}")
        print(f"Battle {battle_no}/{total}")
        print("Enemies:")
        for e in enemies:
            print(f"  - {e.name} (HP {e.hp})")

        # Prepare player deck for each battle.
        player.draw_pile = player.deck[:]
        player.discard_pile.clear()
        player.hand.clear()
        self._shuffle(player.draw_pile)

        enemy_turn_counter = 0
        while True:
            ongoing = self.play_player_turn(player, enemies)
            if player.is_dead():
                return False
            if all(e.is_dead() for e in enemies):
                print("You win this battle.")
                return True
            if not ongoing:
                return False

            ongoing = self.play_enemy_turn(player, enemies, enemy_turn_counter)
            enemy_turn_counter += 1
            if player.is_dead():
                print("You were defeated.")
                return False
            if all(e.is_dead() for e in enemies):
                print("You win this battle.")
                return True
            if not ongoing:
                return False

    def run_campaign(self) -> None:
        print("Card Game Proof of Concept")
        print("=" * 30)

        player = self.choose_character()
        print(f"\nSelected: {player.name} (HP {player.hp}/{player.max_hp})")

        normal_battles = 5
        for i in range(1, normal_battles + 1):
            enemies = self.build_battle(i, is_boss=False)
            won = self.run_battle(player, enemies, battle_no=i, total=normal_battles + 1)
            if not won:
                print("\nGame Over.")
                return
            # Small post-battle recovery to keep PoC playable.
            recovered = self.heal(player, max(1, int(player.max_hp * 0.1)))
            print(f"After battle recovery: +{recovered} HP (now {player.hp}/{player.max_hp})")

        boss = self.build_battle(normal_battles + 1, is_boss=True)
        won = self.run_battle(player, boss, battle_no=normal_battles + 1, total=normal_battles + 1)
        if won and not player.is_dead():
            print("\nYou defeated the final boss. Victory!")
        else:
            print("\nDefeated at the final battle.")


def main() -> None:
    game = Game(BASE_DIR)
    game.run_campaign()


if __name__ == "__main__":
    main()
