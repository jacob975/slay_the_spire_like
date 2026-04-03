from __future__ import annotations

from typing import Optional, Tuple

import pygame

from core.models import Card
from ui import palette as pal


CARD_W = 110
CARD_H = 155


def card_bg_color(card_type: str) -> Tuple[int, int, int]:
    t = card_type.lower()
    if t == "attack":
        return pal.CARD_ATTACK
    if t == "power":
        return pal.CARD_POWER
    return pal.CARD_SKILL


class CardWidget:
    """Renders a Card as a pixel-art card panel."""

    def __init__(
        self,
        card: Card,
        pos: Tuple[int, int],
        font_name: pygame.font.Font,
        font_small: pygame.font.Font,
        selected: bool = False,
        highlighted: bool = False,
        dimmed: bool = False,
    ) -> None:
        self.card        = card
        self.rect        = pygame.Rect(pos[0], pos[1], CARD_W, CARD_H)
        self.font_name   = font_name
        self.font_small  = font_small
        self.selected    = selected
        self.highlighted = highlighted
        self.dimmed      = dimmed

    def draw(self, surface: pygame.Surface) -> None:
        rect = self.rect
        mouse = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse)

        lift = 8 if (hovered or self.selected) else 0
        draw_rect = pygame.Rect(rect.x, rect.y - lift, rect.w, rect.h)

        # Background
        bg = card_bg_color(self.card.type)
        if self.dimmed:
            bg = tuple(max(0, c - 40) for c in bg)  # type: ignore[assignment]
        pygame.draw.rect(surface, bg, draw_rect, border_radius=4)

        # Border
        border = pal.BORDER_SELECT if (self.selected or hovered) else pal.BORDER_BRIGHT
        if self.dimmed:
            border = pal.BORDER
        pygame.draw.rect(surface, border, draw_rect, 2, border_radius=4)

        # Cost pip (top-left)
        cost_rect = pygame.Rect(draw_rect.x + 4, draw_rect.y + 4, 22, 22)
        pygame.draw.rect(surface, pal.CARD_COST_BG, cost_rect, border_radius=3)
        pygame.draw.rect(surface, pal.BORDER_BRIGHT, cost_rect, 1, border_radius=3)
        cost_surf = self.font_name.render(str(self.card.cost), True, pal.CARD_COST_FG)
        surface.blit(cost_surf, cost_surf.get_rect(center=cost_rect.center))

        # Type label (top-right, tiny)
        type_surf = self.font_small.render(self.card.type.upper(), True, pal.TEXT_DIM)
        surface.blit(type_surf, (draw_rect.right - type_surf.get_width() - 4, draw_rect.y + 6))

        # Art area placeholder (simple icon line)
        art_rect = pygame.Rect(draw_rect.x + 8, draw_rect.y + 32, draw_rect.w - 16, 50)
        pygame.draw.rect(surface, (0, 0, 0, 80), art_rect, border_radius=2)
        pygame.draw.rect(surface, pal.BORDER, art_rect, 1, border_radius=2)
        # Draw a simple type icon
        self._draw_type_icon(surface, art_rect)

        # Name
        name_surf = self.font_name.render(self.card.name, True, pal.TEXT_PRIMARY)
        if name_surf.get_width() > draw_rect.w - 8:
            name_surf = pygame.transform.scale(
                name_surf, (draw_rect.w - 8, name_surf.get_height()))
        surface.blit(name_surf, (draw_rect.x + 4, draw_rect.y + 88))

        # Description (word-wrapped)
        self._draw_desc(surface, draw_rect)

    def _draw_type_icon(self, surface: pygame.Surface, art_rect: pygame.Rect) -> None:
        cx, cy = art_rect.centerx, art_rect.centery
        t = self.card.type.lower()
        if t == "attack":
            # Sword shape
            pts = [(cx, cy - 16), (cx + 5, cy + 10), (cx, cy + 6), (cx - 5, cy + 10)]
            pygame.draw.polygon(surface, (180, 120, 120), pts)
        elif t == "skill":
            # Shield
            pts = [(cx, cy - 14), (cx + 12, cy - 4), (cx + 10, cy + 10),
                   (cx, cy + 16), (cx - 10, cy + 10), (cx - 12, cy - 4)]
            pygame.draw.polygon(surface, (100, 140, 200), pts)
        else:
            # Star / power
            pygame.draw.circle(surface, (180, 100, 220), (cx, cy), 12)
            pygame.draw.circle(surface, (220, 150, 255), (cx, cy), 6)

    def _draw_desc(self, surface: pygame.Surface, draw_rect: pygame.Rect) -> None:
        desc = self.card.description
        y = draw_rect.y + 104
        max_w = draw_rect.w - 8

        # Build wrap units: Chinese characters are split individually;
        # ASCII words are kept whole (split by spaces).
        units: list[str] = []
        for token in desc.split(" "):
            if not token:
                continue
            # Check if any character in the token is CJK
            if any("\u4e00" <= ch <= "\u9fff" for ch in token):
                units.extend(list(token))
            else:
                units.append(token)

        line = ""
        for unit in units:
            sep = "" if (not line or any("\u4e00" <= ch <= "\u9fff" for ch in line[-1]) or any("\u4e00" <= ch <= "\u9fff" for ch in unit)) else " "
            test = line + sep + unit
            if self.font_small.size(test)[0] > max_w:
                if line:
                    surf = self.font_small.render(line, True, pal.TEXT_DIM)
                    surface.blit(surf, (draw_rect.x + 4, y))
                    y += 13
                line = unit
            else:
                line = test
        if line:
            surf = self.font_small.render(line, True, pal.TEXT_DIM)
            surface.blit(surf, (draw_rect.x + 4, y))
