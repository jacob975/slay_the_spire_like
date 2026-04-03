from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import pygame

from core.models import Card
from scenes.base_scene import BaseScene
from ui import palette as pal
from ui.widgets.button import Button
from ui.widgets.card_widget import CardWidget, CARD_W, CARD_H

if TYPE_CHECKING:
    from ui.scene_manager import SceneManager


class CardRewardScene(BaseScene):
    """Post-battle card reward selection screen."""

    def __init__(self, manager: "SceneManager") -> None:
        super().__init__(manager)
        W, H = manager.screen.get_size()
        self.W, self.H = W, H

        self._choices: List[Card] = manager.engine.card_reward_choices(3)
        self._selected: Optional[int] = None
        self._card_widgets: List[CardWidget] = []
        self._build_widgets()

        btn_w, btn_h = 180, 44
        self._btn_confirm = Button(
            rect=pygame.Rect((W - btn_w) // 2, H - 80, btn_w, btn_h),
            label="CONFIRM",
            font=manager.font_medium,
            color=pal.BTN_SUCCESS,
            hover_color=(50, 120, 80),
            on_click=self._confirm,
        )
        self._btn_skip = Button(
            rect=pygame.Rect((W - btn_w) // 2 + btn_w + 20, H - 80, 120, btn_h),
            label="SKIP",
            font=manager.font_medium,
            color=pal.BTN_NORMAL,
            hover_color=pal.BTN_HOVER,
            on_click=self._skip,
        )

    def _build_widgets(self) -> None:
        W, H = self.W, self.H
        n = len(self._choices)
        total_w = n * CARD_W + (n - 1) * 30
        start_x = (W - total_w) // 2
        cy = H // 2 - CARD_H // 2
        self._card_widgets = []
        for i, card in enumerate(self._choices):
            x = start_x + i * (CARD_W + 30)
            self._card_widgets.append(CardWidget(
                card=card,
                pos=(x, cy),
                font_name=self.manager.font_small,
                font_small=self.manager.font_tiny,
                selected=(i == self._selected),
            ))

    def _confirm(self) -> None:
        chosen = self._choices[self._selected] if self._selected is not None else None
        self.manager.engine.accept_card_reward(chosen)
        self._transition()

    def _skip(self) -> None:
        self.manager.engine.accept_card_reward(None)
        self._transition()

    def _transition(self) -> None:
        engine = self.manager.engine
        if engine.campaign_over:
            from scenes.game_over import GameOverScene
            self.manager.switch_to(GameOverScene(self.manager, victory=engine.victory))
        else:
            from scenes.battle import BattleScene
            self.manager.switch_to(BattleScene(self.manager))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT and self._selected is not None:
                self._selected = max(0, self._selected - 1)
                self._build_widgets()
            elif event.key == pygame.K_RIGHT:
                n = len(self._choices)
                if self._selected is None:
                    self._selected = 0
                else:
                    self._selected = min(n - 1, self._selected + 1)
                self._build_widgets()
            elif event.key == pygame.K_RETURN and self._selected is not None:
                self._confirm()
            elif event.key == pygame.K_s:
                self._skip()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, cw in enumerate(self._card_widgets):
                if cw.rect.collidepoint(event.pos):
                    if self._selected == i:
                        self._confirm()
                    else:
                        self._selected = i
                        self._build_widgets()
                    return

        self._btn_confirm.handle_event(event)
        self._btn_skip.handle_event(event)
        self._btn_confirm.enabled = self._selected is not None

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(pal.BG_DARK)
        W, H = self.W, self.H
        engine = self.manager.engine

        title = self.manager.font_large.render("CHOOSE A CARD REWARD", True, pal.TEXT_TITLE)
        surface.blit(title, title.get_rect(center=(W // 2, 40)))

        if engine.player:
            sub = self.manager.font_small.render(
                f"Battle {engine.battle_no} complete!  HP: {engine.player.hp}/{engine.player.max_hp}",
                True, pal.TEXT_DIM,
            )
            surface.blit(sub, sub.get_rect(center=(W // 2, 72)))

        for cw in self._card_widgets:
            cw.draw(surface)

        self._btn_confirm.draw(surface)
        self._btn_skip.draw(surface)

        hint = self.manager.font_tiny.render(
            "Click to select  ·  Click again or ENTER to confirm  ·  [S] to skip",
            True, pal.TEXT_DIM,
        )
        surface.blit(hint, hint.get_rect(center=(W // 2, H - 20)))
