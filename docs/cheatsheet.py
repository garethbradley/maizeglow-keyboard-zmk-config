#!/usr/bin/env python3
"""
Generate docs/MaizeGlow-cheatsheet.pdf from the keymap sources.

Reads the layer files, combos, macros and per-key RGB maps, so the sheet stays in sync with the
firmware. Needs reportlab:  pip install reportlab
"""

import re
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
SHIELD = ROOT / "boards/shields/maizeglow"
OUT = Path(__file__).resolve().parent / "MaizeGlow-cheatsheet.pdf"

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "Arial Unicode.ttf")))  # has arrows
pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "Arial Bold.ttf")))

INK = HexColor("#1d1d1f")
MUTED = HexColor("#6e6e73")
RULE = HexColor("#d2d2d7")
OFF_FILL = HexColor("#f5f5f7")
OFF_EDGE = HexColor("#e3e3e8")

# ---------------------------------------------------------------------------------------------
# Parsing


def strip_comments(text):
    return re.sub(r"//[^\n]*", "", text)


def parse_bindings(block):
    """'&kp TAB &mo LOWER &bt BT_SEL 0' -> [('kp', ['TAB']), ('mo', ['LOWER']), ...]"""
    out = []
    for tok in re.split(r"\s*&", " " + block.strip())[1:]:
        parts = tok.split()
        out.append((parts[0], parts[1:]))
    return out


def load_layer_ids():
    ids = {}
    for name, num in re.findall(r"#define\s+(\w+)\s+(\d+)", (SHIELD / "os/layers.keymap").read_text()):
        ids[name] = int(num)
    return ids


def load_layers():
    layers = []
    for path in sorted((SHIELD / "keymap").glob("*.keymap")):
        text = strip_comments(path.read_text())
        name = re.search(r'display-name\s*=\s*"([^"]+)"', text).group(1)
        body = re.search(r"bindings\s*=\s*<(.*?)>\s*;", text, re.S).group(1)
        layers.append({"name": name, "keys": parse_bindings(body)})
    return layers


def load_rgb(layer_ids):
    """layer number -> list of 42 (hex colour) ; plus legend [(hex, label, description)]"""
    text = (SHIELD / "settings/rgb_layers.keymap").read_text()
    colours, legend = {}, []
    for macro, hexval, comment in re.findall(
        r"#define\s+(UG_\w+)\s+&ug\s+0x([0-9A-Fa-f]{6})[ \t]*(?://\s*(.*))?", text
    ):
        colours[macro] = "#" + hexval
        if comment:
            label, _, desc = comment.partition(":")
            legend.append(("#" + hexval, label.strip(), desc.strip()))
    maps = {}
    body = strip_comments(text)
    for layer, bindings in re.findall(r"layer-id\s*=\s*<(\w+)>;\s*bindings\s*=\s*<(.*?)>;", body, re.S):
        maps[layer_ids[layer]] = [colours[m] for m in re.findall(r"\bUG_\w+\b", bindings)]
    return maps, legend


def load_combos():
    combos = []
    for line in strip_comments((SHIELD / "os/combos.keymap").read_text()).splitlines():
        m = re.match(r"\s*COMBO_ALL\((\w+),\s*(&[^,]+),\s*([\d ]+)\)", line)
        if m:
            combos.append((m.group(2), [int(p) for p in m.group(3).split()], None))
            continue
        m = re.match(r"\s*COMBO\((\w+),\s*(&[^,]+),\s*([\d ]+),\s*([\d ]+)\)", line)
        if m:
            combos.append((m.group(2), [int(p) for p in m.group(3).split()],
                           [int(l) for l in m.group(4).split()]))
    return combos


# ---------------------------------------------------------------------------------------------
# Key labels

KP = {
    "TAB": "Tab", "BSPC": "Bksp", "DEL": "Del", "INS": "Ins", "ESC": "Esc", "SPACE": "Space",
    "ENTER": "Enter", "LCTRL": "Ctrl", "LSHFT": "Shift", "LALT": "Alt", "RALT": "AltGr",
    "LGUI": "GUI", "SEMI": ";", "SQT": "'", "COMMA": ",", "DOT": ".", "FSLH": "/",
    "EQUAL": "=", "MINUS": "-", "LBKT": "[", "RBKT": "]", "BSLH": "\\", "UP": "↑", "DOWN": "↓",
    "LEFT": "←", "RIGHT": "→", "TILDE": "~", "EXCL": "!", "AT": "@", "HASH": "#", "DLLR": "$",
    "PRCNT": "%", "CARET": "^", "AMPS": "&", "ASTERISK": "*", "LPAR": "(", "RPAR": ")",
    "UNDER": "_", "PLUS": "+", "LBRC": "{", "RBRC": "}", "PIPE": "|", "HOME": "Home",
    "END": "End", "PAGE_UP": "PgUp", "PAGE_DOWN": "PgDn", "KP_NLCK": "Num\nLock",
    "KP_DIVIDE": "/", "KP_MULTIPLY": "*", "KP_MINUS": "-", "KP_PLUS": "+", "KP_DOT": ".",
    "C_BRI_INC": "Bright\n+", "C_BRI_DEC": "Bright\n−", "CAPSLOCK": "Caps\nLock",
    "SCROLLLOCK": "Scroll\nLock", "PSCRN": "Print\nScreen", "C_AC_HOME": "Browser\nHome",
    "C_AL_EMAIL": "Email", "C_PREV": "Prev\ntrack", "C_NEXT": "Next\ntrack", "C_VOL_DN": "Vol −",
    "C_VOL_UP": "Vol +", "C_PLAY_PAUSE": "Play /\nPause",
}

MACROS = {
    "tab_prev": ("Prev\ntab", "Ctrl + PgUp — previous tab"),
    "tab_next": ("Next\ntab", "Ctrl + PgDn — next tab"),
    "lng_eng": ("EN", "Ctrl + Shift + 1 — English input"),
    "lng_lt": ("LT", "Ctrl + Shift + 2 — Lithuanian input"),
    "lng_ru": ("RU", "Ctrl + Shift + 3 — Russian input"),
    "alt_summary": ("Alt\n61", "Alt + numpad 6, 1 (Alt code 61)"),
    "log_off": ("Lock", "Win + L — lock the computer"),
    "code_format_doc": ("Format", "Shift + Alt + F — format document"),
    "screenshot": ("Screen\nshot", "Shift + Cmd + 4 — area screenshot (macOS)"),
}

# Group names for the LED colours in settings/rgb_layers.keymap (keyed by the comment's colour name)
GROUP_NAMES = {
    "cyan": "Navigation", "yellow": "Numbers", "purple": "Symbols", "blue": "F-keys",
    "orange": "Editing", "dim white": "Modifiers", "pink": "Layer keys",
    "green": "System & media", "white": "Connectivity", "red": "Danger",
}

OUT_CMDS = {"OUT_TOG": "USB ⇄\nBLE", "OUT_BLE": "BLE", "OUT_USB": "USB"}
RGB_CMDS = {"RGB_TOG": "LEDs\non/off", "RGB_EFF": "Effect\nnext", "RGB_EFR": "Effect\nprev",
            "RGB_BRI": "LED\nbright +", "RGB_BRD": "LED\nbright −", "RGB_HUI": "Hue +",
            "RGB_HUD": "Hue −", "RGB_SAI": "Sat +", "RGB_SAD": "Sat −", "RGB_SPI": "Speed +",
            "RGB_SPD": "Speed −"}


def label(behavior, params, layer_names):
    """-> (main label, small sub-label)"""
    if behavior == "kp":
        k = params[0]
        if re.fullmatch(r"N\d", k) or re.fullmatch(r"KP_N\d", k):
            return k[-1], ""
        if re.fullmatch(r"F\d+", k):
            return k, ""
        if len(k) == 1:
            return k, ""
        return KP.get(k, k.replace("_", " ").title()), ""
    if behavior == "mo":
        return layer_names.get(params[0], params[0]), "hold"
    if behavior == "to":
        return "→ " + layer_names.get(params[0], params[0]), "tap"
    if behavior == "bt":
        cmd = params[0]
        if cmd == "BT_SEL":
            return f"BT {params[1]}", "profile"
        return {"BT_PRV": ("BT\nprev", ""), "BT_NXT": ("BT\nnext", ""),
                "BT_CLR": ("Clear\nBT", ""), "BT_CLR_ALL": ("Clear\nall BT", "")}.get(cmd, (cmd, ""))
    if behavior == "out":
        return OUT_CMDS.get(params[0], params[0]), ""
    if behavior == "rgb_ug":
        return RGB_CMDS.get(params[0], params[0]), ""
    if behavior in ("none", "trans"):
        return "", ""
    if behavior in MACROS:
        return MACROS[behavior][0], ""
    return behavior, ""


# BASE has no LED map (it shows the animated effect); colour its keys by the same groups
def base_group(behavior, params, legend_by_label):
    k = params[0] if params else ""
    if behavior in ("mo", "to"):
        return legend_by_label.get("pink")
    if k in ("LCTRL", "LSHFT", "LALT", "RALT", "LGUI"):
        return legend_by_label.get("dim white")
    if k in ("TAB", "BSPC", "DEL", "ESC", "SPACE", "ENTER", "INS"):
        return legend_by_label.get("orange")
    if k in ("SEMI", "SQT", "COMMA", "DOT", "FSLH"):
        return legend_by_label.get("purple")
    return None  # letters: neutral


# ---------------------------------------------------------------------------------------------
# Drawing


def tint(hexcol, amount):
    """Mix a colour with white; amount=0 -> white, 1 -> colour."""
    c = HexColor(hexcol)
    return Color(1 - (1 - c.red) * amount, 1 - (1 - c.green) * amount, 1 - (1 - c.blue) * amount)


def shade(hexcol, amount):
    c = HexColor(hexcol)
    return Color(c.red * amount, c.green * amount, c.blue * amount)


def edge_for(hexcol):
    c = HexColor(hexcol)
    lum = 0.2126 * c.red + 0.7152 * c.green + 0.0722 * c.blue
    if lum > 0.85:  # white
        return HexColor("#b8b8c0")
    if lum < 0.3 and c.red == c.green == c.blue:  # dim white / grey
        return HexColor("#9a9aa2")
    return shade(hexcol, 0.85)


def fit_text(c, text, font, max_size, max_width):
    size = max_size
    while size > 5 and max(c.stringWidth(t, font, size) for t in text.split("\n")) > max_width:
        size -= 0.25
    return size


def draw_key(c, x, y, w, h, main, sub, colour, dim=False):
    if colour is None:
        fill, edge = white, RULE
    elif dim:
        fill, edge = OFF_FILL, OFF_EDGE
    else:
        fill, edge = tint(colour, 0.28), edge_for(colour)
    c.setFillColor(fill)
    c.setStrokeColor(edge)
    c.setLineWidth(0.9)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    if colour is not None and not dim:  # colour tab along the top edge
        c.setFillColor(HexColor(colour) if colour.lower() != "#ffffff" else HexColor("#c7c7cc"))
        c.roundRect(x + 3, y + h - 3.2, w - 6, 1.8, 0.9, stroke=0, fill=1)
    if not main:
        return
    lines = main.split("\n")
    start = 13 if len(main) == 1 else (10.5 if len(lines) == 1 else 8)
    size = fit_text(c, main, "Sans", start, w - 6)
    c.setFillColor(INK)
    line_h = size * 1.1
    total = line_h * len(lines) + (5 if sub else 0)
    ty = y + h / 2 + total / 2 - size * 0.85
    for line in lines:
        c.setFont("Sans", size)
        c.drawCentredString(x + w / 2, ty, line)
        ty -= line_h
    if sub:
        c.setFont("Sans", 5.5)
        c.setFillColor(MUTED)
        c.drawCentredString(x + w / 2, ty + line_h - size * 0.1 - 5.5, sub)


# keymap position -> (column, row); thumbs sit under columns 3-5 / 6-8
def position_grid():
    grid = []
    for row in range(3):
        for col in range(12):
            grid.append((col, row))
    for col in (3, 4, 5, 6, 7, 8):
        grid.append((col, 3))
    return grid


GRID = position_grid()


def draw_layer(c, x, y_top, width, layer, idx, rgb_map, reach, layer_names, legend_by_label):
    gap_units = 0.55
    unit = width / (12 + gap_units)
    kw, kh, pad = unit - 4, 29, 4
    # title
    c.setFont("Sans-Bold", 12.5)
    c.setFillColor(INK)
    c.drawString(x, y_top - 12, f"{idx} · {layer['name']}")
    tw = c.stringWidth(f"{idx} · {layer['name']}", "Sans-Bold", 12.5)
    c.setFont("Sans", 8.5)
    c.setFillColor(MUTED)
    c.drawString(x + tw + 10, y_top - 12, reach)
    top = y_top - 22
    for pos, (beh, params) in enumerate(layer["keys"]):
        col, row = GRID[pos]
        kx = x + col * unit + (gap_units * unit if col >= 6 else 0) + 2
        ky = top - (row + 1) * (kh + pad) + (-3 if row == 3 else 0)
        main, sub = label(beh, params, layer_names)
        if rgb_map:
            colour = rgb_map[pos]
            dim = colour.lower() == "#000000"
        else:
            colour = base_group(beh, params, legend_by_label)
            dim = False
        if not main:
            colour, dim = (colour or "#000000"), True
        draw_key(c, kx, ky, kw, kh, main, sub, colour, dim)
    return top - 4 * (kh + pad) - 3


def header(c, W, H, page, pages):
    c.setFillColor(INK)
    c.setFont("Sans-Bold", 17)
    c.drawString(28, H - 38, "MaizeGlow")
    c.setFont("Sans", 11)
    c.setFillColor(MUTED)
    c.drawString(28 + c.stringWidth("MaizeGlow", "Sans-Bold", 17) + 8, H - 38, "keymap cheat sheet")
    c.setFont("Sans", 8)
    c.drawRightString(W - 28, H - 38, f"{page} / {pages}")
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(28, H - 46, W - 28, H - 46)


def legend_strip(c, W, legend):
    y = 22
    c.setFont("Sans-Bold", 7)
    c.setFillColor(MUTED)
    c.drawString(28, y + 2, "KEY / LED COLOURS")
    x = 28 + c.stringWidth("KEY / LED COLOURS", "Sans-Bold", 7) + 10
    for hexcol, name, desc in legend:
        if name == "black":
            continue
        short = GROUP_NAMES.get(name, name)
        c.setFillColor(tint(hexcol, 0.28))
        c.setStrokeColor(edge_for(hexcol))
        c.roundRect(x, y, 10, 9, 2, stroke=1, fill=1)
        c.setFont("Sans", 7)
        c.setFillColor(INK)
        c.drawString(x + 13, y + 2, short)
        x += 13 + c.stringWidth(short, "Sans", 7) + 11


def panel(c, x, y, w, title, rows, col_split=0.42):
    c.setFont("Sans-Bold", 10.5)
    c.setFillColor(INK)
    c.drawString(x, y, title)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(x, y - 4, x + w, y - 4)
    y -= 17
    for left, right in rows:
        c.setFont("Sans", 8.2)
        c.setFillColor(INK)
        c.drawString(x, y, left)
        c.setFillColor(MUTED)
        # wrap right column
        words, line, lines = right.split(), "", []
        maxw = w * (1 - col_split) - 4
        for word in words:
            trial = (line + " " + word).strip()
            if c.stringWidth(trial, "Sans", 8.2) > maxw and line:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
        for i, ln in enumerate(lines):
            c.drawString(x + w * col_split, y - i * 10.5, ln)
        y -= 10.5 * len(lines) + 4
    return y


# ---------------------------------------------------------------------------------------------


def main():
    layer_ids = load_layer_ids()
    id_to_define = {v: k for k, v in layer_ids.items()}
    layers = load_layers()
    rgb_maps, legend = load_rgb(layer_ids)
    legend_by_label = {name: hexcol for hexcol, name, _ in legend}
    combos = load_combos()
    layer_names = {k: layers[v]["name"] for k, v in layer_ids.items() if v < len(layers)}

    # How to reach each layer, from &mo / &to bindings
    reach = {0: "Default layer"}
    for src, layer in enumerate(layers):
        for pos, (beh, params) in enumerate(layer["keys"]):
            if beh not in ("mo", "to") or params[0] not in layer_ids:
                continue
            dst = layer_ids[params[0]]
            if dst == src or dst in reach:
                continue
            name = layers[dst]["name"]
            if beh == "mo" and src == 0:
                reach[dst] = f"Hold the {name} thumb key"
            elif beh == "mo":
                reach[dst] = f"Hold {layers[src]['name']}, then also hold {name}"
            else:
                reach[dst] = f"From {layers[src]['name']}, tap → {name}  ·  stays on until → BASE"

    W, H = landscape(A4)
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle("MaizeGlow keymap cheat sheet")
    c.setAuthor("MaizeGlow")
    content_w = W - 56
    pages = [[0, 1, 2], [3, 4, 5], [6]]

    for pnum, page_layers in enumerate(pages, 1):
        header(c, W, H, pnum, len(pages))
        y = H - 58
        for idx in page_layers:
            y = draw_layer(c, 28, y, content_w, layers[idx], idx, rgb_maps.get(idx),
                           reach.get(idx, ""), layer_names, legend_by_label) - 14
        if pnum == len(pages):
            # reference panels
            col_w = (content_w - 2 * 24) / 3
            top = y - 4
            x1, x2, x3 = 28, 28 + col_w + 24, 28 + 2 * (col_w + 24)

            rows = []
            for binding, positions, only in combos:
                src_layer = only[0] if only else 0
                keys = " + ".join(label(*layers[src_layer]["keys"][p], layer_names)[0].replace("\n", " ")
                                  for p in positions)
                beh = parse_bindings(binding)[0]
                if beh[0] in MACROS:
                    what = MACROS[beh[0]][1]
                else:
                    what = label(*beh, layer_names)[0].replace("\n", " ")
                    if beh[0] == "bt" and beh[1][0] == "BT_CLR":
                        what = "Clear the current Bluetooth profile's pairing"
                where = "any layer" if not only else "on " + ", ".join(layers[l]["name"] for l in only)
                rows.append((keys, f"{what}  ({where})"))
            yb = panel(c, x1, top, col_w, "Combos  (press together, within 50 ms)", rows, 0.3)

            used = {b for l in layers for b, _ in l["keys"]} | {
                parse_bindings(b)[0][0] for b, _, _ in combos}
            rows = [(MACROS[m][0].replace("\n", " "), MACROS[m][1]) for m in MACROS if m in used]
            panel(c, x2, top, col_w, "Macro keys", rows, 0.26)

            rows = [
                ("Layer keys", "Hold keys work while held; → keys switch and stay until → BASE"),
                ("Idle", "LEDs dim to 25% after 1 min on USB, turn off on battery"),
                ("RGB keys", "PLAYER layer: next/prev effect, on/off. The effect shows for 5 s, "
                             "then the layer colours return"),
                ("Effects", "Solid, breathe, spectrum, swirl, then “layer colours only” (dark BASE)"),
                ("BASE LEDs", "Show the selected effect; other layers light their keys by group"),
            ]
            yg = panel(c, x3, top, col_w, "Good to know", rows, 0.26)

            # Full colour key, in two columns across the first two panels' width
            ky = min(yb, yg) - 18
            c.setFont("Sans-Bold", 10.5)
            c.setFillColor(INK)
            c.drawString(x1, ky, "Key colours  (the LEDs use the same colours when a layer is active)")
            c.setStrokeColor(RULE)
            c.setLineWidth(0.6)
            c.line(x1, ky - 4, 28 + content_w, ky - 4)
            entries = [(h, n, d) for h, n, d in legend if n != "black"]
            per_col = (len(entries) + 2) // 3
            for i, (hexcol, name, desc) in enumerate(entries):
                cx = 28 + (i // per_col) * (col_w + 24)
                cy = ky - 22 - (i % per_col) * 22
                draw_key(c, cx, cy - 3, 22, 13, "", "", hexcol)
                c.setFont("Sans-Bold", 8.2)
                c.setFillColor(INK)
                c.drawString(cx + 30, cy, GROUP_NAMES.get(name, name))
                c.setFont("Sans", 8.2)
                c.setFillColor(MUTED)
                maxw, words, lines, line = col_w - 30 - 78 - 6, desc.split(), [], ""
                for word in words:
                    trial = (line + " " + word).strip()
                    if c.stringWidth(trial, "Sans", 8.2) > maxw and line:
                        lines.append(line)
                        line = word
                    else:
                        line = trial
                lines.append(line)
                for j, ln in enumerate(lines):
                    c.drawString(cx + 30 + 78, cy - j * 9.5, ln)
        legend_strip(c, W, legend)
        c.showPage()
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
