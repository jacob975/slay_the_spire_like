"""Pixel-art dungeon color palette."""

# Backgrounds
BG_DARK       = (14,  17,  22)   # main game background
BG_PANEL      = (24,  30,  40)   # panel / card background
BG_PANEL_ALT  = (32,  40,  52)   # hover / selected panel
BG_OVERLAY    = (0,   0,   0,  180)  # semi-transparent overlay (RGBA)

# Borders & lines
BORDER        = (60,  75,  95)
BORDER_BRIGHT = (100, 130, 160)
BORDER_SELECT = (220, 190,  60)  # selected / highlighted border

# Text
TEXT_PRIMARY  = (220, 215, 200)  # main body text
TEXT_DIM      = (120, 120, 110)  # secondary / disabled text
TEXT_TITLE    = (255, 240, 160)  # title / heading gold

# HP / Status
HP_HIGH       = ( 60, 180,  80)  # HP bar >= 50 %
HP_MID        = (220, 160,  30)  # HP bar 25–50 %
HP_LOW        = (200,  50,  50)  # HP bar < 25 %
BLOCK_COLOR   = ( 80, 120, 200)  # block bar

# Energy pips
ENERGY_FULL   = (255, 200,  40)
ENERGY_EMPTY  = ( 50,  50,  50)

# Card types
CARD_ATTACK   = ( 80,  30,  30)   # dark red
CARD_SKILL    = ( 30,  50,  80)   # dark blue
CARD_POWER    = ( 60,  30,  80)   # dark purple
CARD_COST_BG  = ( 20,  20,  20)
CARD_COST_FG  = (240, 200,  60)

# Status effects
STATUS_WEAK       = (160,  80,  30)
STATUS_VULNERABLE = (180,  50,  50)
STATUS_POISON      = ( 80, 160,  40)
STATUS_REGEN       = ( 60, 180, 120)

# UI actions
BTN_NORMAL    = ( 40,  55,  70)
BTN_HOVER     = ( 55,  75, 100)
BTN_PRESSED   = ( 25,  35,  50)
BTN_TEXT      = (210, 210, 200)
BTN_DANGER    = ( 90,  30,  30)
BTN_SUCCESS   = ( 30,  80,  50)

# Effects
DAMAGE_FLASH  = (255, 100,  80)
HEAL_FLASH    = ( 80, 220, 120)
