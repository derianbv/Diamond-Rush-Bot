import os
import time
import cv2
import mss
import numpy as np

# Dynamically set directory relative to this script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")

print("Starting...")
time.sleep(5)
print("5 seconds have passed!")

sct = mss.mss()
monitor = sct.monitors[1]

# Capture screen
screenshot = np.array(sct.grab(monitor))

# Select ROI for the game board
initial_x, initial_y, width, height = cv2.selectROI("Selecciona el tablero del juego", screenshot)
cv2.destroyAllWindows()
cv2.waitKey(1)

# Crop to ROI
game_board_raw = screenshot[initial_y : initial_y + height, initial_x : initial_x + width]
print("Captura de area de juego hecha con exito!", game_board_raw.shape)

# Save ROI image to file
board_path = os.path.join(SCRIPT_DIR, "captured_board.png")
cv2.imwrite(board_path, game_board_raw)

# Extract individual tiles (15 rows x 10 columns)
tiles = []
for row in range(15):
    for col in range(10):
        y1 = int(row * height / 15)
        y2 = int((row + 1) * height / 15)
        x1 = int(col * width / 10)
        x2 = int((col + 1) * width / 10)

        tile = game_board_raw[y1:y2, x1:x2]
        tiles.append(tile)

print(f"Extraído {len(tiles)} casillas.")


def load_templates(assets_dir):
    """Loads all PNG tile templates from the assets directory."""
    templates = {}
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir, exist_ok=True)
        print(f"[!] Directory '{assets_dir}' did not exist; created it.")
        return templates

    for filename in os.listdir(assets_dir):
        if filename.lower().endswith(".png"):
            name = os.path.splitext(filename)[0]
            path = os.path.join(assets_dir, filename)
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                templates[name] = img
            else:
                print(f"[!] Warning: Failed to load asset {filename}")
    return templates


def identify_grid_tiles(board_img, templates, rows=15, cols=10, match_threshold=0.65):
    """Slices board image into cells and matches each cell against loaded templates."""
    img_h, img_w = board_img.shape[:2]
    cell_h = img_h // rows
    cell_w = img_w // cols

    grid = []

    for r in range(rows):
        row_tiles = []
        for c in range(cols):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            cell = board_img[y1:y2, x1:x2]

            best_tile = "unknown"
            best_score = -1.0

            for name, template in templates.items():
                if template.ndim == 3 and template.shape[2] == 4:
                    tpl_bgr = template[:, :, :3]
                    mask = template[:, :, 3]
                else:
                    tpl_bgr = template
                    mask = None

                tpl_resized = cv2.resize(tpl_bgr, (cell_w, cell_h))
                mask_resized = cv2.resize(mask, (cell_w, cell_h)) if mask is not None else None

                if mask_resized is not None:
                    res = cv2.matchTemplate(cell, tpl_resized, cv2.TM_CCORR_NORMED, mask=mask_resized)
                else:
                    res = cv2.matchTemplate(cell, tpl_resized, cv2.TM_CCOEFF_NORMED)

                score = res[0, 0]

                if score > best_score and score >= match_threshold:
                    best_score = score
                    best_tile = name

            row_tiles.append(best_tile)
        grid.append(row_tiles)

    return grid


# Match tiles against template sprites
templates = load_templates(ASSETS_DIR)
print(f"Loaded {len(templates)} templates from {ASSETS_DIR}: {list(templates.keys())}")

if templates:
    grid = identify_grid_tiles(game_board_raw, templates, rows=15, cols=10, match_threshold=0.6)
    print("\nIdentified Grid:")
    for row_idx, row in enumerate(grid):
        print(f"Row {row_idx:02d}: {row}")
else:
    print(f"\n[!] Add your template PNGs (e.g. player.png, diamond.png) into:\n    {ASSETS_DIR}")