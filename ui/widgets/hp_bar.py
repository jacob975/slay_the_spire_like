from __future__ import annotations

from typing import Tuple

import pygame

from ui import palette as pal


def draw_hp_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    current: int,
    maximum: int,
    show_text: bool = True,
    font: pygame.font.Font = None,  # type: ignore[assignment]
) -> None:
    """Draw a segmented HP bar inside rect."""
    pygame.draw.rect(surface, (20, 20, 20), rect)
    if maximum > 0:
        ratio = max(0.0, min(1.0, current / maximum))
        if ratio > 0.5:
            color = pal.HP_HIGH
        elif ratio > 0.25:
            color = pal.HP_MID
        else:
            color = pal.HP_LOW
        fill = pygame.Rect(rect.x, rect.y, int(rect.w * ratio), rect.h)
        pygame.draw.rect(surface, color, fill)
    pygame.draw.rect(surface, pal.BORDER, rect, 1)

    if show_text and font:
        label = f"{current}/{maximum}"
        surf = font.render(label, True, pal.TEXT_PRIMARY)
        surface.blit(surf, surf.get_rect(center=rect.center))


def draw_block_pip(
    surface: pygame.Surface,
    x: int,
    y: int,
    block: int,
    font: pygame.font.Font,
) -> None:
    """Draw a shield icon with block value next to it."""
    if block <= 0:
        return
    shield_rect = pygame.Rect(x, y, 20, 20)
    pts = [
        (shield_rect.centerx, shield_rect.top),
        (shield_rect.right, shield_rect.top + 5),
        (shield_rect.right - 2, shield_rect.bottom - 4),
        (shield_rect.centerx, shield_rect.bottom),
        (shield_rect.left + 2, shield_rect.bottom - 4),
        (shield_rect.left, shield_rect.top + 5),
    ]
    pygame.draw.polygon(surface, pal.BLOCK_COLOR, pts)
    pygame.draw.polygon(surface, pal.BORDER_BRIGHT, pts, 1)
    surf = font.render(str(block), True, pal.TEXT_PRIMARY)
    surface.blit(surf, (x + 24, y + 2))


def draw_energy_pips(
    surface: pygame.Surface,
    x: int,
    y: int,
    current: int,
    maximum: int = 3,
    pip_size: int = 16,
) -> None:
    """Draw energy pips as small circles."""
    for i in range(maximum):
        cx = x + i * (pip_size + 4) + pip_size // 2
        cy = y + pip_size // 2
        color = pal.ENERGY_FULL if i < current else pal.ENERGY_EMPTY
        pygame.draw.circle(surface, color, (cx, cy), pip_size // 2)
        pygame.draw.circle(surface, pal.BORDER_BRIGHT, (cx, cy), pip_size // 2, 1)


def draw_status_tags(
    surface: pygame.Surface,
    x: int,
    y: int,
    statuses: dict,
    font: pygame.font.Font,
) -> None:
    """Draw small colored status badges."""
    STATUS_COLORS = {
        "weak":       pal.STATUS_WEAK,
        "vulnerable": pal.STATUS_VULNERABLE,
        "poison":     pal.STATUS_POISON,
        "regen":      pal.STATUS_REGEN,
    }
    cx = x
    for name, turns in statuses.items():
        color = STATUS_COLORS.get(name, pal.BORDER)
        label = f"{name[:3].upper()}({turns})"
        surf = font.render(label, True, pal.TEXT_PRIMARY)
        bg_rect = pygame.Rect(cx, y, surf.get_width() + 6, surf.get_height() + 2)
        pygame.draw.rect(surface, color, bg_rect, border_radius=3)
        surface.blit(surf, (cx + 3, y + 1))
        cx += bg_rect.w + 4
