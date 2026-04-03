from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from core.engine import GameEngine

if TYPE_CHECKING:
    from scenes.base_scene import BaseScene


_CJK_FONT_CANDIDATES = [
    "stheitimedium",      # macOS
    "stheitilight",       # macOS
    "hiraginosansgb",     # macOS (Simplified, but renders TC glyphs too)
    "microsoftyahei",     # Windows
    "simsun",             # Windows
    "wenquanyimicrohei",  # Linux
    "notosanscjk",        # Linux / cross-platform
    "arial",              # fallback (no CJK, but won't crash)
]


def _pick_cjk_font() -> str:
    """Return the first available CJK-capable system font name."""
    available = set(pygame.font.get_fonts())
    for name in _CJK_FONT_CANDIDATES:
        if name in available:
            return name
    return ""  # empty string → pygame default font


class SceneManager:
    """Manages the active scene and the shared GameEngine."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen  = screen
        self.engine  = GameEngine()
        self._scene: "BaseScene | None" = None
        self.running = True

        # Shared fonts (loaded once, reused by all scenes).
        # CJK-capable font candidates tried in order for cross-platform support.
        _cjk_font = _pick_cjk_font()
        self.font_large  = pygame.font.SysFont(_cjk_font, 32, bold=True)
        self.font_medium = pygame.font.SysFont(_cjk_font, 20, bold=True)
        self.font_small  = pygame.font.SysFont(_cjk_font, 14)
        self.font_tiny   = pygame.font.SysFont(_cjk_font, 11)

    @property
    def scene(self) -> "BaseScene | None":
        return self._scene

    def switch_to(self, scene: "BaseScene") -> None:
        self._scene = scene

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if self._scene:
                    self._scene.handle_event(event)

            if self._scene:
                self._scene.update(dt)
                self._scene.draw(self.screen)

            pygame.display.flip()
