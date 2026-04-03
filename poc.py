from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from card_effects import CardPlayContext, resolve_card_effects
# Re-export models from core so card_effects.py TYPE_CHECKING imports still resolve.
from core.models import Action, Card, Enemy, Entity, Player  # noqa: F401


BASE_DIR = Path(__file__).resolve().parent


class Game:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.cards = self._load_cards(root / "cards.yaml")
        self.characters = self._load_characters(root / "characters.yaml")
        self.enemies = self._load_enemies(root / "enemies.yaml")
        self.status_defs = self._load_statuses(root / "statuses.yaml")
        # UI / battle state
        self.battle_log: List[str] = []
        self.battle_no: int = 0
        self.battle_total: int = 0
        self._current_turn_counter: int = 0
        self._battle_player: Optional[Player] = None
        self._battle_enemies: List[Enemy] = []

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
                draw=int(value.get("draw", 0)),
                discard=int(value.get("discard", 0)),
                draw_until_non_attack=bool(value.get("draw_until_non_attack", False)),
                copy_to_discard=bool(value.get("copy_to_discard", False)),
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
                        heal=int(item.get("heal", 0)),
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

    def _clear_screen(self) -> None:
        """Clear the terminal using ANSI escape codes."""
        print("\033[2J\033[H", end="", flush=True)

    def _hp_bar(self, current: int, maximum: int, width: int = 16) -> str:
        if maximum <= 0:
            return "░" * width
        filled = max(0, min(width, int(round(current / maximum * width))))
        return "█" * filled + "░" * (width - filled)

    def _energy_pips(self, current: int, maximum: int = 3) -> str:
        return "●" * current + "○" * max(0, maximum - current)

    def _log(self, msg: str) -> None:
        """Append a message to the battle log (keeps last 8 entries)."""
        self.battle_log.append(msg)
        if len(self.battle_log) > 8:
            self.battle_log.pop(0)

    def show_battle_ui(
        self,
        player: "Player",
        enemies: List["Enemy"],
        show_hand: bool = True,
        prompt_message: str = "",
    ) -> None:
        """Clear the screen and render the complete battle UI."""
        self._clear_screen()
        W = 76
        SEP = "═" * W
        THIN = "─" * W

        # Header
        title = f" BATTLE {self.battle_no}/{self.battle_total} "
        pad_l = (W - len(title)) // 2
        pad_r = W - pad_l - len(title)
        print("═" * pad_l + title + "═" * pad_r)

        # Enemies
        print(" ENEMIES")
        print(THIN)
        for idx, enemy in enumerate(enemies, start=1):
            bar = self._hp_bar(enemy.hp, enemy.max_hp)
            if enemy.is_dead():
                print(f"  [{idx}] {enemy.name:<16} {bar} {enemy.hp:>3}/{enemy.max_hp:<3}  [DEAD]")
            else:
                print(f"  [{idx}] {enemy.name:<16} {bar} {enemy.hp:>3}/{enemy.max_hp:<3}  Blk:{enemy.block}")
                if enemy.statuses:
                    st = "  ".join(f"{k}({v})" for k, v in enemy.statuses.items())
                    print(f"       Statuses: {st}")
                if enemy.action_pattern:
                    acts = enemy.action_pattern[
                        self._current_turn_counter % len(enemy.action_pattern)
                    ]
                    parts: List[str] = []
                    for a in acts:
                        if a.type.lower() == "attack":
                            parts.append(f"Attack {a.damage} dmg")
                        elif a.type.lower() == "defend":
                            parts.append(f"Defend +{a.block} blk")
                        else:
                            parts.append(a.type)
                    print(f"       Intent:   {', '.join(parts)}")

        # Player
        print(THIN)
        bar = self._hp_bar(player.hp, player.max_hp)
        energy = self._energy_pips(player.energy)
        print(
            f" {player.name:<16} {bar} {player.hp:>3}/{player.max_hp:<3}"
            f"  Blk:{player.block}  Energy: {energy}"
        )
        if player.statuses:
            st = "  ".join(f"{k}({v})" for k, v in player.statuses.items())
            print(f" Statuses: {st}")

        # Battle log
        if self.battle_log:
            print(THIN)
            print(" LOG")
            for msg in self.battle_log[-6:]:
                print(f"  {msg}")

        # Hand
        if show_hand:
            print(THIN)
            pile_info = f"Draw: {len(player.draw_pile)}   Discard: {len(player.discard_pile)}"
            print(f" HAND  [{len(player.hand)} cards]   {pile_info}")
            print(THIN)
            for i, card_key in enumerate(player.hand, start=1):
                card = self.cards[card_key]
                print(f"  [{i}] {card.name:<20} ({card.cost})  {card.description}")

        print(SEP)
        if prompt_message:
            print(f"  {prompt_message}")
        elif show_hand:
            print("  [0] End Turn")

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
                        self._log(f"{target.name} suffers {dealt} from {status}.")
                if "heal" in definition:
                    healed = self.heal(target, int(definition.get("heal", 0)))
                    if healed > 0:
                        self._log(f"{target.name} heals {healed} from {status}.")
                target.statuses[status] -= 1

            if target.statuses.get(status, 0) <= 0:
                target.statuses.pop(status, None)

    def draw_cards_until_non_attack(self, player: Player) -> None:
        """Keep drawing cards one at a time until a non-Attack card is drawn."""
        while True:
            before = len(player.hand)
            self.draw_cards(player, 1)
            if len(player.hand) == before:
                break
            drawn_card = self.cards[player.hand[-1]]
            self._log(f"Drew {drawn_card.name}.")
            if drawn_card.type.lower() != "attack":
                break

    def choose_discard(self, player: Player, count: int) -> None:
        """Ask the player to choose `count` cards from hand to discard."""
        for _ in range(count):
            if not player.hand:
                return
            self.show_battle_ui(
                player,
                self._battle_enemies or [],
                show_hand=True,
                prompt_message="Choose a card to discard (enter card index):",
            )
            while True:
                raw = input("> ").strip()
                if raw.isdigit() and 1 <= int(raw) <= len(player.hand):
                    idx = int(raw) - 1
                    discarded = player.hand.pop(idx)
                    player.discard_pile.append(discarded)
                    self._log(f"Discarded {self.cards[discarded].name}.")
                    break
                print("  Invalid choice. ", end="", flush=True)

    def choose_target(self, enemies: List[Enemy]) -> Optional[Enemy]:
        alive = [e for e in enemies if not e.is_dead()]
        if not alive:
            return None
        self.show_battle_ui(
            self._battle_player or alive[0],
            enemies,
            show_hand=False,
            prompt_message="Choose target enemy (enter enemy index):",
        )
        while True:
            raw = input("> ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(enemies) and not enemies[idx].is_dead():
                    return enemies[idx]
            print("  Invalid target. ", end="", flush=True)

    def play_player_turn(self, player: Player, enemies: List[Enemy], enemy_turn_counter: int = 0) -> bool:
        # Returns True if battle should continue, False if battle ended.
        self._battle_player = player
        self._battle_enemies = enemies
        self._current_turn_counter = enemy_turn_counter

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

            self.show_battle_ui(player, enemies)
            raw = input("\n> Play card (or 0 to end turn): ").strip()

            if raw == "0":
                break
            if not raw.isdigit() or not (1 <= int(raw) <= len(player.hand)):
                self._log("Invalid card index.")
                continue

            hand_idx = int(raw) - 1
            card_key = player.hand[hand_idx]
            card = self.cards[card_key]

            if player.energy < card.cost:
                self._log("Not enough energy.")
                continue

            # Cost payment order follows README: pay first, then resolve effects.
            player.energy -= card.cost
            if card.hp_cost > 0:
                player.hp = max(0, player.hp - card.hp_cost)
                self._log(f"{player.name} paid {card.hp_cost} HP.")

            player.hand.pop(hand_idx)
            player.discard_pile.append(card_key)

            if player.is_dead():
                self._log("You died from card cost.")
                return False

            card_context = CardPlayContext(
                game=self,
                player=player,
                enemies=enemies,
                card=card,
                card_key=card_key,
            )
            if not resolve_card_effects(card_context):
                return False

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

        self.battle_log.clear()
        for enemy in enemies:
            if enemy.is_dead():
                continue
            if not enemy.action_pattern:
                continue

            turn_actions = enemy.action_pattern[enemy_turn_counter % len(enemy.action_pattern)]
            self._log(f"── {enemy.name} acts ──")
            for action in turn_actions:
                if enemy.is_dead():
                    break
                atype = action.type.lower()
                if atype == "attack":
                    dealt = self.deal_damage(enemy, player, action.damage)
                    self._log(f"  → attacks for {dealt} damage.")
                elif atype == "defend":
                    enemy.block += action.block
                    self._log(f"  → gains {action.block} block.")
                else:
                    self._log(f"  → {action.type} (skipped).")

                if player.is_dead():
                    self.show_battle_ui(player, enemies, show_hand=False)
                    print("\n  You were defeated.")
                    return False

        if all(e.is_dead() for e in enemies):
            return False

        # Show the result of the enemy turn, then wait for the player.
        self.show_battle_ui(player, enemies, show_hand=False)
        input("\n  [Press Enter to start your turn] ")
        self.battle_log.clear()
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
        self.battle_no = battle_no
        self.battle_total = total
        self.battle_log.clear()

        # Prepare player deck for each battle.
        player.draw_pile = player.deck[:]
        player.discard_pile.clear()
        player.hand.clear()
        self._shuffle(player.draw_pile)

        enemy_turn_counter = 0
        while True:
            ongoing = self.play_player_turn(player, enemies, enemy_turn_counter)
            if player.is_dead():
                return False
            if all(e.is_dead() for e in enemies):
                self._clear_screen()
                print("\n You cleared the battle!")
                return True
            if not ongoing:
                return False

            ongoing = self.play_enemy_turn(player, enemies, enemy_turn_counter)
            enemy_turn_counter += 1
            if player.is_dead():
                return False
            if all(e.is_dead() for e in enemies):
                self._clear_screen()
                print("\n You cleared the battle!")
                return True
            if not ongoing:
                return False

    def offer_card_reward(self, player: Player) -> None:
        """Let the player choose one of three random cards to add to their deck."""
        all_keys = list(self.cards.keys())
        if not all_keys:
            return
        picks = random.sample(all_keys, k=min(3, len(all_keys)))
        print("\n--- Card Reward ---")
        print("Choose a card to add to your deck:")
        for i, key in enumerate(picks, start=1):
            card = self.cards[key]
            print(f"  {i}. {card.name} (cost {card.cost}) - {card.description}")
        print("  0. Skip")

        while True:
            raw = input("Enter number: ").strip()
            if raw == "0":
                print("Skipped card reward.")
                return
            if raw.isdigit() and 1 <= int(raw) <= len(picks):
                chosen_key = picks[int(raw) - 1]
                player.deck.append(chosen_key)
                print(f"Added {self.cards[chosen_key].name} to your deck.")
                return
            print("Invalid choice.")

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
            self.offer_card_reward(player)

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
