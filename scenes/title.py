from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from scenes.base_scene import BaseScene
from ui import palette as pal
from ui.widgets.button import Button

if TYPE_CHECKING:
    from ui.scene_manager import SceneManager


class TitleScene(BaseScene):
    """Animated title / main-menu screen."""

    def __init__(self, manager: "SceneManager") -> None:
        super().__init__(manager)
        W, H = manager.screen.get_size()
        self._time = 0.0

        # Starfield
        import random
        self._stars = [
            (random.randint(0, W), random.randint(0, H), random.random())
            for _ in range(120)
        ]

        btn_w, btn_h = 220, 48
        self._btn_start = Button(
            rect=pygame.Rect((W - btn_w) // 2, H // 2 + 60, btn_w, btn_h),
            label="START GAME",
            font=manager.font_medium,
            color=pal.BTN_SUCCESS,
            hover_color=(50, 120, 80),
            on_click=self._go_to_char_select,
        )
        self._btn_quit = Button(
            rect=pygame.Rect((W - btn_w) // 2, H // 2 + 120, btn_w, btn_h),
            label="QUIT",
            font=manager.font_medium,
            color=pal.BTN_DANGER,
            hover_color=(130, 50, 50),
            on_click=lambda: setattr(manager, "running", False),
        )

    def _go_to_char_select(self) -> None:
        from scenes.character_select import CharacterSelectScene
        self.manager.switch_to(CharacterSelectScene(self.manager))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._go_to_char_select()
        self._btn_start.handle_event(event)
        self._btn_quit.handle_event(event)

    def update(self, dt: float) -> None:
        self._time += dt

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(pal.BG_DARK)
        W, H = surface.get_size()

        # Twinkling stars
        for x, y, phase in self._stars:
            brightness = int(80 + 60 * math.sin(self._time * 2.0 + phase * 6.28))
            color = (brightness, brightness, brightness + 20)
            surface.set_at((x, y), color)

        # Scanlines overlay (every other row slightly darker)
        scan = pygame.Surface((W, H), pygame.SRCALPHA)
        for row in range(0, H, 2):
            pygame.draw.line(scan, (0, 0, 0, 30), (0, row), (W, row))
        surface.blit(scan, (0, 0))

        # Title
        bob = int(6 * math.sin(self._time * 1.5))
        title1 = self.manager.font_large.render("DUNGEON CARDS", True, pal.TEXT_TITLE)
        title2 = self.manager.font_medium.render("A Slay the Spire-Like", True, pal.TEXT_DIM)
        surface.blit(title1, title1.get_rect(center=(W // 2, H // 2 - 60 + bob)))
        surface.blit(title2, title2.get_rect(center=(W // 2, H // 2 - 20 + bob)))

        self._btn_start.draw(surface)
        self._btn_quit.draw(surface)

        hint = self.manager.font_tiny.render("Press ENTER or click START GAME", True, pal.TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(W // 2, H - 30)))
