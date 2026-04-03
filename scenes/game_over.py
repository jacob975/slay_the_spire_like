from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from scenes.base_scene import BaseScene
from ui import palette as pal
from ui.widgets.button import Button

if TYPE_CHECKING:
    from ui.scene_manager import SceneManager


class GameOverScene(BaseScene):
    """Victory or defeat screen."""

    def __init__(self, manager: "SceneManager", victory: bool) -> None:
        super().__init__(manager)
        self.victory = victory
        W, H = manager.screen.get_size()
        btn_w, btn_h = 220, 48

        self._btn_menu = Button(
            rect=pygame.Rect((W - btn_w) // 2, H // 2 + 100, btn_w, btn_h),
            label="MAIN MENU",
            font=manager.font_medium,
            color=pal.BTN_NORMAL,
            hover_color=pal.BTN_HOVER,
            on_click=self._to_menu,
        )

    def _to_menu(self) -> None:
        from scenes.title import TitleScene
        self.manager.switch_to(TitleScene(self.manager))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self._to_menu()
        self._btn_menu.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(pal.BG_DARK)
        W, H = surface.get_size()
        engine = self.manager.engine
        player = engine.player

        if self.victory:
            title_text = "VICTORY!"
            title_color = pal.TEXT_TITLE
            sub_text = "You defeated the final boss!"
        else:
            title_text = "DEFEATED"
            title_color = pal.HP_LOW
            sub_text = "You have fallen in the dungeon."

        title_surf = self.manager.font_large.render(title_text, True, title_color)
        surface.blit(title_surf, title_surf.get_rect(center=(W // 2, H // 2 - 80)))

        sub_surf = self.manager.font_medium.render(sub_text, True, pal.TEXT_PRIMARY)
        surface.blit(sub_surf, sub_surf.get_rect(center=(W // 2, H // 2 - 30)))

        if player:
            stats = [
                f"Final HP:  {player.hp} / {player.max_hp}",
                f"Deck size: {len(player.deck)} cards",
                f"Battles:   {engine.battle_no} / {engine.battle_total}",
            ]
            for i, line in enumerate(stats):
                surf = self.manager.font_small.render(line, True, pal.TEXT_DIM)
                surface.blit(surf, surf.get_rect(center=(W // 2, H // 2 + 20 + i * 22)))

        self._btn_menu.draw(surface)
