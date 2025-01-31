class Style:
    styles = {
        "END": "\033[0m",

        "BOLD": "\033[1m",
        "DIM": "\033[2m",
        "ITALIC": "\033[3m",
        "UNDERLINED": "\033[4m",
        "BLINK": "\033[5m",
        "REVERSE": "\033[7m",
        "HIDDEN": "\033[8m",

        "END_BOLD": "\033[21m",
        "END_DIM": "\033[22m",
        "END_ITALIC": "\033[23m",
        "END_UNDERLINED": "\033[24m",
        "END_BLINK": "\033[25m",
        "END_REVERSE": "\033[27m",
        "END_HIDDEN": "\033[28m",

        # Text colors
        "BLACK": "\033[30m",
        "DARK_RED": "\033[31m",
        "DARK_GREEN": "\033[32m",
        "DARK_YELLOW": "\033[33m",
        "DARK_BLUE": "\033[34m",
        "DARK_MAGENTA": "\033[35m",
        "DARK_CYAN": "\033[36m",
        "LIGHT_GRAY": "\033[37m",

        "END_COLOR": "\033[39m",

        "DARKGRAY": "\033[90m",
        "RED": "\033[91m",
        "GREEN": "\033[92m",
        "YELLOW": "\033[93m",
        "BLUE": "\033[94m",
        "MAGENTA": "\033[95m",
        "CYAN": "\033[96m",
        "WHITE": "\033[97m",

        # Background colors
        "BG_BLACK": "\033[40m",
        "BG_DARK_RED": "\033[41m",
        "BG_DARK_GREEN": "\033[42m",
        "BG_DARK_YELLOW": "\033[43m",
        "BG_DARK_BLUE": "\033[44m",
        "BG_DARK_MAGENTA": "\033[45m",
        "BG_DARK_CYAN": "\033[46m",
        "BG_LIGHT_GRAY": "\033[47m",

        "END_BG": "\033[49m",

        "BG_DARKGRAY": "\033[100m",
        "BG_RED": "\033[101m",
        "BG_GREEN": "\033[102m",
        "BG_YELLOW": "\033[103m",
        "BG_BLUE": "\033[104m",
        "BG_MAGENTA": "\033[105m",
        "BG_CYAN": "\033[106m",
        "BG_WHITE": "\033[107m",
    }
    # Other
    styles['ORANGE'] = styles['DARK_YELLOW']
    styles['BG_ORANGE'] = styles['BG_DARK_YELLOW']
    styles['PURPLE'] = styles['DARK_MAGENTA']
    styles['BG_PURPLE'] = styles['BG_DARK_MAGENTA']
    styles['PINK'] = styles['MAGENTA']
    styles['BG_PINK'] = styles['BG_MAGENTA']

    def __init__(self, code=""):
        self.code = code

    def __getattr__(self, name: str) -> "Style":
        if name in self.styles:
            return Style(self.code + self.styles[name])
        raise AttributeError(f"'Style' object has no attribute '{name}'")

    def __str__(self) -> str:
        return self.code

    # Trick for Auto-complete Support during Static Code Analysis
    END: "Style"

    BOLD: "Style"
    DIM: "Style"
    ITALIC: "Style"
    UNDERLINED: "Style"
    BLINK: "Style"
    REVERSE: "Style"
    HIDDEN: "Style"

    END_BOLD: "Style"
    END_DIM: "Style"
    END_ITALIC: "Style"
    END_UNDERLINED: "Style"
    END_BLINK: "Style"
    END_REVERSE: "Style"
    END_HIDDEN: "Style"

    # Text colors
    BLACK: "Style"
    DARK_RED: "Style"
    DARK_GREEN: "Style"
    DARK_YELLOW: "Style"
    DARK_BLUE: "Style"
    DARK_MAGENTA: "Style"
    DARK_CYAN: "Style"
    LIGHT_GRAY: "Style"

    END_COLOR: "Style"

    DARKGRAY: "Style"
    RED: "Style"
    GREEN: "Style"
    YELLOW: "Style"
    BLUE: "Style"
    MAGENTA: "Style"
    CYAN: "Style"
    WHITE: "Style"

    # Background colors
    BG_BLACK: "Style"
    BG_DARK_RED: "Style"
    BG_DARK_GREEN: "Style"
    BG_DARK_YELLOW: "Style"
    BG_DARK_BLUE: "Style"
    BG_DARK_MAGENTA: "Style"
    BG_DARK_CYAN: "Style"
    BG_LIGHT_GRAY: "Style"

    END_BG: "Style"

    BG_DARKGRAY: "Style"
    BG_RED: "Style"
    BG_GREEN: "Style"
    BG_YELLOW: "Style"
    BG_BLUE: "Style"
    BG_MAGENTA: "Style"
    BG_CYAN: "Style"
    BG_WHITE: "Style"

    # Other
    ORANGE: "Style"
    BG_ORANGE: "Style"
    PURPLE: "Style"
    BG_PURPLE: "Style"
    PINK: "Style"
    BG_PINK: "Style"


END = Style(Style.styles["END"])

BOLD = Style(Style.styles["BOLD"])
DIM = Style(Style.styles["DIM"])
ITALIC = Style(Style.styles["ITALIC"])
UNDERLINED = Style(Style.styles["UNDERLINED"])
BLINK = Style(Style.styles["BLINK"])
REVERSE = Style(Style.styles["REVERSE"])
HIDDEN = Style(Style.styles["HIDDEN"])

END_BOLD = Style(Style.styles["END_BOLD"])
END_DIM = Style(Style.styles["END_DIM"])
END_ITALIC = Style(Style.styles["END_ITALIC"])
END_UNDERLINED = Style(Style.styles["END_UNDERLINED"])
END_BLINK = Style(Style.styles["END_BLINK"])
END_REVERSE = Style(Style.styles["END_REVERSE"])
END_HIDDEN = Style(Style.styles["END_HIDDEN"])

# Text colors
BLACK = Style(Style.styles["BLACK"])
DARK_RED = Style(Style.styles["DARK_RED"])
DARK_GREEN = Style(Style.styles["DARK_GREEN"])
DARK_YELLOW = Style(Style.styles["DARK_YELLOW"])
DARK_BLUE = Style(Style.styles["DARK_BLUE"])
DARK_MAGENTA = Style(Style.styles["DARK_MAGENTA"])
DARK_CYAN = Style(Style.styles["DARK_CYAN"])
LIGHT_GRAY = Style(Style.styles["LIGHT_GRAY"])

END_COLOR = Style(Style.styles["END_COLOR"])

DARKGRAY = Style(Style.styles["DARKGRAY"])
RED = Style(Style.styles["RED"])
GREEN = Style(Style.styles["GREEN"])
YELLOW = Style(Style.styles["YELLOW"])
BLUE = Style(Style.styles["BLUE"])
MAGENTA = Style(Style.styles["MAGENTA"])
CYAN = Style(Style.styles["CYAN"])
WHITE = Style(Style.styles["WHITE"])

# Background colors
BG_BLACK = Style(Style.styles["BG_BLACK"])
BG_DARK_RED = Style(Style.styles["BG_DARK_RED"])
BG_DARK_GREEN = Style(Style.styles["BG_DARK_GREEN"])
BG_DARK_YELLOW = Style(Style.styles["BG_DARK_YELLOW"])
BG_DARK_BLUE = Style(Style.styles["BG_DARK_BLUE"])
BG_DARK_MAGENTA = Style(Style.styles["BG_DARK_MAGENTA"])
BG_DARK_CYAN = Style(Style.styles["BG_DARK_CYAN"])
BG_LIGHT_GRAY = Style(Style.styles["BG_LIGHT_GRAY"])

END_BG = Style(Style.styles["END_BG"])

BG_DARKGRAY = Style(Style.styles["BG_DARKGRAY"])
BG_RED = Style(Style.styles["BG_RED"])
BG_GREEN = Style(Style.styles["BG_GREEN"])
BG_YELLOW = Style(Style.styles["BG_YELLOW"])
BG_BLUE = Style(Style.styles["BG_BLUE"])
BG_MAGENTA = Style(Style.styles["BG_MAGENTA"])
BG_CYAN = Style(Style.styles["BG_CYAN"])
BG_WHITE = Style(Style.styles["BG_WHITE"])

# Other
ORANGE = DARK_YELLOW
BG_ORANGE = BG_DARK_YELLOW
PURPLE = DARK_MAGENTA
BG_PURPLE = BG_DARK_MAGENTA
PINK = MAGENTA
BG_PINK = BG_MAGENTA

if __name__ == "__main__":
    # Basic Text Styles
    print(f"{BOLD}This is bold text!{END}")
    print(f"{ITALIC}This is italic text!{END}")
    print(f"{UNDERLINED}This is underlined text!{END}")
    print(f"{BLINK}This text is blinking (if supported)!{END}")
    print(f"{REVERSE}This text has reversed colors!{END}")

    # Text Colors
    print(f"{RED}This is red text!{END}")
    print(f"{GREEN}This is green text!{END}")
    print(f"{BLUE}This is blue text!{END}")
    print(f"{YELLOW}This is yellow text!{END}")

    # Background Colors
    print(f"{BG_RED}This is text with a red background!{END}")
    print(f"{BG_GREEN}This is text with a green background!{END}")
    print(f"{BG_BLUE}This is text with a blue background!{END}")
    print(f"{BG_YELLOW}This is text with a yellow background!{END}")

    # Combining Text Color and Background Color
    print(f"{RED.BG_YELLOW}Red text on a yellow background!{END}")
    print(f"{WHITE.BG_BLUE}White text on a blue background!{END}")

    # Combining Multiple Styles
    print(f"{BOLD.UNDERLINED.GREEN}Bold, underlined and green text!{END}")
    print(f"{ITALIC.BLINK.RED.BG_WHITE}Italic and blinking red text on white background!{END}")
