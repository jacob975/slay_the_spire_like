from __future__ import annotations

import abc

import pygame


class BaseScene(abc.ABC):
    """Abstract base for all game scenes."""

    def __init__(self, manager: "SceneManager") -> None:
        self.manager = manager

    @abc.abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None: ...

    @abc.abstractmethod
    def update(self, dt: float) -> None: ...

    @abc.abstractmethod
    def draw(self, surface: pygame.Surface) -> None: ...
