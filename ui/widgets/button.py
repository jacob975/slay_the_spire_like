from __future__ import annotations

from typing import Callable, Optional, Tuple

import pygame

from ui import palette as pal


class Button:
    """Clickable pixel-art button."""

    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int] = pal.BTN_NORMAL,
        hover_color: Tuple[int, int, int] = pal.BTN_HOVER,
        text_color: Tuple[int, int, int] = pal.BTN_TEXT,
        border_color: Tuple[int, int, int] = pal.BORDER,
        on_click: Optional[Callable[[], None]] = None,
    ) -> None:
        self.rect        = rect
        self.label       = label
        self.font        = font
        self.color       = color
        self.hover_color = hover_color
        self.text_color  = text_color
        self.border_color = border_color
        self.on_click    = on_click
        self._pressed    = False
        self.enabled     = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if button was clicked."""
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                if self.on_click:
                    self.on_click()
                return True
            self._pressed = False
        return False

    def draw(self, surface: pygame.Surface) -> None:
        mouse = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse) and self.enabled
        bg = self.hover_color if hovered else self.color
        if not self.enabled:
            bg = pal.BTN_PRESSED

        pygame.draw.rect(surface, bg, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)

        color = self.text_color if self.enabled else pal.TEXT_DIM
        text_surf = self.font.render(self.label, True, color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
