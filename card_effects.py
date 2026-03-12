from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from poc import Card, Enemy, Player


@dataclass
class CardPlayContext:
    game: object
    player: "Player"
    enemies: List["Enemy"]
    card: "Card"
    card_key: str


def _alive_enemies(enemies: List["Enemy"]) -> List["Enemy"]:
    return [enemy for enemy in enemies if not enemy.is_dead()]


def _choose_target(ctx: CardPlayContext) -> Optional["Enemy"]:
    game = ctx.game
    alive = _alive_enemies(ctx.enemies)
    if not alive:
        return None
    return game.choose_target(ctx.enemies)


def _apply_to_all_enemies(ctx: CardPlayContext) -> None:
    game = ctx.game
    card = ctx.card
    for enemy in ctx.enemies:
        if enemy.is_dead():
            continue
        dealt = game.deal_damage(ctx.player, enemy, card.damage)
        game._log(f"{card.name} deals {dealt} to {enemy.name}.")
        print(f"{card.name} deals {dealt} to {enemy.name}.")
        if card.vulnerable > 0 and not enemy.is_dead():
            game.apply_status(enemy, "vulnerable", card.vulnerable)
            game._log(f"{enemy.name} gains vulnerable x{card.vulnerable}.")
            print(f"{enemy.name} gains vulnerable x{card.vulnerable}.")
        if card.weak > 0 and not enemy.is_dead():
            game.apply_status(enemy, "weak", card.weak)
            game._log(f"{enemy.name} gains weak x{card.weak}.")
            print(f"{enemy.name} gains weak x{card.weak}.")


def _apply_to_single_enemy(ctx: CardPlayContext) -> bool:
    game = ctx.game
    card = ctx.card
    target = _choose_target(ctx)
    if target is None:
        return False

    dealt = game.deal_damage(ctx.player, target, card.damage)
    game._log(f"{card.name} deals {dealt} to {target.name}.")
    print(f"{card.name} deals {dealt} to {target.name}.")
    if card.vulnerable > 0 and not target.is_dead():
        game._log(f"{target.name} gains vulnerable x{card.vulnerable}.")
        print(f"{target.name} gains vulnerable x{card.vulnerable}.")
    if card.weak > 0 and not target.is_dead():
        game.apply_status(target, "weak", card.weak)
        print(f"{target.name} gains weak x{card.weak}.")
    return True


def _apply_to_self(ctx: CardPlayContext) -> None:
    game = ctx.game
    card = ctx.card
    player = ctx.player

    if card.damage > 0:
        dealt = game.deal_damage(player, player, card.damage)
        game._log(f"{card.name} deals {dealt} to {player.name}.")
        print(f"{card.name} deals {dealt} to {player.name}.")

    if card.block > 0:
        player.block += card.block
        game._log(f"{player.name} gains {card.block} block.")
        print(f"{player.name} gains {card.block} block.")

    if card.heal > 0:
        healed = game.heal(player, card.heal)
        game._log(f"{player.name} heals {healed} HP.")
        print(f"{player.name} heals {healed} HP.")

    if card.vulnerable > 0:
        game.apply_status(player, "vulnerable", card.vulnerable)
        game._log(f"{player.name} gains vulnerable x{card.vulnerable}.")
        print(f"{player.name} gains vulnerable x{card.vulnerable}.")

    if card.weak > 0:
        game.apply_status(player, "weak", card.weak)
        game._log(f"{player.name} gains weak x{card.weak}.")
        print(f"{player.name} gains weak x{card.weak}.")


def _apply_generic_non_self_effects(ctx: CardPlayContext) -> None:
    game = ctx.game
    card = ctx.card
    player = ctx.player

    if card.block > 0 and card.target != "self":
        player.block += card.block
        game._log(f"{player.name} gains {card.block} block.")
        print(f"{player.name} gains {card.block} block.")

    if card.heal > 0 and card.target != "self":
        healed = game.heal(player, card.heal)
        game._log(f"{player.name} heals {healed} HP.")
        print(f"{player.name} heals {healed} HP.")


def _effect_draw(ctx: CardPlayContext, amount: int) -> None:
    if amount <= 0:
        return
    ctx.game.draw_cards(ctx.player, amount)
    ctx.game._log(f"{ctx.player.name} draws {amount} card(s).")
    print(f"{ctx.player.name} draws {amount} card(s).")


def _effect_discard(ctx: CardPlayContext, amount: int) -> None:
    if amount <= 0:
        return
    ctx.game.choose_discard(ctx.player, amount)
    ctx.game._log(f"{ctx.player.name} discards {amount} card(s).")


def _effect_draw_until_non_attack(ctx: CardPlayContext, enabled: bool) -> None:
    if enabled:
        ctx.game.draw_cards_until_non_attack(ctx.player)
        ctx.game._log(f"{ctx.player.name} draws until a non-attack card.")


def _effect_copy_to_discard(ctx: CardPlayContext, enabled: bool) -> None:
    if enabled:
        ctx.player.discard_pile.append(ctx.card_key)
        ctx.game._log(f"{ctx.card.name} copied to discard pile.")
        print(f"{ctx.card.name} copied to discard pile.")


def resolve_card_effects(ctx: CardPlayContext) -> bool:
    """Resolve one card's effects. Returns False if battle should end immediately."""
    card = ctx.card

    if card.target == "all_enemies":
        _apply_to_all_enemies(ctx)
    elif card.target == "single_enemy":
        if not _apply_to_single_enemy(ctx):
            return False
    else:
        _apply_to_self(ctx)

    _apply_generic_non_self_effects(ctx)
    _effect_draw(ctx, card.draw)
    _effect_discard(ctx, card.discard)
    _effect_draw_until_non_attack(ctx, card.draw_until_non_attack)
    _effect_copy_to_discard(ctx, card.copy_to_discard)

    return True
