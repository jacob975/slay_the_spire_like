from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import pygame

from core.engine import BattleState
from core.models import Enemy
from scenes.base_scene import BaseScene
from ui import palette as pal
from ui.widgets.button import Button
from ui.widgets.card_widget import CardWidget, CARD_W, CARD_H
from ui.widgets.hp_bar import (
    draw_hp_bar, draw_block_pip, draw_energy_pips, draw_status_tags,
)

if TYPE_CHECKING:
    from ui.scene_manager import SceneManager

LOG_MAX = 8
ANIM_ENEMY_TURN_DELAY = 1.2   # seconds to pause and show enemy actions


class BattleScene(BaseScene):
    """Main battle gameplay scene."""

    def __init__(self, manager: "SceneManager") -> None:
        super().__init__(manager)
        W, H = manager.screen.get_size()
        self.W, self.H = W, H

        self._card_widgets: List[CardWidget] = []
        self._selected_card_idx: Optional[int] = None
        self._enemy_turn_timer: float = 0.0
        self._message: str = ""
        self._message_timer: float = 0.0

        # End Turn button
        self._btn_end_turn = Button(
            rect=pygame.Rect(W - 160, H - 80, 140, 44),
            label="END TURN",
            font=manager.font_medium,
            color=pal.BTN_NORMAL,
            hover_color=pal.BTN_HOVER,
            on_click=self._on_end_turn,
        )

        self._rebuild_hand()
        self._trigger_player_turn_start_if_needed()

    # ------------------------------------------------------------------ state helpers
    def _trigger_player_turn_start_if_needed(self) -> None:
        if self.manager.engine.state == BattleState.PLAYER_TURN_START:
            self.manager.engine.start_player_turn()
            self._rebuild_hand()

    def _rebuild_hand(self) -> None:
        engine = self.manager.engine
        player = engine.player
        if not player:
            return
        W, H = self.W, self.H
        hand = player.hand
        n = len(hand)
        total_w = n * CARD_W + max(0, n - 1) * 8
        start_x = (W - total_w) // 2
        self._card_widgets = []
        for i, card_key in enumerate(hand):
            card = engine.cards[card_key]
            x = start_x + i * (CARD_W + 8)
            y = H - CARD_H - 10
            dimmed = (
                player.energy < card.cost or
                (engine.state == BattleState.CHOOSING_TARGET and i != self._selected_card_idx) or
                engine.state == BattleState.CHOOSING_DISCARD
            )
            self._card_widgets.append(CardWidget(
                card=card,
                pos=(x, y),
                font_name=self.manager.font_small,
                font_small=self.manager.font_tiny,
                selected=(i == self._selected_card_idx),
                dimmed=dimmed,
            ))

    def _flash_message(self, msg: str, duration: float = 1.5) -> None:
        self._message = msg
        self._message_timer = duration

    # ------------------------------------------------------------------ event handling
    def handle_event(self, event: pygame.event.Event) -> None:
        engine = self.manager.engine

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and engine.state == BattleState.CHOOSING_TARGET:
                self._selected_card_idx = None
                engine.state = BattleState.PLAYER_ACTION
                self._rebuild_hand()
            if event.key == pygame.K_e and engine.state == BattleState.PLAYER_ACTION:
                self._on_end_turn()

        if engine.state in (BattleState.PLAYER_ACTION, BattleState.CHOOSING_DISCARD):
            self._btn_end_turn.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_click(event.pos)

    def _on_click(self, pos) -> None:
        engine = self.manager.engine
        state = engine.state

        # Clicking on a card in hand
        if state == BattleState.PLAYER_ACTION:
            for i, cw in enumerate(self._card_widgets):
                if cw.rect.collidepoint(pos[0], pos[1] + (8 if cw.selected else 0)):
                    self._try_play_card(i)
                    return
            # Clicking nowhere clears selection (noop — we don't have selection in this flow)

        elif state == BattleState.CHOOSING_TARGET:
            # Click on an enemy
            alive = [e for e in engine.enemies if not e.is_dead()]
            for i, (enemy, rect) in enumerate(self._enemy_rects(alive)):
                if rect.collidepoint(pos):
                    result = engine.choose_target(i)
                    self._selected_card_idx = None
                    self._handle_result(result)
                    return

        elif state == BattleState.CHOOSING_DISCARD:
            for i, cw in enumerate(self._card_widgets):
                if cw.rect.collidepoint(pos):
                    result = engine.choose_discard(i)
                    self._handle_result(result)
                    return

    def _try_play_card(self, hand_idx: int) -> None:
        engine = self.manager.engine
        result = engine.play_card(hand_idx)
        if result == "no_energy":
            self._flash_message("Not enough energy!", 1.0)
        elif result == "need_target":
            self._selected_card_idx = hand_idx
            self._flash_message("Choose a target →", 2.0)
        else:
            self._selected_card_idx = None
            self._handle_result(result)

    def _handle_result(self, result: str) -> None:
        engine = self.manager.engine
        if result == "battle_over":
            self._check_battle_end()
        elif result in ("ok", "need_discard", "more"):
            self._rebuild_hand()
        self._rebuild_hand()

    def _check_battle_end(self) -> None:
        engine = self.manager.engine
        if engine.state == BattleState.BATTLE_LOST:
            from scenes.game_over import GameOverScene
            self.manager.switch_to(GameOverScene(self.manager, victory=False))
        elif engine.state == BattleState.BATTLE_WON:
            from scenes.card_reward import CardRewardScene
            self.manager.switch_to(CardRewardScene(self.manager))

    def _on_end_turn(self) -> None:
        engine = self.manager.engine
        if engine.state != BattleState.PLAYER_ACTION:
            return
        engine.end_player_turn()
        self._rebuild_hand()
        self._enemy_turn_timer = ANIM_ENEMY_TURN_DELAY
        engine.run_enemy_turn()  # run immediately; timer controls display pause

    # ------------------------------------------------------------------ update
    def update(self, dt: float) -> None:
        engine = self.manager.engine

        if self._message_timer > 0:
            self._message_timer -= dt

        # Decrement flash timers
        for k in list(engine.damage_flashes.keys()):
            engine.damage_flashes[k] -= 1
            if engine.damage_flashes[k] <= 0:
                del engine.damage_flashes[k]
        if engine.player_flash > 0:
            engine.player_flash -= 1

        # Enemy turn display pause
        if engine.state == BattleState.PLAYER_TURN_START and self._enemy_turn_timer > 0:
            self._enemy_turn_timer -= dt
            if self._enemy_turn_timer <= 0:
                engine.start_player_turn()
                self._rebuild_hand()
        elif engine.state == BattleState.PLAYER_TURN_START and self._enemy_turn_timer <= 0:
            engine.start_player_turn()
            self._rebuild_hand()

        # Check for battle end after state changes
        if engine.state in (BattleState.BATTLE_LOST, BattleState.BATTLE_WON):
            self._check_battle_end()

    # ------------------------------------------------------------------ draw
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(pal.BG_DARK)
        engine = self.manager.engine
        player = engine.player
        if not player:
            return

        W, H = self.W, self.H

        self._draw_header(surface, W)
        self._draw_enemies(surface, W)
        self._draw_player_area(surface, W, H, player)
        self._draw_hand(surface)
        self._draw_log(surface, W, H)
        self._draw_state_overlay(surface, W, H)

    def _draw_header(self, surface: pygame.Surface, W: int) -> None:
        engine = self.manager.engine
        label = f"  BATTLE {engine.battle_no} / {engine.battle_total}"
        if engine.battle_no == engine.battle_total:
            label += "  [ BOSS ]"
        surf = self.manager.font_medium.render(label, True, pal.TEXT_TITLE)
        pygame.draw.rect(surface, pal.BG_PANEL, pygame.Rect(0, 0, W, 36))
        pygame.draw.line(surface, pal.BORDER, (0, 36), (W, 36))
        surface.blit(surf, (10, 8))

    def _draw_enemies(self, surface: pygame.Surface, W: int) -> None:
        engine = self.manager.engine
        alive = [e for e in engine.enemies if not e.is_dead()]
        dead  = [e for e in engine.enemies if e.is_dead()]
        all_e = alive + dead

        n = len(all_e)
        slot_w = min(200, (W - 40) // max(n, 1))
        total_w = n * slot_w
        start_x = (W - total_w) // 2

        for i, enemy in enumerate(all_e):
            x = start_x + i * slot_w
            y = 50
            self._draw_enemy_card(surface, enemy, x, y, slot_w - 10)

    def _enemy_rects(self, alive_enemies: List[Enemy]) -> List[tuple]:
        W = self.W
        n = len(alive_enemies)
        slot_w = min(200, (W - 40) // max(n, 1))
        total_w = n * slot_w
        start_x = (W - total_w) // 2
        result = []
        for i, enemy in enumerate(alive_enemies):
            x = start_x + i * slot_w
            rect = pygame.Rect(x, 50, slot_w - 10, 190)
            result.append((enemy, rect))
        return result

    def _draw_enemy_card(
        self, surface: pygame.Surface, enemy: Enemy, x: int, y: int, w: int
    ) -> None:
        engine = self.manager.engine
        h = 190
        rect = pygame.Rect(x, y, w, h)
        is_dead = enemy.is_dead()
        flashing = engine.damage_flashes.get(enemy.name, 0) > 0

        # Highlight on CHOOSING_TARGET for alive enemies
        alive_enemies = [e for e in engine.enemies if not e.is_dead()]
        is_target = engine.state == BattleState.CHOOSING_TARGET and not is_dead

        bg = pal.BG_PANEL_ALT if is_target else pal.BG_PANEL
        if is_dead:
            bg = (20, 20, 20)
        if flashing:
            bg = pal.DAMAGE_FLASH

        pygame.draw.rect(surface, bg, rect, border_radius=4)
        border = pal.BORDER_SELECT if is_target else pal.BORDER
        pygame.draw.rect(surface, border, rect, 2, border_radius=4)

        cy = y + 8
        # Name
        name_color = pal.TEXT_DIM if is_dead else pal.TEXT_PRIMARY
        name_surf = self.manager.font_small.render(enemy.name, True, name_color)
        surface.blit(name_surf, (x + 6, cy))
        cy += 18

        if is_dead:
            dead_surf = self.manager.font_medium.render("DEAD", True, pal.HP_LOW)
            surface.blit(dead_surf, dead_surf.get_rect(center=rect.center))
            return

        # Sprite placeholder
        spr_rect = pygame.Rect(x + w // 2 - 24, cy, 48, 56)
        pygame.draw.rect(surface, (40, 25, 25), spr_rect, border_radius=4)
        icon = self.manager.font_large.render(enemy.name[0].upper(), True, (180, 80, 80))
        surface.blit(icon, icon.get_rect(center=spr_rect.center))
        cy += 62

        # HP bar
        hp_rect = pygame.Rect(x + 4, cy, w - 8, 14)
        draw_hp_bar(surface, hp_rect, enemy.hp, enemy.max_hp,
                    show_text=True, font=self.manager.font_tiny)
        cy += 18

        # Block
        if enemy.block > 0:
            draw_block_pip(surface, x + 4, cy, enemy.block, self.manager.font_tiny)
            cy += 20

        # Statuses
        if enemy.statuses:
            draw_status_tags(surface, x + 4, cy, enemy.statuses, self.manager.font_tiny)
            cy += 16

        # Intent
        intent = engine.get_enemy_intent(enemy)
        if intent:
            parts = []
            for a in intent:
                if a.type == "attack":
                    parts.append(f"ATK {a.damage}")
                elif a.type == "defend":
                    parts.append(f"DEF +{a.block}")
                else:
                    parts.append(a.type.upper())
            intent_text = " | ".join(parts)
            intent_surf = self.manager.font_tiny.render(f"→ {intent_text}", True, pal.TEXT_DIM)
            surface.blit(intent_surf, (x + 4, rect.bottom - 16))

    def _draw_player_area(self, surface: pygame.Surface, W: int, H: int, player) -> None:
        engine = self.manager.engine
        panel_h = 80
        panel_rect = pygame.Rect(0, H - CARD_H - panel_h - 20, 280, panel_h)
        pygame.draw.rect(surface, pal.BG_PANEL, panel_rect, border_radius=4)
        pygame.draw.rect(surface, pal.BORDER, panel_rect, 1, border_radius=4)

        flashing = engine.player_flash > 0
        name_color = pal.DAMAGE_FLASH if flashing else pal.TEXT_TITLE
        name_surf = self.manager.font_medium.render(player.name, True, name_color)
        surface.blit(name_surf, (10, panel_rect.y + 8))

        hp_rect = pygame.Rect(10, panel_rect.y + 32, 180, 14)
        draw_hp_bar(surface, hp_rect, player.hp, player.max_hp,
                    show_text=True, font=self.manager.font_tiny)

        if player.block > 0:
            draw_block_pip(surface, 200, panel_rect.y + 30, player.block, self.manager.font_tiny)

        draw_energy_pips(surface, 10, panel_rect.y + 52, player.energy)

        if player.statuses:
            draw_status_tags(surface, 80, panel_rect.y + 52, player.statuses, self.manager.font_tiny)

        # Deck / discard counts
        deck_info = (
            f"Draw:{len(player.draw_pile)}  "
            f"Disc:{len(player.discard_pile)}  "
            f"Deck:{len(player.deck)}"
        )
        info_surf = self.manager.font_tiny.render(deck_info, True, pal.TEXT_DIM)
        surface.blit(info_surf, (10, H - CARD_H - 18))

        # End turn button (only in PLAYER_ACTION state)
        if engine.state == BattleState.PLAYER_ACTION:
            self._btn_end_turn.enabled = True
        else:
            self._btn_end_turn.enabled = False
        self._btn_end_turn.draw(surface)

    def _draw_hand(self, surface: pygame.Surface) -> None:
        for cw in self._card_widgets:
            cw.draw(surface)

    def _draw_log(self, surface: pygame.Surface, W: int, H: int) -> None:
        engine = self.manager.engine
        log_w = 280
        log_rect = pygame.Rect(W - log_w - 10, 50, log_w, H - CARD_H - 100)
        pygame.draw.rect(surface, pal.BG_PANEL, log_rect, border_radius=4)
        pygame.draw.rect(surface, pal.BORDER, log_rect, 1, border_radius=4)

        header = self.manager.font_tiny.render("BATTLE LOG", True, pal.TEXT_DIM)
        surface.blit(header, (log_rect.x + 6, log_rect.y + 4))
        pygame.draw.line(surface, pal.BORDER,
                         (log_rect.x, log_rect.y + 18), (log_rect.right, log_rect.y + 18))

        msgs = engine.battle_log[-LOG_MAX:]
        for i, msg in enumerate(msgs):
            y = log_rect.y + 22 + i * 14
            if y + 14 > log_rect.bottom:
                break
            surf = self.manager.font_tiny.render(msg[:36], True, pal.TEXT_PRIMARY)
            surface.blit(surf, (log_rect.x + 4, y))

    def _draw_state_overlay(self, surface: pygame.Surface, W: int, H: int) -> None:
        engine = self.manager.engine
        state = engine.state

        # State label at top center
        labels = {
            BattleState.PLAYER_ACTION:   ("YOUR TURN",      pal.TEXT_TITLE),
            BattleState.CHOOSING_TARGET: ("CHOOSE TARGET",  pal.ENERGY_FULL),
            BattleState.CHOOSING_DISCARD:("CHOOSE DISCARD", pal.STATUS_VULNERABLE),
            BattleState.ENEMY_TURN:      ("ENEMY TURN",     pal.HP_LOW),
            BattleState.PLAYER_TURN_START:("...",           pal.TEXT_DIM),
        }
        if state in labels:
            text, color = labels[state]
            surf = self.manager.font_medium.render(text, True, color)
            surface.blit(surf, surf.get_rect(centerx=W // 2, top=42))

        # Temp message
        if self._message_timer > 0:
            alpha = min(255, int(self._message_timer / 1.5 * 255))
            msg_surf = self.manager.font_small.render(self._message, True, pal.TEXT_TITLE)
            msg_surf.set_alpha(alpha)
            surface.blit(msg_surf, msg_surf.get_rect(center=(W // 2, H // 2)))

        # ESC hint in CHOOSING_TARGET
        if state == BattleState.CHOOSING_TARGET:
            hint = self.manager.font_tiny.render("ESC to cancel", True, pal.TEXT_DIM)
            surface.blit(hint, hint.get_rect(centerx=W // 2, top=H - CARD_H - 40))

        # E key hint
        if state == BattleState.PLAYER_ACTION:
            hint = self.manager.font_tiny.render("[E] End Turn", True, pal.TEXT_DIM)
            surface.blit(hint, (self.W - 160, self.H - 95))
