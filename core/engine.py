from __future__ import annotations

import random
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from core.models import Action, Card, Enemy, Entity, Player


BASE_DIR = Path(__file__).resolve().parent.parent


class BattleState(Enum):
    IDLE               = auto()
    PLAYER_TURN_START  = auto()
    PLAYER_ACTION      = auto()
    CHOOSING_TARGET    = auto()
    CHOOSING_DISCARD   = auto()
    ENEMY_TURN         = auto()
    BATTLE_WON         = auto()
    BATTLE_LOST        = auto()


class GameEngine:
    """Pure game logic — no I/O.  Scenes call methods and read state."""

    # ------------------------------------------------------------------ init
    def __init__(self, root: Path = BASE_DIR) -> None:
        self.root = root
        self.cards:       Dict[str, Card]   = self._load_cards(root / "cards.yaml")
        self.characters:  Dict[str, dict]   = self._load_yaml(root / "characters.yaml")
        self.enemy_defs:  Dict[str, Enemy]  = self._load_enemies(root / "enemies.yaml")
        self.status_defs: Dict[str, dict]   = self._load_yaml(root / "statuses.yaml")

        # Campaign state
        self.player:         Optional[Player]   = None
        self.enemies:        List[Enemy]         = []
        self.battle_no:      int                 = 0
        self.battle_total:   int                 = 6   # 5 normal + 1 boss
        self.campaign_over:  bool                = False
        self.victory:        bool                = False

        # Battle state machine
        self.state:               BattleState         = BattleState.IDLE
        self._turn_counter:       int                  = 0
        self.battle_log:          List[str]            = []
        self._pending_card_key:   Optional[str]        = None
        self._pending_card_idx:   int                  = -1
        self._pending_card_obj:   Optional[Card]       = None
        self._pending_energy_cost: int                 = 0
        self._pending_hp_cost:    int                  = 0
        self._pending_discard_n:  int                  = 0

        # Per-enemy flash timers for UI  {enemy_name: ticks_remaining}
        self.damage_flashes:      Dict[str, int]       = {}
        self.player_flash:        int                   = 0
        # Log of enemy actions from last enemy turn (for UI display)
        self.last_enemy_actions:  List[str]            = []

    # ------------------------------------------------------------------ yaml helpers
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

    def _normalize_pattern(self, raw_pattern: object) -> List[List[Action]]:
        pattern: List[List[Action]] = []
        if not isinstance(raw_pattern, list):
            return pattern
        if raw_pattern and isinstance(raw_pattern[0], dict):
            raw_pattern = [[x] for x in raw_pattern]
        for turn_actions in raw_pattern:
            if not isinstance(turn_actions, list):
                continue
            actions: List[Action] = []
            for item in turn_actions:
                if not isinstance(item, dict):
                    continue
                actions.append(Action(
                    type=str(item.get("type", "attack")).lower(),
                    damage=int(item.get("damage", 0)),
                    block=int(item.get("block", 0)),
                    heal=int(item.get("heal", 0)),
                    target=str(item.get("target", "player")),
                ))
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

    # ------------------------------------------------------------------ campaign API
    def character_list(self) -> List[Tuple[str, dict]]:
        """Return [(key, data), ...] for UI display."""
        return list(self.characters.items())

    def start_campaign(self, character_key: str) -> None:
        data = self.characters[character_key]
        deck_key = "inital_deck" if "inital_deck" in data else "initial_deck"
        deck = list(data.get(deck_key, []))
        hp = int(data.get("health", 80))
        self.player = Player(
            name=str(data.get("name", "Player")),
            max_hp=int(data.get("health_cap", hp)),
            hp=hp,
            deck=deck,
        )
        self.battle_no = 0
        self.campaign_over = False
        self.victory = False
        self._start_next_battle()

    def _start_next_battle(self) -> None:
        self.battle_no += 1
        is_boss = self.battle_no == self.battle_total
        self.enemies = self._build_battle(self.battle_no - 1, is_boss)
        self.battle_log.clear()
        self.last_enemy_actions.clear()
        self._turn_counter = 0
        self.state = BattleState.PLAYER_TURN_START

        assert self.player is not None
        self.player.draw_pile = self.player.deck[:]
        self.player.discard_pile.clear()
        self.player.hand.clear()
        random.shuffle(self.player.draw_pile)

    def _clone_enemy(self, source: Enemy, hp_scale: float = 1.0, dmg_scale: float = 1.0) -> Enemy:
        pattern: List[List[Action]] = []
        for turn in source.action_pattern:
            copied: List[Action] = []
            for a in turn:
                copied.append(Action(
                    type=a.type,
                    damage=max(0, int(round(a.damage * dmg_scale))),
                    block=max(0, int(round(a.block * dmg_scale))),
                    heal=a.heal,
                    target=a.target,
                ))
            pattern.append(copied)
        hp = max(1, int(round(source.max_hp * hp_scale)))
        return Enemy(name=source.name, max_hp=hp, hp=hp,
                     action_pattern=pattern, ability=source.ability)

    def _build_battle(self, battle_index: int, is_boss: bool) -> List[Enemy]:
        templates = list(self.enemy_defs.values())
        if not templates:
            raise RuntimeError("No enemies in enemies.yaml")
        if is_boss:
            template = max(templates, key=lambda e: e.max_hp)
            boss = self._clone_enemy(template, hp_scale=2.3, dmg_scale=1.5)
            boss.name = f"Boss {boss.name}"
            return [boss]
        count = random.choice([1, 2])
        picks = random.sample(templates, k=min(count, len(templates)))
        return [self._clone_enemy(p,
                    hp_scale=1.0 + battle_index * 0.08,
                    dmg_scale=1.0 + battle_index * 0.05)
                for p in picks]

    # ------------------------------------------------------------------ battle turn API
    def start_player_turn(self) -> None:
        """Process status effects, draw 5 cards, set energy. Call when state == PLAYER_TURN_START."""
        assert self.player is not None
        self.player.block = 0
        self._process_statuses(self.player, "player")
        if self.player.is_dead():
            self.state = BattleState.BATTLE_LOST
            return
        self.player.energy = 3
        self._draw_cards(self.player, 5)
        self.state = BattleState.PLAYER_ACTION

    def play_card(self, hand_idx: int) -> str:
        """
        Attempt to play the card at hand_idx.
        Returns a status string: 'ok', 'no_energy', 'need_target', 'need_discard', 'battle_over'.
        State is updated accordingly.
        """
        assert self.player is not None
        player = self.player
        if hand_idx < 0 or hand_idx >= len(player.hand):
            return "invalid"
        card_key = player.hand[hand_idx]
        card = self.cards[card_key]

        if player.energy < card.cost:
            return "no_energy"

        # Pay costs
        player.energy -= card.cost
        if card.hp_cost > 0:
            player.hp = max(0, player.hp - card.hp_cost)
            self._log(f"{player.name} paid {card.hp_cost} HP.")
        player.hand.pop(hand_idx)
        player.discard_pile.append(card_key)

        if player.is_dead():
            self._log("Died from card cost.")
            self.state = BattleState.BATTLE_LOST
            return "battle_over"

        # Resolve based on target type
        if card.target == "all_enemies":
            self._resolve_all_enemies(player, card)
            if self._check_battle_end():
                return "battle_over"
        elif card.target == "single_enemy":
            # Store pending card and ask scene to provide target
            self._pending_card_key = card_key
            self._pending_card_idx = hand_idx  # already removed, just for reference
            self._pending_energy_cost = card.cost
            self._pending_hp_cost = card.hp_cost
            self.state = BattleState.CHOOSING_TARGET
            self._pending_card_obj = card
            return "need_target"
        else:
            self._resolve_self(player, card)

        # Generic non-self block/heal
        self._apply_generic_non_self(player, card)

        # Draw / discard effects
        if card.draw > 0:
            self._draw_cards(player, card.draw)
            self._log(f"{player.name} draws {card.draw} card(s).")
        if card.discard > 0:
            self._pending_discard_n = card.discard
            self.state = BattleState.CHOOSING_DISCARD
            return "need_discard"
        if card.draw_until_non_attack:
            self._draw_until_non_attack(player)
        if card.copy_to_discard:
            player.discard_pile.append(card_key)
            self._log(f"{card.name} copied to discard pile.")

        return "ok"

    def cancel_pending_card(self) -> str:
        """Cancel a pending single-target card and restore the pre-selection state."""
        assert self.player is not None
        if self.state != BattleState.CHOOSING_TARGET:
            return "invalid"
        if not self._pending_card_key or self._pending_card_obj is None:
            return "invalid"

        player = self.player
        insert_at = max(0, min(self._pending_card_idx, len(player.hand)))
        player.hand.insert(insert_at, self._pending_card_key)

        if player.discard_pile and player.discard_pile[-1] == self._pending_card_key:
            player.discard_pile.pop()
        else:
            for i in range(len(player.discard_pile) - 1, -1, -1):
                if player.discard_pile[i] == self._pending_card_key:
                    player.discard_pile.pop(i)
                    break

        player.energy += self._pending_energy_cost
        if self._pending_hp_cost > 0:
            player.hp = min(player.max_hp, player.hp + self._pending_hp_cost)

        self._clear_pending_card()
        self.state = BattleState.PLAYER_ACTION
        return "ok"

    def choose_target(self, enemy_idx: int) -> str:
        """Complete a pending single-enemy card play. Returns 'ok' or 'battle_over'."""
        assert self.player is not None
        alive = [e for e in self.enemies if not e.is_dead()]
        if enemy_idx < 0 or enemy_idx >= len(alive):
            return "invalid"
        if self._pending_card_obj is None:
            return "invalid"
        target = alive[enemy_idx]
        card = self._pending_card_obj
        player = self.player

        dealt = self._deal_damage(player, target, card.damage)
        self._log(f"{card.name} deals {dealt} to {target.name}.")
        if target.is_dead():
            self.damage_flashes[target.name] = 15
        else:
            self.damage_flashes[target.name] = 12

        if card.vulnerable > 0 and not target.is_dead():
            self._apply_status(target, "vulnerable", card.vulnerable)
            self._log(f"{target.name} gains vulnerable x{card.vulnerable}.")
        if card.weak > 0 and not target.is_dead():
            self._apply_status(target, "weak", card.weak)
            self._log(f"{target.name} gains weak x{card.weak}.")

        self._apply_generic_non_self(player, card)

        if card.draw > 0:
            self._draw_cards(player, card.draw)
            self._log(f"{player.name} draws {card.draw} card(s).")
        if card.discard > 0:
            self._pending_discard_n = card.discard
            self.state = BattleState.CHOOSING_DISCARD
            return "need_discard"
        if card.draw_until_non_attack:
            self._draw_until_non_attack(player)
        if card.copy_to_discard:
            player.discard_pile.append(self._pending_card_key or "")
            self._log(f"{card.name} copied to discard pile.")

        self._clear_pending_card()
        if self._check_battle_end():
            return "battle_over"
        self.state = BattleState.PLAYER_ACTION
        return "ok"

    def choose_discard(self, hand_idx: int) -> str:
        """Discard one card from hand during a CHOOSING_DISCARD state."""
        assert self.player is not None
        player = self.player
        if hand_idx < 0 or hand_idx >= len(player.hand):
            return "invalid"
        discarded = player.hand.pop(hand_idx)
        player.discard_pile.append(discarded)
        self._log(f"Discarded {self.cards[discarded].name}.")
        self._pending_discard_n -= 1
        if self._pending_discard_n <= 0:
            # Finish any remaining post-card effects
            card = self._pending_card_obj
            if card:
                if card.draw_until_non_attack:
                    self._draw_until_non_attack(player)
                if card.copy_to_discard:
                    player.discard_pile.append(self._pending_card_key or "")
            self._clear_pending_card()
            if self._check_battle_end():
                return "battle_over"
            self.state = BattleState.PLAYER_ACTION
            return "ok"
        return "more"

    def _clear_pending_card(self) -> None:
        self._pending_card_key = None
        self._pending_card_idx = -1
        self._pending_card_obj = None
        self._pending_energy_cost = 0
        self._pending_hp_cost = 0

    def end_player_turn(self) -> None:
        """Discard hand and advance to enemy turn."""
        assert self.player is not None
        self.player.discard_pile.extend(self.player.hand)
        self.player.hand.clear()
        self.state = BattleState.ENEMY_TURN

    def run_enemy_turn(self) -> List[str]:
        """Execute all enemy actions. Returns log of events. Advances state."""
        assert self.player is not None
        player = self.player
        self.last_enemy_actions.clear()

        for enemy in self.enemies:
            if enemy.is_dead():
                continue
            enemy.block = 0
            self._process_statuses(enemy, "enemy")

        events: List[str] = []
        for enemy in self.enemies:
            if enemy.is_dead():
                continue
            if not enemy.action_pattern:
                continue
            turn_actions = enemy.action_pattern[self._turn_counter % len(enemy.action_pattern)]
            events.append(f"── {enemy.name} acts ──")
            for action in turn_actions:
                if enemy.is_dead():
                    break
                atype = action.type.lower()
                if atype == "attack":
                    dealt = self._deal_damage(enemy, player, action.damage)
                    msg = f"  {enemy.name} attacks for {dealt} dmg."
                    events.append(msg)
                    self._log(msg)
                    if dealt > 0:
                        self.player_flash = 15
                elif atype == "defend":
                    enemy.block += action.block
                    msg = f"  {enemy.name} gains {action.block} block."
                    events.append(msg)
                    self._log(msg)
                else:
                    msg = f"  {enemy.name}: {action.type}."
                    events.append(msg)
                    self._log(msg)

                if player.is_dead():
                    self.state = BattleState.BATTLE_LOST
                    self.last_enemy_actions = events
                    return events

        self._turn_counter += 1
        self.last_enemy_actions = events

        if all(e.is_dead() for e in self.enemies):
            self._handle_battle_won()
        else:
            self.state = BattleState.PLAYER_TURN_START
        return events

    # ------------------------------------------------------------------ card reward API
    def card_reward_choices(self, n: int = 3) -> List[Card]:
        all_keys = list(self.cards.keys())
        picks = random.sample(all_keys, k=min(n, len(all_keys)))
        return [self.cards[k] for k in picks]

    def accept_card_reward(self, card: Optional[Card]) -> None:
        """Add card to deck (or None to skip). Then advance to next battle or end campaign."""
        assert self.player is not None
        if card is not None:
            self.player.deck.append(card.key)
        # Post-battle recovery
        recovered = self._heal(self.player, max(1, int(self.player.max_hp * 0.1)))
        self._log(f"Recovered {recovered} HP.")
        if self.battle_no >= self.battle_total:
            self.campaign_over = True
            self.victory = True
        else:
            self._start_next_battle()

    def get_enemy_intent(self, enemy: Enemy) -> List[Action]:
        """Return the actions the enemy intends to do this turn."""
        if not enemy.action_pattern:
            return []
        return enemy.action_pattern[self._turn_counter % len(enemy.action_pattern)]

    # ------------------------------------------------------------------ internal helpers
    def _log(self, msg: str) -> None:
        self.battle_log.append(msg)
        if len(self.battle_log) > 10:
            self.battle_log.pop(0)

    def _draw_cards(self, player: Player, count: int) -> None:
        for _ in range(count):
            if not player.draw_pile and player.discard_pile:
                player.draw_pile = player.discard_pile[:]
                player.discard_pile.clear()
                random.shuffle(player.draw_pile)
            if not player.draw_pile:
                return
            player.hand.append(player.draw_pile.pop())

    def _draw_until_non_attack(self, player: Player) -> None:
        while True:
            before = len(player.hand)
            self._draw_cards(player, 1)
            if len(player.hand) == before:
                break
            drawn = self.cards[player.hand[-1]]
            self._log(f"Drew {drawn.name}.")
            if drawn.type.lower() != "attack":
                break

    @staticmethod
    def _apply_damage(target: Entity, amount: int) -> int:
        if amount <= 0:
            return 0
        absorbed = min(target.block, amount)
        target.block -= absorbed
        dealt = amount - absorbed
        target.hp = max(0, target.hp - dealt)
        return dealt

    def _damage_multiplier_deal(self, source: Entity) -> float:
        if source.statuses.get("weak", 0) > 0:
            return float(self.status_defs.get("weak", {}).get("ratio", 0.75))
        return 1.0

    def _damage_multiplier_receive(self, target: Entity) -> float:
        if target.statuses.get("vulnerable", 0) > 0:
            return float(self.status_defs.get("vulnerable", {}).get("ratio", 1.5))
        return 1.0

    def _deal_damage(self, source: Entity, target: Entity, base: int) -> int:
        dmg = int(round(base * self._damage_multiplier_deal(source)))
        dmg = int(round(dmg * self._damage_multiplier_receive(target)))
        return self._apply_damage(target, dmg)

    @staticmethod
    def _heal(target: Entity, amount: int) -> int:
        if amount <= 0:
            return 0
        old = target.hp
        target.hp = min(target.max_hp, target.hp + amount)
        return target.hp - old

    def _apply_status(self, target: Entity, status: str, turns: int) -> None:
        if turns <= 0:
            return
        target.statuses[status] = target.statuses.get(status, 0) + turns

    def _process_statuses(self, target: Entity, turn_owner: str) -> None:
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
                    dealt = self._apply_damage(target, int(definition["damage"]))
                    if dealt > 0:
                        self._log(f"{target.name} suffers {dealt} from {status}.")
                if "heal" in definition:
                    healed = self._heal(target, int(definition["heal"]))
                    if healed > 0:
                        self._log(f"{target.name} heals {healed} from {status}.")
                target.statuses[status] -= 1
            if target.statuses.get(status, 0) <= 0:
                target.statuses.pop(status, None)

    def _resolve_all_enemies(self, player: Player, card: Card) -> None:
        for enemy in self.enemies:
            if enemy.is_dead():
                continue
            dealt = self._deal_damage(player, enemy, card.damage)
            self._log(f"{card.name} deals {dealt} to {enemy.name}.")
            self.damage_flashes[enemy.name] = 12
            if card.vulnerable > 0 and not enemy.is_dead():
                self._apply_status(enemy, "vulnerable", card.vulnerable)
            if card.weak > 0 and not enemy.is_dead():
                self._apply_status(enemy, "weak", card.weak)

    def _resolve_self(self, player: Player, card: Card) -> None:
        if card.damage > 0:
            dealt = self._deal_damage(player, player, card.damage)
            self._log(f"{card.name} deals {dealt} to {player.name}.")
        if card.block > 0:
            player.block += card.block
            self._log(f"{player.name} gains {card.block} block.")
        if card.heal > 0:
            healed = self._heal(player, card.heal)
            self._log(f"{player.name} heals {healed} HP.")
        if card.vulnerable > 0:
            self._apply_status(player, "vulnerable", card.vulnerable)
        if card.weak > 0:
            self._apply_status(player, "weak", card.weak)

    def _apply_generic_non_self(self, player: Player, card: Card) -> None:
        if card.block > 0 and card.target != "self":
            player.block += card.block
            self._log(f"{player.name} gains {card.block} block.")
        if card.heal > 0 and card.target != "self":
            healed = self._heal(player, card.heal)
            self._log(f"{player.name} heals {healed} HP.")

    def _check_battle_end(self) -> bool:
        assert self.player is not None
        if self.player.is_dead():
            self.state = BattleState.BATTLE_LOST
            return True
        if all(e.is_dead() for e in self.enemies):
            self._handle_battle_won()
            return True
        return False

    def _handle_battle_won(self) -> None:
        self.state = BattleState.BATTLE_WON
