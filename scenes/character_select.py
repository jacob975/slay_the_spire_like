from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import pygame

from scenes.base_scene import BaseScene
from ui import palette as pal
from ui.widgets.button import Button

if TYPE_CHECKING:
    from ui.scene_manager import SceneManager


class CharacterSelectScene(BaseScene):
    """Character selection screen."""

    CARD_W = 240
    CARD_H = 340

    def __init__(self, manager: "SceneManager") -> None:
        super().__init__(manager)
        W, H = manager.screen.get_size()
        self._characters: List[Tuple[str, dict]] = manager.engine.character_list()
        self._selected: int = 0

        # Position character cards
        n = len(self._characters)
        total_w = n * self.CARD_W + (n - 1) * 30
        start_x = (W - total_w) // 2
        self._card_rects: List[pygame.Rect] = [
            pygame.Rect(start_x + i * (self.CARD_W + 30), H // 2 - self.CARD_H // 2 - 20, self.CARD_W, self.CARD_H)
            for i in range(n)
        ]

        btn_w, btn_h = 200, 48
        self._btn_confirm = Button(
            rect=pygame.Rect((W - btn_w) // 2, H - 80, btn_w, btn_h),
            label="CONFIRM",
            font=manager.font_medium,
            color=pal.BTN_SUCCESS,
            hover_color=(50, 120, 80),
            on_click=self._confirm,
        )
        self._btn_back = Button(
            rect=pygame.Rect(20, H - 80, 120, btn_h),
            label="BACK",
            font=manager.font_medium,
            on_click=self._back,
        )

    def _confirm(self) -> None:
        if not self._characters:
            return
        key = self._characters[self._selected][0]
        self.manager.engine.start_campaign(key)
        from scenes.battle import BattleScene
        self.manager.switch_to(BattleScene(self.manager))

    def _back(self) -> None:
        from scenes.title import TitleScene
        self.manager.switch_to(TitleScene(self.manager))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._selected = max(0, self._selected - 1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._selected = min(len(self._characters) - 1, self._selected + 1)
            elif event.key == pygame.K_RETURN:
                self._confirm()
            elif event.key == pygame.K_ESCAPE:
                self._back()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._card_rects):
                if rect.collidepoint(event.pos):
                    self._selected = i
        self._btn_confirm.handle_event(event)
        self._btn_back.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(pal.BG_DARK)
        W, H = surface.get_size()

        title = self.manager.font_large.render("CHOOSE YOUR CHARACTER", True, pal.TEXT_TITLE)
        surface.blit(title, title.get_rect(center=(W // 2, 50)))

        for i, (key, data) in enumerate(self._characters):
            rect = self._card_rects[i]
            selected = i == self._selected
            self._draw_char_card(surface, rect, key, data, selected)

        self._btn_confirm.draw(surface)
        self._btn_back.draw(surface)

        hint = self.manager.font_tiny.render("← → to browse  |  ENTER to confirm", True, pal.TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(W // 2, H - 20)))

    def _draw_char_card(
        self, surface: pygame.Surface, rect: pygame.Rect,
        key: str, data: dict, selected: bool
    ) -> None:
        bg = pal.BG_PANEL_ALT if selected else pal.BG_PANEL
        border = pal.BORDER_SELECT if selected else pal.BORDER
        pygame.draw.rect(surface, bg, rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 2, border_radius=6)

        name = str(data.get("name", key))
        ability = str(data.get("ability", ""))
        hp = data.get("health", "?")
        hp_cap = data.get("health_cap", hp)
        deck_key = "inital_deck" if "inital_deck" in data else "initial_deck"
        deck = data.get(deck_key, [])

        y = rect.y + 16

        # Name
        surf = self.manager.font_medium.render(name, True, pal.TEXT_TITLE)
        surface.blit(surf, surf.get_rect(centerx=rect.centerx, top=y))
        y += 36

        # Silhouette placeholder
        sil_rect = pygame.Rect(rect.x + 30, y, rect.w - 60, 100)
        pygame.draw.rect(surface, (30, 40, 55), sil_rect, border_radius=4)
        pygame.draw.rect(surface, pal.BORDER, sil_rect, 1, border_radius=4)
        icon_surf = self.manager.font_large.render(name[0].upper(), True, pal.BORDER_BRIGHT)
        surface.blit(icon_surf, icon_surf.get_rect(center=sil_rect.center))
        y += 110

        # Stats
        for label, value in [("HP", f"{hp}/{hp_cap}"), ("Cards", str(len(deck)))]:
            line = self.manager.font_small.render(f"{label}: {value}", True, pal.TEXT_PRIMARY)
            surface.blit(line, (rect.x + 14, y))
            y += 20

        # Ability
        y += 6
        ab_label = self.manager.font_tiny.render("ABILITY:", True, pal.TEXT_DIM)
        surface.blit(ab_label, (rect.x + 14, y))
        y += 14
        words = ability.split()
        line_str = ""
        for word in words:
            test = (line_str + " " + word).strip()
            if self.manager.font_tiny.size(test)[0] > rect.w - 28:
                surf2 = self.manager.font_tiny.render(line_str, True, pal.TEXT_DIM)
                surface.blit(surf2, (rect.x + 14, y))
                y += 13
                line_str = word
            else:
                line_str = test
        if line_str:
            surf2 = self.manager.font_tiny.render(line_str, True, pal.TEXT_DIM)
            surface.blit(surf2, (rect.x + 14, y))

        # Starting deck preview
        y = rect.y + rect.h - 14
        deck_label = self.manager.font_tiny.render(
            f"Starting deck: {len(deck)} cards", True, pal.TEXT_DIM)
        surface.blit(deck_label, (rect.x + 14, y - 4))
