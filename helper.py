import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk
import random
import math
import os
import json

# ---------------------------------------------------------
# Desktop Helper – walking sprite + little reminder bubble
#
# Notes to myself:
# - This is my first “desktop buddy” project.
# - She walks along the bottom of the screen.
# - Every so often she pops a small text bubble with a message
#   and a random emoji image from the folder.
#
# TODO (for future me):
# - Add sound effects
# - Let her react to keyboard shortcuts or time of day
#
# If I ever forget how this works, I can scroll through the
# comments below. I kept them short but clear on purpose.
# ---------------------------------------------------------

# --- basic settings / files ---

# sprite sheets (idle + walking)
IDLE_SHEET = "Idle.png"
WALK_SHEET = "Walk.png"

# small logo that shows under her feet
LOGO_FILE = "logo.png"

# each frame in the sprite sheet
FRAME_WIDTH = 128
FRAME_HEIGHT = 128

# scaling the sprite up a bit so she’s easier to see
SCALE = 1.4

# movement / animation timing
STEP_SIZE = 4           # how many pixels she moves each tick
MOVE_DELAY = 70         # ms between animation updates
FLOAT_AMPLITUDE = 5     # how much she “bobs” up and down
FLOAT_SPEED = 0.15      # speed of the bobbing

# file where I remember the user’s name
CONFIG_FILE = "helper_config.json"

# reminder timing
NOTE_INTERVAL_MS = 30000   # show a reminder every 30 seconds
NOTE_DURATION_MS = 10000   # bubble stays for 10 seconds

# fade-in/fade-out for the bubble
BUBBLE_FADE_STEPS = 10
BUBBLE_FADE_INTERVAL = 40   # ms between fade steps

# folder to scan for emoji images (emoji_*.png)
EMOJI_FOLDER = "."


class DesktopHelper:
    def __init__(self, root: tk.Tk):
        # Make the main window invisible and always on top.
        # The magenta color is used as the transparent key.
        self.root = root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="magenta")
        root.attributes("-transparentcolor", "magenta")

        # Remember the user’s name between runs (stored in JSON file).
        self.user_name = self.load_or_ask_name()

        # Load sprite frames for idle and walking.
        self.idle_right, self.idle_left = self.load_sheet(IDLE_SHEET)
        self.walk_right, self.walk_left = self.load_sheet(WALK_SHEET)

        # Load any emoji_*.png files in the folder.
        # These get picked randomly for the speech bubble.
        self.emojis = self.load_emojis()
        self.current_emoji_key = None

        # Current facing direction & frame index for animation.
        self.facing = "right"
        self.frame_index = 0

        # Start with the first idle frame (just to have something).
        self.tk_img = self.idle_right[0]
        self.label = tk.Label(
            root, image=self.tk_img, bg="magenta",
            bd=0, highlightthickness=0
        )
        self.label.pack()

        # --- footer with logo + credit text ---

        self.logo_img = None
        if os.path.exists(LOGO_FILE):
            try:
                logo = Image.open(LOGO_FILE).convert("RGBA")
                logo = logo.resize((18, 18), Image.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(logo)
            except Exception:
                # If the logo fails to load, I just skip it.
                self.logo_img = None

        self.footer = tk.Frame(root, bg="magenta", bd=0, highlightthickness=0)
        self.footer.pack(pady=(0, 0))

        if self.logo_img:
            self.logo_label = tk.Label(
                self.footer, image=self.logo_img,
                bg="magenta", bd=0, highlightthickness=0
            )
            self.logo_label.pack(side="left", padx=(0, 3))

        # Little signature under her feet.
        self.credit_label = tk.Label(
            self.footer,
            text="Creations by Kashiro",
            bg="magenta",
            fg="#ff5abf",
            font=("Segoe UI", 7),
            bd=0,
            highlightthickness=0
        )
        self.credit_label.pack(side="left")

        # Ask Tk for the actual widget size after layout.
        root.update_idletasks()
        self.width = root.winfo_width()
        self.height = root.winfo_height()

        # Get full screen size so she can walk edge to edge.
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()

        # Start her somewhere along the bottom of the screen.
        self.x = random.randint(0, self.screen_width - self.width)
        self.base_y = self.screen_height - self.height - 40
        self.y = self.base_y

        # Horizontal velocity and bobbing phase.
        self.vx = STEP_SIZE
        self.float_phase = 0.0

        # Info for the reminder bubble.
        # At some point I tried a big “cloud” bubble with circles;
        # it felt too busy, so this version is just a small rectangle.
        self.note_window = None
        self.note_canvas = None
        self.note_text_item = None
        self.note_text_content = ""
        self.bubble_w = 170
        self.bubble_h = 70

        # Fade state for the bubble.
        self.note_alpha_step = 0
        self.note_fading_out = False

        # Position the window at the start.
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        # Kick off the animation loop and reminder schedule.
        self.move()
        self.schedule_next_note()

    # -----------------------------------------------------
    # Name memory – load/save a single name in a JSON file.
    # -----------------------------------------------------
    def load_or_ask_name(self) -> str:
        # Try to load the name if the config file exists.
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    name = data.get("user_name")
                    if isinstance(name, str) and name.strip():
                        return name.strip()
            except Exception:
                # If anything goes wrong, I’ll just ask again.
                pass

        # First run (or config missing): ask what to call the user.
        name = simpledialog.askstring("Hi!", "What should I call you?")
        if not name:
            name = "friend"
        name = name.strip()

        # Save it for next time.
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"user_name": name}, f)
        except Exception:
            # If saving fails, it’s not the end of the world.
            pass

        return name

    # -----------------------------------------------------
    # Sprite sheet loading
    # -----------------------------------------------------
    def load_sheet(self, filename):
        # Each sheet is a row of frames of the same size.
        sheet = Image.open(filename).convert("RGBA")

        cols = sheet.width // FRAME_WIDTH
        frames_right = []
        frames_left = []

        target_w = int(FRAME_WIDTH * SCALE)
        target_h = int(FRAME_HEIGHT * SCALE)

        for i in range(cols):
            x0 = i * FRAME_WIDTH
            y0 = 0
            x1 = x0 + FRAME_WIDTH
            y1 = y0 + FRAME_HEIGHT

            # Cut out a single frame from the sheet.
            frame = sheet.crop((x0, y0, x1, y1))
            frame = frame.resize((target_w, target_h), Image.NEAREST)

            # Right-facing and left-facing versions of the frame.
            right = ImageTk.PhotoImage(frame)
            left = ImageTk.PhotoImage(frame.transpose(Image.FLIP_LEFT_RIGHT))

            frames_right.append(right)
            frames_left.append(left)

        return frames_right, frames_left

    # -----------------------------------------------------
    # Emoji loading – anything named emoji_*.png gets used.
    # -----------------------------------------------------
    def load_emojis(self):
        result = {}
        for filename in os.listdir(EMOJI_FOLDER):
            if filename.lower().endswith(".png") and filename.startswith("emoji_"):
                try:
                    img = Image.open(filename).convert("RGBA")
                    img = img.resize((22, 22), Image.LANCZOS)
                    key = filename.replace(".png", "").replace("emoji_", "")
                    result[key] = ImageTk.PhotoImage(img)
                except Exception:
                    # If a file fails to load, I just skip it.
                    continue
        return result

    # -----------------------------------------------------
    # Main animation loop – walking + screen edge bounce.
    # -----------------------------------------------------
    def move(self):
        # Move horizontally; bounce off left/right edges.
        self.x += self.vx
        if self.x <= 0:
            self.x = 0
            self.vx = STEP_SIZE
        elif self.x + self.width >= self.screen_width:
            self.x = self.screen_width - self.width
            self.vx = -STEP_SIZE

        # Decide which direction she is facing.
        self.facing = "right" if self.vx > 0 else "left"

        # Gentle up/down bobbing so the walk looks more alive.
        self.float_phase += FLOAT_SPEED
        self.y = self.base_y + int(FLOAT_AMPLITUDE * math.sin(self.float_phase))

        # Cycle through walking frames.
        frames = self.walk_right if self.facing == "right" else self.walk_left
        self.frame_index = (self.frame_index + 1) % len(frames)
        self.tk_img = frames[self.frame_index]
        self.label.config(image=self.tk_img)

        # Update the window position.
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        # Keep the bubble attached if it’s visible.
        if self.note_window and self.note_window.winfo_exists():
            self.position_note()

        # Schedule the next animation step.
        self.root.after(MOVE_DELAY, self.move)

    # -----------------------------------------------------
    # Reminder timing
    # -----------------------------------------------------
    def schedule_next_note(self):
        self.root.after(NOTE_INTERVAL_MS, self.show_note)

    def show_note(self):
        # Lines she can say. I can add or change these later.
        msg = random.choice([
            f"You're doing great, {self.user_name}!",
            f"Drink some water, {self.user_name}.",
            "Don't forget to stretch.",
            "Time to save your work.",
            "Posture check!"
        ])

        # Pick a random emoji image if I have any loaded.
        emoji_key = None
        if self.emojis:
            emoji_key = random.choice(list(self.emojis.keys()))

        self.note_text_content = msg
        self.current_emoji_key = emoji_key

        # Either update the existing bubble or create a new one.
        if self.note_window and self.note_window.winfo_exists():
            if self.note_canvas and self.note_text_item:
                self.note_canvas.itemconfig(self.note_text_item, text=self.note_text_content)
            self.position_note()
        else:
            self.note_window = tk.Toplevel()
            self.note_window.overrideredirect(True)
            self.note_window.attributes("-topmost", True)
            self.note_window.config(bg="magenta")
            self.note_window.attributes("-transparentcolor", "magenta")
            self.note_window.attributes("-alpha", 0.0)

            self.note_canvas = tk.Canvas(
                self.note_window,
                width=self.bubble_w,
                height=self.bubble_h,
                bg="magenta",
                highlightthickness=0,
                bd=0,
            )
            self.note_canvas.pack(fill="both", expand=True)
            self.note_canvas.bind("<Button-1>", lambda e: self.fade_out())

            self.position_note()

        # Start fading the bubble in.
        self.note_fading_out = False
        self.note_alpha_step = 0
        self.fade_in()

        # Schedule fade-out and the next reminder.
        self.root.after(NOTE_DURATION_MS, self.fade_out)
        self.schedule_next_note()

    # -----------------------------------------------------
    # Fade-in / fade-out logic for the bubble window.
    # -----------------------------------------------------
    def fade_in(self):
        if not (self.note_window and self.note_window.winfo_exists()):
            return
        if self.note_fading_out:
            return

        alpha = self.note_alpha_step / BUBBLE_FADE_STEPS
        if alpha > 1.0:
            alpha = 1.0
        self.note_window.attributes("-alpha", alpha)

        if self.note_alpha_step < BUBBLE_FADE_STEPS:
            self.note_alpha_step += 1
            self.root.after(BUBBLE_FADE_INTERVAL, self.fade_in)

    def fade_out(self):
        if not (self.note_window and self.note_window.winfo_exists()):
            return
        self.note_fading_out = True
        self._fade_out_step(BUBBLE_FADE_STEPS)

    def _fade_out_step(self, step):
        if not (self.note_window and self.note_window.winfo_exists()):
            return
        alpha = step / BUBBLE_FADE_STEPS
        if alpha < 0.0:
            alpha = 0.0
        self.note_window.attributes("-alpha", alpha)
        if step > 0:
            self.root.after(BUBBLE_FADE_INTERVAL, self._fade_out_step, step - 1)
        else:
            # Once it’s fully faded, remove the bubble window completely.
            self.note_window.destroy()
            self.note_window = None
            self.note_canvas = None
            self.note_text_item = None

    # -----------------------------------------------------
    # Drawing and positioning the small rectangle bubble.
    # -----------------------------------------------------
    def draw_bubble(self):
        if not self.note_canvas:
            return

        self.note_canvas.delete("all")

        w = self.bubble_w
        h = self.bubble_h
        fill = "#fffbe6"
        outline = "#f0c48a"

        # This used to be a cloud built with overlapping circles.
        # That felt too big and noisy, so now it’s a simple rectangle
        # with a small tail.
        margin = 4
        rect_top = 6
        rect_bottom = h - 18
        self.note_canvas.create_rectangle(
            margin, rect_top, w - margin, rect_bottom,
            fill=fill, outline=outline, width=2
        )

        # Little tail at the bottom center.
        mid_x = w // 2
        self.note_canvas.create_polygon(
            mid_x - 7, rect_bottom,
            mid_x + 7, rect_bottom,
            mid_x, h - margin,
            fill=fill, outline=outline, width=2
        )

        # Text in pink so it matches my “signature” color.
        self.note_text_item = self.note_canvas.create_text(
            w // 2 - 4,
            (rect_top + rect_bottom) // 2 - 8,
            text=self.note_text_content,
            font=("Segoe UI", 9),
            fill="#ff5abf",
            width=w - 30,
            justify="center",
        )

        # Optional emoji under the text, if one is set.
        if self.current_emoji_key and self.current_emoji_key in self.emojis:
            self.note_canvas.create_image(
                w // 2,
                rect_bottom - 3,
                image=self.emojis[self.current_emoji_key]
            )

    def position_note(self):
        if not (self.note_window and self.note_window.winfo_exists()):
            return

        margin_y = 4

        # Rough guess for where her mouth is on the sprite.
        mouth_x = self.x + int(self.width * 0.35)
        mouth_y = self.y + int(self.height * 0.35)

        # The tail tip is at the bottom center of the bubble.
        tail_x_offset = self.bubble_w // 2
        tail_y_offset = self.bubble_h - 4

        # Align tail to mouth.
        nx = mouth_x - tail_x_offset
        ny = mouth_y - tail_y_offset - margin_y

        # Make sure the bubble stays fully on screen.
        nx = max(0, min(nx, self.screen_width - self.bubble_w))
        ny = max(0, min(ny, self.screen_height - self.bubble_h))

        self.note_window.geometry(f"{self.bubble_w}x{self.bubble_h}+{nx}+{ny}")
        self.draw_bubble()


if __name__ == "__main__":
    root = tk.Tk()
    app = DesktopHelper(root)
    root.mainloop()
