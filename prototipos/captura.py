import mss
from PIL import Image
import numpy as np
import cv2
import time
import os

print("Starting...")
time.sleep(10)  # Wait 5 seconds
print("5 seconds have passed!")


# How is mss used?
# How can i use dictionaries for this?
#How do i even make dictionaries? What do i name them? it says i should use postion and size
#What is sct? screenshot abbreviation i guess


sct = mss.MSS()
monitor = sct.monitors[1]

# ex_left = 100
# ex_top = 100
# ex_right = 500
# ex_bottom = 500
# initial_x = 428
# initial_y = 0
# height = 510
# width = 666



screenshot = np.array(sct.grab(monitor))


initial_x, initial_y, width, height = cv2.selectROI("Selecciona el tablero del juego", screenshot)

cv2.destroyAllWindows()
cv2.waitKey(1)

#grayed_game_img = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

region_of_interest = {
    "top": initial_y,
    "left": initial_x,
    "height": height,
    "width":  width
    
}

tile_width = width // 10
tile_height = height // 15

game_board_raw = screenshot[initial_y : initial_y + height, initial_x : initial_x + width]
print("Captura de area de juego hecha con exito!", game_board_raw.shape)

tiles = []

for row in range(15):
    for col in range(10):
        y1 = int(row * height / 15)
        y2 = int((row + 1) * height / 15)
        
        x1 = int(col * width / 10)
        x2 = int((col + 1) * width / 10)

        tile = game_board_raw[y1: y2, x1: x2]
        #why is y first?
        tiles.append(tile)
        cv2.imwrite(f"test_tile{row}{col}.png",tile)

print(f"extraido {len(tiles)} casillas")

import os
import cv2
import numpy as np

ASSETS_DIR = "./assets"

def load_templates(assets_dir):
    """Loads all PNG tile templates from the assets directory."""
    templates = {}
    if not os.path.exists(assets_dir):
        print(f"[!] Directory '{assets_dir}' not found.")
        return templates

    for filename in os.listdir(assets_dir):
        if filename.lower().endswith(".png"):
            name = os.path.splitext(filename)[0]
            path = os.path.join(assets_dir, filename)
            # Read with alpha channel if present
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                templates[name] = img
            else:
                print(f"[!] Warning: Failed to load asset {filename}")
    return templates


def identify_grid_tiles(image_path, templates, rows=10, cols=10, match_threshold=0.65):
    """
    Slices a fixed grid board into cells and matches each cell against loaded templates.
    Falls back to 'unknown' when missing assets or low match scores occur.
    """
    board = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if board is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    img_h, img_w, _ = board.shape
    cell_h = img_h // rows
    cell_w = img_w // cols

    grid = []

    for r in range(rows):
        row_tiles = []
        for c in range(cols):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            cell = board[y1:y2, x1:x2]

            best_tile = "unknown"
            best_score = -1.0

            for name, template in templates.items():
                # Separate BGR and Alpha mask if transparency exists
                if template.ndim == 3 and template.shape[2] == 4:
                    tpl_bgr = template[:, :, :3]
                    mask = template[:, :, 3]
                else:
                    tpl_bgr = template
                    mask = None

                # Resize template to match exact cell dimensions
                tpl_resized = cv2.resize(tpl_bgr, (cell_w, cell_h))
                mask_resized = cv2.resize(mask, (cell_w, cell_h)) if mask is not None else None

                # Compare cell with template
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


def scan_unaligned_tiles(image_path, templates, threshold=0.8):
    """
    Scans the board using Template Matching to find arbitrary tile positions.
    Useful when grid coordinates are dynamic or unknown.
    """
    board = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if board is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    detections = []

    for name, template in templates.items():
        if template.ndim == 3 and template.shape[2] == 4:
            tpl_bgr = template[:, :, :3]
            mask = template[:, :, 3]
        else:
            tpl_bgr = template
            mask = None

        h, w = tpl_bgr.shape[:2]

        if mask is not None:
            res = cv2.matchTemplate(board, tpl_bgr, cv2.TM_CCORR_NORMED, mask=mask)
        else:
            res = cv2.matchTemplate(board, tpl_bgr, cv2.TM_CCOEFF_NORMED)

        loc = np.where(res >= threshold)
        for pt in zip(*loc[::-1]):
            detections.append({
                "tile": name,
                "x": int(pt[0]),
                "y": int(pt[1]),
                "width": w,
                "height": h,
                "confidence": float(res[pt[1], pt[0]])
            })

    return detections


if __name__ == "__main__":
    # Load all available sprite assets
    templates = load_templates(ASSETS_DIR)
    print(f"Loaded {len(templates)} templates: {list(templates.keys())}")

    test_image = "captured_board.png" if os.path.exists("captured_board.png") else "captura_test.png"

    if os.path.exists(test_image):
        print(f"\nTesting tile identification on '{test_image}'...")

        # Option A: Grid-based evaluation (Adjust rows/cols to match game layout)
        try:
            grid = identify_grid_tiles(test_image, templates, rows=8, cols=8, match_threshold=0.6)
            print("\nIdentified Grid:")
            for row_idx, row in enumerate(grid):
                print(f"Row {row_idx:02d}: {row}")
        except Exception as e:
            print(f"Grid detection error: {e}")

        # Option B: Scanning for arbitrary position detection
        try:
            hits = scan_unaligned_tiles(test_image, templates, threshold=0.75)
            print(f"\nFound {len(hits)} individual tile detections.")
        except Exception as e:
            print(f"Scan detection error: {e}")
    else:
        print(f"\n[!] Test image '{test_image}' not found.")


#cv2 and numpy work test
cv2.imwrite("captured_board.png", screenshot)
#cv2.imwrite("test_tile.png",tiles[0])
#What is a monitor dict, or a left,top,right,bottom tuple
#print(screenshot.size, "and", game_board.size)
#print(type(game_board))
#print(dir(game_board))

#mss.tools.to_png(game_board.rgb, game_board.size, output="captura_test.png")
