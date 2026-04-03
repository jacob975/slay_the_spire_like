from __future__ import annotations

import os
import sys

import pygame

# Suppress pygame hello message
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Dungeon Cards")

    screen = pygame.display.set_mode((1280, 720))

    from ui.scene_manager import SceneManager
    from scenes.title import TitleScene

    manager = SceneManager(screen)
    manager.switch_to(TitleScene(manager))
    manager.run()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
