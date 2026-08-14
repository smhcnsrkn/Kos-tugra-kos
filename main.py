# -*- coding: utf-8 -*-
"""
TUGRA KOSUYOR - genisletilmis surum
Python + Kivy | Pydroid 3 / Android uyumlu
Ayni klasorde su dosyalar bulunmalidir:
  run_1.png ... run_6.png     (kosu animasyonu kareleri)
  splash_1.png ... splash_42.png  (acilis logo animasyonu kareleri)
  icon.png                    (uygulama simgesi - buildozer.spec tarafindan kullanilir)

Akis: SPLASH (logo animasyonu) -> MENU (dokun baslat) -> OYUN

Kontroller (oyun icinde):
  - Sola/saga kaydir  -> serit degistir
  - Yukari kaydir      -> zipla
  - Asagi kaydir       -> kay
  - Sag ust kose       -> duraklat
"""

import math
import random

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics import (Color, Rectangle, Ellipse, Line, Mesh, Triangle,
                            PushMatrix, PopMatrix, Rotate, Translate)
from kivy.clock import Clock
from kivy.core.audio import SoundLoader

# =================================================================
# GENEL SABITLER
# =================================================================
SPLASH_FRAME_COUNT = 42
SPLASH_FPS = 15.0
SPLASH_HOLD_SECONDS = 0.5
BG_DARK_COLOR = (0.043, 0.055, 0.098, 1)

LANE_COUNT = 3

BASE_SPEED = 420.0
MAX_SPEED = 1150.0
SPEED_RAMP = 6.0

JUMP_DURATION = 0.55
JUMP_HEIGHT_RATIO = 0.24
SLIDE_DURATION = 0.55
LANE_LEAN_MAX_DEG = 5.0

OBSTACLE_MIN_GAP = 0.95
OBSTACLE_MAX_GAP = 1.7
COIN_CHANCE = 0.55

GROUND_TYPES = ["bin", "barrier", "cone"]
OVERHEAD_TYPE = "beam"

BIN_BODY_COLOR = (0.30, 0.34, 0.30, 1)
BIN_LID_COLOR = (0.22, 0.26, 0.22, 1)
BIN_WHEEL_COLOR = (0.08, 0.08, 0.09, 1)
BARRIER_COLOR_A = (0.85, 0.85, 0.85, 1)
BARRIER_COLOR_B = (0.85, 0.35, 0.10, 1)
CONE_COLOR = (0.88, 0.42, 0.05, 1)
CONE_STRIPE_COLOR = (0.95, 0.95, 0.95, 1)
BEAM_COLOR = (0.78, 0.15, 0.15, 1)
COIN_COLOR = (1.0, 0.85, 0.15, 1)
COIN_GLOW_COLOR = (1.0, 0.95, 0.55, 1)

ROAD_COLOR = (0.15, 0.15, 0.18, 1)
SIDEWALK_COLOR = (0.30, 0.30, 0.33, 1)
LANE_LINE_COLOR = (0.60, 0.60, 0.66, 1)
SKY_TOP_COLOR = (0.10, 0.12, 0.22, 1)
SKY_HORIZON_COLOR = (0.30, 0.28, 0.42, 1)
BUILDING_COLOR = (0.13, 0.14, 0.20, 1)
WINDOW_COLOR = (0.95, 0.85, 0.35, 1)
SHADOW_COLOR = (0, 0, 0, 1)

BOB_AMPLITUDE_RATIO = 0.018
TILT_MAX_DEG = 3.5
RUN_CYCLE_BASE = 7.5
DUST_COLOR = (0.55, 0.55, 0.55, 1)

HORIZON_RATIO = 0.80
ROAD_BOTTOM_MARGIN = 0.04
ROAD_TOP_HALF_RATIO = 0.09
MIN_DISTANCE_SCALE = 0.22
PERSPECTIVE_EASE_POWER = 2.3

FRAME_COUNT = 6
FRAME_PATHS = ["run_{}.png".format(i) for i in range(1, FRAME_COUNT + 1)]
FRAME_ASPECT = 466.0 / 460.0

HIT_STUN_DURATION = 0.30
SHAKE_DURATION = 0.28
SHAKE_MAG_PX = 10.0
PARTICLE_COUNT = 12
PARTICLE_LIFE = 0.45
PARTICLE_COLOR = (0.95, 0.55, 0.15, 1)

# =================================================================
# SES YONETICISI
# =================================================================
FOOTSTEP_BASE_VOLUME = 0.55
MUSIC_BASE_VOLUME = 0.32

_sound_cache = {}


def _get_sound(filename):
    if filename not in _sound_cache:
        try:
            _sound_cache[filename] = SoundLoader.load(filename)
        except Exception:
            _sound_cache[filename] = None
    return _sound_cache[filename]


def play_once(filename, volume=1.0):
    snd = _get_sound(filename)
    if snd is None:
        return
    try:
        snd.stop()
        snd.volume = volume
        snd.play()
    except Exception:
        pass


def start_loop(filename, volume=1.0):
    snd = _get_sound(filename)
    if snd is None:
        return None
    try:
        snd.loop = True
        snd.volume = volume
        if snd.state != "play":
            snd.play()
    except Exception:
        pass
    return snd


def set_volume(snd, volume):
    if snd is None:
        return
    try:
        snd.volume = volume
    except Exception:
        pass


COMBO_SCORE_STEP = 0.05
COMBO_SCORE_CAP = 20


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# =================================================================
# ACILIS EKRANI (LOGO ANIMASYONU)
# =================================================================
# Kaynak videoda 18-34 arasi neredeyse hareketsiz bir "donuk" bolge vardi
# (kare farki analiziyle tespit edildi) ve 34->35 aninda cok buyuk bir
# sicrama vardi. Bu yuzden tum 42 kareyi degil, gercek hareket iceren
# kareleri + donuk bolgeden sadece birkac "kopru" kare secip oynatiyoruz.
SPLASH_SEQUENCE = (
    list(range(1, 18)) +          # ucarak giris (gercek hareket)
    [21, 25, 29, 33] +            # donuk bolgeden kisa bir kopru
    list(range(35, 43))           # aciliş/yerlesme (gercek hareket)
)


class SplashScreen(Widget):
    def __init__(self, on_finish, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)
        self.on_finish = on_finish
        self.seq_idx = 0
        self.finished = False
        self._timer = 0.0

        self.logo_img = Image(
            source="splash_{}.png".format(SPLASH_SEQUENCE[0]),
            allow_stretch=True, keep_ratio=True,
            size_hint=(None, None),
        )
        self.add_widget(self.logo_img)

        self.bind(size=self._layout, pos=self._layout)
        Clock.schedule_once(self._layout, 0)
        Clock.schedule_interval(self._advance, 1.0 / SPLASH_FPS)
        play_once("sfx_logo.ogg", volume=0.8)

    def _layout(self, *args):
        if self.width <= 0 or self.height <= 0:
            return
        side = min(self.width, self.height) * 0.72
        self.logo_img.size = (side, side)
        self.logo_img.pos = (self.center_x - side / 2.0, self.center_y - side / 2.0)

    def _advance(self, dt):
        if self.finished:
            return False
        if self.seq_idx < len(SPLASH_SEQUENCE) - 1:
            self.seq_idx += 1
            frame_num = SPLASH_SEQUENCE[self.seq_idx]
            self.logo_img.source = "splash_{}.png".format(frame_num)
            return True
        self._timer += dt
        if self._timer >= SPLASH_HOLD_SECONDS:
            self._finish()
            return False
        return True

    def _finish(self):
        if not self.finished:
            self.finished = True
            self.on_finish()

    def on_touch_down(self, touch):
        if not self.finished:
            self._finish()
        return True

    def redraw_background(self):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*BG_DARK_COLOR)
            Rectangle(pos=(0, 0), size=(self.width, self.height))


# =================================================================
# ANA MENU (DOKUN BASLAT)
# =================================================================
class MenuScreen(Widget):
    def __init__(self, on_start, **kwargs):
        super(MenuScreen, self).__init__(**kwargs)
        self.on_start = on_start
        self.elapsed = 0.0

        self.logo_img = Image(
            source="splash_{}.png".format(SPLASH_FRAME_COUNT),
            allow_stretch=True, keep_ratio=True, size_hint=(None, None),
        )
        self.add_widget(self.logo_img)

        self.hint_label = Label(
            text="DOKUNARAK BASLA", font_size="24sp", bold=True,
            color=(1, 1, 1, 1), size_hint=(None, None), size=(400, 50),
            halign="center", valign="middle",
        )
        self.hint_label.bind(size=self.hint_label.setter("text_size"))
        self.add_widget(self.hint_label)

        self.bind(size=self._layout, pos=self._layout)
        Clock.schedule_once(self._layout, 0)
        Clock.schedule_interval(self._update, 1.0 / 30.0)

    def _layout(self, *args):
        if self.width <= 0 or self.height <= 0:
            return
        side = min(self.width, self.height) * 0.62
        self.logo_img.size = (side, side)
        self.logo_img.pos = (self.center_x - side / 2.0, self.center_y - side * 0.35)
        self.hint_label.pos = (self.center_x - self.hint_label.width / 2.0,
                                self.center_y - side * 0.62)

    def _update(self, dt):
        self.elapsed += dt
        pulse = 0.55 + 0.45 * abs(math.sin(self.elapsed * 2.2))
        self.hint_label.color = (1, 1, 1, pulse)
        self.redraw_background()
        return True

    def redraw_background(self):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*BG_DARK_COLOR)
            Rectangle(pos=(0, 0), size=(self.width, self.height))

    def on_touch_down(self, touch):
        play_once("sfx_ui.ogg", volume=0.7)
        self.on_start()
        return True


# =================================================================
# OYUN
# =================================================================
class GameWidget(Widget):
    def __init__(self, **kwargs):
        super(GameWidget, self).__init__(**kwargs)

        self.state = "playing"   # playing | paused | hit_stun | gameover
        self._ready = False

        self.player_lane = 1
        self.player_x = 0.0
        self.player_y = 0.0
        self._prev_player_x = 0.0
        self.lane_lean = 0.0

        self.jumping = False
        self.jump_t = 0.0
        self.sliding = False
        self.slide_t = 0.0

        self.speed = BASE_SPEED
        self.elapsed = 0.0
        self.score = 0.0
        self.high_score = 0
        self.combo = 0
        self.best_combo = 0
        self.coins_collected = 0

        self.obstacles = []
        self.coins = []
        self.spawn_timer = 0.0
        self.road_scroll = 0.0

        self.run_cycle = 0.0
        self.current_frame_idx = 0
        self.dust = []
        self.dust_timer = 0.0
        self.particles = []

        self.shake_time = 0.0
        self.hit_stun_timer = 0.0

        self.char_w = 60.0
        self.char_h = 100.0

        self.horizon_y = 0.0
        self.vp_x = 0.0
        self.road_bl = 0.0
        self.road_br = 0.0
        self.road_tl = 0.0
        self.road_tr = 0.0
        self.pause_btn_rect = (0, 0, 0, 0)

        self.buildings = []

        # --- karakter gorseli ---
        self.char_img = Image(
            source=FRAME_PATHS[0], allow_stretch=True, keep_ratio=True,
            size_hint=(None, None),
        )
        self.add_widget(self.char_img)

        with self.char_img.canvas.before:
            PushMatrix()
            self.char_rotate = Rotate(angle=0, origin=(0, 0), axis=(0, 0, 1))
        with self.char_img.canvas.after:
            PopMatrix()

        # --- UI etiketleri ---
        self.score_label = Label(
            text="0", font_size="26sp", bold=True, color=(1, 1, 1, 1),
            size_hint=(None, None), size=(240, 44), halign="left", valign="middle"
        )
        self.score_label.bind(size=self.score_label.setter("text_size"))
        self.add_widget(self.score_label)

        self.coin_label = Label(
            text="0", font_size="22sp", bold=True, color=(1, 0.85, 0.2, 1),
            size_hint=(None, None), size=(160, 40), halign="right", valign="middle"
        )
        self.coin_label.bind(size=self.coin_label.setter("text_size"))
        self.add_widget(self.coin_label)

        self.combo_label = Label(
            text="", font_size="20sp", bold=True, color=(0.6, 1.0, 0.4, 1),
            size_hint=(None, None), size=(260, 40), halign="center", valign="middle"
        )
        self.combo_label.bind(size=self.combo_label.setter("text_size"))
        self.add_widget(self.combo_label)

        self.pause_icon_label = Label(
            text="II", font_size="20sp", bold=True, color=(1, 1, 1, 1),
            size_hint=(None, None), size=(50, 50), halign="center", valign="middle"
        )
        self.pause_icon_label.bind(size=self.pause_icon_label.setter("text_size"))
        self.add_widget(self.pause_icon_label)

        self.gameover_label = Label(
            text="", font_size="42sp", bold=True, color=(1, 1, 1, 1),
            size_hint=(None, None), size=(560, 70),
            halign="center", valign="middle"
        )
        self.gameover_label.bind(size=self.gameover_label.setter("text_size"))
        self.add_widget(self.gameover_label)

        self.score_final_label = Label(
            text="", font_size="22sp", color=(1, 1, 1, 1),
            size_hint=(None, None), size=(560, 40),
            halign="center", valign="middle"
        )
        self.score_final_label.bind(size=self.score_final_label.setter("text_size"))
        self.add_widget(self.score_final_label)

        self.stats_label = Label(
            text="", font_size="18sp", color=(0.85, 0.85, 0.9, 1),
            size_hint=(None, None), size=(560, 40),
            halign="center", valign="middle"
        )
        self.stats_label.bind(size=self.stats_label.setter("text_size"))
        self.add_widget(self.stats_label)

        self.restart_label = Label(
            text="", font_size="17sp", color=(0.8, 0.8, 0.85, 1),
            size_hint=(None, None), size=(560, 36),
            halign="center", valign="middle"
        )
        self.restart_label.bind(size=self.restart_label.setter("text_size"))
        self.add_widget(self.restart_label)

        self.pause_overlay_label = Label(
            text="", font_size="40sp", bold=True, color=(1, 1, 1, 1),
            size_hint=(None, None), size=(400, 60),
            halign="center", valign="middle"
        )
        self.pause_overlay_label.bind(size=self.pause_overlay_label.setter("text_size"))
        self.add_widget(self.pause_overlay_label)

        self.bind(size=self._on_size_change, pos=self._on_size_change)
        Clock.schedule_once(self._init_after_layout, 0)
        Clock.schedule_interval(self.update, 1.0 / 60.0)

        self.footstep_sound = start_loop("loop_footstep.ogg", volume=0.0)
        self.music_sound = start_loop("loop_music.ogg", volume=MUSIC_BASE_VOLUME)

    # -------------------------------------------------------
    # KURULUM
    # -------------------------------------------------------
    def _init_after_layout(self, dt):
        if self.width > 0 and self.height > 0:
            self._layout_metrics()
            self.reset_game()
            self._ready = True
        else:
            Clock.schedule_once(self._init_after_layout, 0)

    def _on_size_change(self, *args):
        if self.width > 0 and self.height > 0:
            self._layout_metrics()

    def _layout_metrics(self):
        self.char_w = self.width * 0.23
        self.char_h = self.char_w / FRAME_ASPECT
        self.player_y = self.height * 0.15
        self.char_img.size = (self.char_w, self.char_h)

        self.horizon_y = self.height * HORIZON_RATIO
        self.vp_x = self.width * 0.5
        self.road_bl = self.width * ROAD_BOTTOM_MARGIN
        self.road_br = self.width * (1.0 - ROAD_BOTTOM_MARGIN)
        self.road_tl = self.vp_x - self.width * ROAD_TOP_HALF_RATIO
        self.road_tr = self.vp_x + self.width * ROAD_TOP_HALF_RATIO

        self.player_x = self.lane_center_x(self.player_lane, self.player_y)
        self._prev_player_x = self.player_x

        btn_size = self.width * 0.11
        self.pause_btn_rect = (self.width - btn_size - 16, self.height - btn_size - 16,
                                btn_size, btn_size)

        rnd = random.Random(42)
        self.buildings = []
        x = -self.width * 0.2
        while x < self.width * 1.4:
            w = rnd.uniform(self.width * 0.06, self.width * 0.12)
            h = rnd.uniform(self.height * 0.06, self.height * 0.18)
            n_windows = rnd.randint(3, 7)
            windows = []
            for _ in range(n_windows):
                windows.append((rnd.uniform(0.15, 0.85), rnd.uniform(0.15, 0.85)))
            self.buildings.append({"x": x, "w": w, "h": h, "windows": windows})
            x += w + rnd.uniform(self.width * 0.015, self.width * 0.045)

    def road_bounds(self, y):
        t = clamp(y / self.horizon_y, 0.0, 1.0) if self.horizon_y > 0 else 0.0
        left = lerp(self.road_bl, self.road_tl, t)
        right = lerp(self.road_br, self.road_tr, t)
        return left, right

    def sidewalk_bounds(self, y):
        t = clamp(y / self.horizon_y, 0.0, 1.0) if self.horizon_y > 0 else 0.0
        left = lerp(self.road_bl - self.width * 0.05, self.road_tl - self.width * 0.018, t)
        right = lerp(self.road_br + self.width * 0.05, self.road_tr + self.width * 0.018, t)
        return left, right

    def lane_center_x(self, lane_index, y):
        left, right = self.road_bounds(y)
        frac = (lane_index + 1) / (LANE_COUNT + 1)
        return left + frac * (right - left)

    def distance_scale(self, y):
        t = clamp(y / self.horizon_y, 0.0, 1.0) if self.horizon_y > 0 else 0.0
        return lerp(1.0, MIN_DISTANCE_SCALE, t)

    def perspective_y(self, t):
        t = clamp(t, 0.0, 1.2)
        eased = 1.0 - (max(0.0, 1.0 - t)) ** PERSPECTIVE_EASE_POWER
        return self.player_y + (self.horizon_y - self.player_y) * eased

    # -------------------------------------------------------
    # OYUNU SIFIRLA
    # -------------------------------------------------------
    def reset_game(self):
        self.state = "playing"
        self.player_lane = 1
        self.player_x = self.lane_center_x(1, self.player_y)
        self._prev_player_x = self.player_x
        self.lane_lean = 0.0
        self.jumping = False
        self.jump_t = 0.0
        self.sliding = False
        self.slide_t = 0.0
        self.speed = BASE_SPEED
        self.elapsed = 0.0
        self.score = 0.0
        self.combo = 0
        self.coins_collected = 0
        self.obstacles = []
        self.coins = []
        self.spawn_timer = 1.0
        self.road_scroll = 0.0
        self.run_cycle = 0.0
        self.current_frame_idx = 0
        self.char_img.source = FRAME_PATHS[0]
        self.dust = []
        self.dust_timer = 0.0
        self.particles = []
        self.shake_time = 0.0
        self.hit_stun_timer = 0.0
        self.gameover_label.text = ""
        self.score_final_label.text = ""
        self.stats_label.text = ""
        self.restart_label.text = ""
        self.pause_overlay_label.text = ""

    # -------------------------------------------------------
    # DOKUNMA / KAYDIRMA
    # -------------------------------------------------------
    def _point_in_rect(self, x, y, rect):
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super(GameWidget, self).on_touch_down(touch)

        if self.state in ("playing", "paused") and self._point_in_rect(
                touch.x, touch.y, self.pause_btn_rect):
            touch.ud["is_pause_btn"] = True
            return True

        touch.ud["start_pos"] = touch.pos
        return True

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return super(GameWidget, self).on_touch_up(touch)

        if touch.ud.get("is_pause_btn"):
            play_once("sfx_ui.ogg", volume=0.6)
            if self.state == "playing":
                self.state = "paused"
                self.pause_overlay_label.text = "DURAKLADI"
            elif self.state == "paused":
                self.state = "playing"
                self.pause_overlay_label.text = ""
            return True

        if self.state == "paused":
            self.state = "playing"
            self.pause_overlay_label.text = ""
            return True

        if self.state == "gameover":
            self.reset_game()
            return True

        if self.state != "playing":
            return True

        start = touch.ud.get("start_pos")
        if start is None:
            return True

        dx = touch.x - start[0]
        dy = touch.y - start[1]
        threshold = 35

        if abs(dx) > abs(dy) and abs(dx) > threshold:
            if dx > 0:
                self.change_lane(1)
            else:
                self.change_lane(-1)
        elif abs(dy) > threshold:
            if dy > 0:
                self.start_jump()
            else:
                self.start_slide()

        return True

    def change_lane(self, direction):
        new_lane = self.player_lane + direction
        if 0 <= new_lane < LANE_COUNT:
            self.player_lane = new_lane

    def start_jump(self):
        if not self.jumping and not self.sliding:
            self.jumping = True
            self.jump_t = 0.0
            play_once("sfx_jump.ogg", volume=0.8)

    def start_slide(self):
        if not self.sliding and not self.jumping:
            self.sliding = True
            self.slide_t = 0.0
            play_once("sfx_slide.ogg", volume=0.7)

    # -------------------------------------------------------
    # ANA DONGU
    # -------------------------------------------------------
    def update(self, dt):
        if not self._ready:
            return

        if self.state == "playing":
            self._update_playing(dt)
        elif self.state == "hit_stun":
            self._update_hit_stun(dt)

        if self.shake_time > 0:
            self.shake_time = max(0.0, self.shake_time - dt)

        self._update_particles(dt)
        self._update_audio()
        self._update_labels()
        self.redraw()

    def _update_audio(self):
        running_normally = (self.state == "playing" and not self.jumping and not self.sliding)
        set_volume(self.footstep_sound, FOOTSTEP_BASE_VOLUME if running_normally else 0.0)

        if self.state in ("paused", "gameover"):
            set_volume(self.music_sound, MUSIC_BASE_VOLUME * 0.35)
        else:
            set_volume(self.music_sound, MUSIC_BASE_VOLUME)

    def _update_hit_stun(self, dt):
        self.hit_stun_timer -= dt
        if self.hit_stun_timer <= 0:
            self.trigger_game_over()

    def _update_particles(self, dt):
        still = []
        for p in self.particles:
            p["age"] += dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] -= 260 * dt
            if p["age"] < p["life"]:
                still.append(p)
        self.particles = still

    def _update_playing(self, dt):
        self.elapsed += dt
        self.speed = min(BASE_SPEED + self.elapsed * SPEED_RAMP * 10, MAX_SPEED)
        self.score += self.speed * dt * 0.02

        self._prev_player_x = self.player_x
        target_x = self.lane_center_x(self.player_lane, self.player_y)
        self.player_x += (target_x - self.player_x) * min(1.0, dt * 12.0)
        dx = self.player_x - self._prev_player_x
        target_lean = clamp(dx / max(1.0, self.char_w * 0.5), -1.0, 1.0) * LANE_LEAN_MAX_DEG
        self.lane_lean += (target_lean - self.lane_lean) * min(1.0, dt * 14.0)

        if self.jumping:
            self.jump_t += dt
            if self.jump_t >= JUMP_DURATION:
                self.jumping = False
                self.jump_t = 0.0

        if self.sliding:
            self.slide_t += dt
            if self.slide_t >= SLIDE_DURATION:
                self.sliding = False
                self.slide_t = 0.0

        cycle_speed = RUN_CYCLE_BASE * (0.6 + self.speed / BASE_SPEED * 0.5)
        self.run_cycle += dt * cycle_speed

        if not self.jumping and not self.sliding:
            frame_progress = (self.run_cycle / (2.0 * math.pi)) % 1.0
            idx = int(frame_progress * FRAME_COUNT) % FRAME_COUNT
            if idx != self.current_frame_idx:
                self.current_frame_idx = idx
                self.char_img.source = FRAME_PATHS[idx]

        if not self.jumping:
            self.dust_timer -= dt
            if self.dust_timer <= 0:
                self.dust_timer = max(0.07, 0.17 - self.speed / 6000.0)
                self.dust.append({
                    "x": self.player_x + random.uniform(-self.char_w * 0.18, self.char_w * 0.18),
                    "y": self.player_y - self.char_h * 0.06,
                    "age": 0.0, "life": 0.32,
                })

        still_dust = []
        for d in self.dust:
            d["age"] += dt
            d["y"] -= dt * 40
            if d["age"] < d["life"]:
                still_dust.append(d)
        self.dust = still_dust

        self.road_scroll = (self.road_scroll + self.speed * dt) % 80.0

        self._spawn_logic(dt)
        self._move_and_check(dt)

    def _spawn_logic(self, dt):
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            gap = OBSTACLE_MAX_GAP - min(1.0, self.elapsed / 40.0) * (OBSTACLE_MAX_GAP - OBSTACLE_MIN_GAP)
            self.spawn_timer = random.uniform(max(OBSTACLE_MIN_GAP * 0.6, gap * 0.7), gap)

            lane = random.randrange(LANE_COUNT)
            roll = random.random()
            if roll < 0.30:
                obstacle_type = OVERHEAD_TYPE
            else:
                obstacle_type = random.choice(GROUND_TYPES)

            self.obstacles.append({
                "lane": lane, "type": obstacle_type, "t": 1.0,
                "y": self.horizon_y, "resolved": False,
            })

            if random.random() < COIN_CHANCE:
                coin_lane = random.randrange(LANE_COUNT)
                if coin_lane != lane:
                    pattern = random.choice(["line", "zigzag"])
                    other_lane = coin_lane + (1 if coin_lane == 0 else -1)
                    other_lane = clamp(other_lane, 0, LANE_COUNT - 1)
                    if other_lane == lane:
                        pattern = "line"
                    for i in range(4):
                        use_lane = coin_lane
                        if pattern == "zigzag" and i % 2 == 1:
                            use_lane = other_lane
                        self.coins.append({
                            "lane": use_lane, "t": 1.0 + i * 0.055,
                            "y": self.horizon_y, "collected": False,
                        })

    def _spawn_particles(self, x, y):
        for _ in range(PARTICLE_COUNT):
            ang = random.uniform(0, math.pi * 2)
            spd = random.uniform(90, 240)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(ang) * spd, "vy": math.sin(ang) * spd * 0.6 + 60,
                "age": 0.0, "life": PARTICLE_LIFE,
            })

    def _move_and_check(self, dt):
        span = max(1.0, self.horizon_y - self.player_y)
        t_rate = (self.speed / span) * dt

        char_band_low = self.player_y - self.char_h * 0.30
        char_band_high = self.player_y + self.char_h * 0.55

        still_obstacles = []
        for ob in self.obstacles:
            ob["t"] -= t_rate
            ob["y"] = self.perspective_y(ob["t"])
            if ob["t"] < -0.08:
                if not ob["resolved"]:
                    self.combo += 1
                    self.best_combo = max(self.best_combo, self.combo)
                continue

            if (not ob["resolved"]) and ob["lane"] == self.player_lane:
                if char_band_low <= ob["y"] <= char_band_high:
                    avoided = False
                    if ob["type"] in GROUND_TYPES and self.jumping and self.jump_t < JUMP_DURATION * 0.85:
                        avoided = True
                    if ob["type"] == OVERHEAD_TYPE and self.sliding:
                        avoided = True
                    if not avoided:
                        self.trigger_hit()
                        return
                    ob["resolved"] = True
                    self.combo += 1
                    self.best_combo = max(self.best_combo, self.combo)

            still_obstacles.append(ob)
        self.obstacles = still_obstacles

        still_coins = []
        for c in self.coins:
            c["t"] -= t_rate
            c["y"] = self.perspective_y(c["t"])
            if c["t"] < -0.08:
                continue
            if (not c["collected"]) and c["lane"] == self.player_lane:
                if char_band_low - 20 <= c["y"] <= char_band_high + 20:
                    c["collected"] = True
                    self.coins_collected += 1
                    mult = 1.0 + min(self.combo, COMBO_SCORE_CAP) * COMBO_SCORE_STEP
                    self.score += 15 * mult
                    play_once("sfx_coin.ogg", volume=0.9)
                    continue
            still_coins.append(c)
        self.coins = still_coins

    def trigger_hit(self):
        self.state = "hit_stun"
        self.hit_stun_timer = HIT_STUN_DURATION
        self.shake_time = SHAKE_DURATION
        self.combo = 0
        self._spawn_particles(self.player_x, self.player_y + self.char_h * 0.35)
        play_once("sfx_hit.ogg", volume=1.0)

    def trigger_game_over(self):
        self.state = "gameover"
        final = int(self.score)
        if final > self.high_score:
            self.high_score = final
        self.gameover_label.text = "OYUN BITTI"
        self.score_final_label.text = "Skor: {}   En Iyi: {}".format(final, self.high_score)
        self.stats_label.text = "Para: {}    En Iyi Kombo: {}".format(
            self.coins_collected, self.best_combo)
        self.restart_label.text = "Tekrar baslamak icin ekrana dokun"
        play_once("sfx_ui.ogg", volume=0.7)

    # -------------------------------------------------------
    # ARAYUZ
    # -------------------------------------------------------
    def _update_labels(self):
        self.score_label.text = str(int(self.score))
        self.score_label.pos = (16, self.height - 52)

        self.coin_label.text = "{} PARA".format(self.coins_collected)
        self.coin_label.pos = (self.width - self.coin_label.width - 90, self.height - 50)

        if self.combo >= 3 and self.state == "playing":
            self.combo_label.text = "KOMBO x{}".format(self.combo)
        else:
            self.combo_label.text = ""
        self.combo_label.pos = (self.width / 2.0 - self.combo_label.width / 2.0,
                                 self.height - 52)

        btn_x, btn_y, btn_w, btn_h = self.pause_btn_rect
        self.pause_icon_label.pos = (btn_x + btn_w / 2.0 - self.pause_icon_label.width / 2.0,
                                      btn_y + btn_h / 2.0 - self.pause_icon_label.height / 2.0)

        panel_cx = self.width / 2.0
        panel_cy = self.height / 2.0
        self.gameover_label.pos = (panel_cx - self.gameover_label.width / 2.0, panel_cy + 55)
        self.score_final_label.pos = (panel_cx - self.score_final_label.width / 2.0, panel_cy + 10)
        self.stats_label.pos = (panel_cx - self.stats_label.width / 2.0, panel_cy - 22)
        self.restart_label.pos = (panel_cx - self.restart_label.width / 2.0, panel_cy - 70)

        self.pause_overlay_label.pos = (panel_cx - self.pause_overlay_label.width / 2.0,
                                         panel_cy)

        jump_offset = 0.0
        squash = 1.0
        bob_offset = 0.0
        tilt_deg = 0.0

        if self.jumping:
            phase = self.jump_t / JUMP_DURATION
            jump_offset = math.sin(phase * math.pi) * self.height * JUMP_HEIGHT_RATIO
            squash = self._jump_squash(phase)
        if self.sliding:
            squash = 0.55

        if self.state == "playing" and not self.jumping and not self.sliding:
            bob_offset = abs(math.sin(self.run_cycle)) * self.height * BOB_AMPLITUDE_RATIO
            tilt_deg = math.sin(self.run_cycle) * TILT_MAX_DEG

        tilt_deg += self.lane_lean
        self._last_jump_offset = jump_offset

        w = self.char_w
        h = self.char_h * squash
        self.char_img.size = (w, h)
        self.char_img.pos = (self.player_x - w / 2.0, self.player_y + jump_offset + bob_offset)

        self.char_rotate.origin = self.char_img.center
        self.char_rotate.angle = tilt_deg

    def _jump_squash(self, t):
        if t < 0.08:
            return lerp(1.0, 0.80, t / 0.08)
        if t < 0.18:
            return lerp(0.80, 1.08, (t - 0.08) / 0.10)
        if t < 0.82:
            return 1.05
        if t < 1.0:
            return lerp(1.05, 0.85, (t - 0.82) / 0.18)
        return 1.0

    # -------------------------------------------------------
    # CIZIM
    # -------------------------------------------------------
    def redraw(self):
        self.canvas.clear()

        shake_x = 0.0
        shake_y = 0.0
        if self.shake_time > 0:
            mag = SHAKE_MAG_PX * (self.shake_time / SHAKE_DURATION)
            shake_x = random.uniform(-mag, mag)
            shake_y = random.uniform(-mag, mag)

        with self.canvas:
            PushMatrix()
            Translate(shake_x, shake_y)

            self._draw_sky()
            self._draw_buildings()
            self._draw_sidewalk_and_road()
            self._draw_lane_lines()
            self._draw_distance_marks()
            self._draw_dust()
            self._draw_obstacles()
            self._draw_coins()
            self._draw_particles()
            self._draw_shadow()

            PopMatrix()

            if self.state == "paused":
                Color(0, 0, 0, 0.55)
                Rectangle(pos=(0, 0), size=(self.width, self.height))
            if self.state == "gameover":
                self._draw_gameover_panel()

            self._draw_pause_button()

        for child in reversed(self.children):
            self.canvas.add(child.canvas)

    def _draw_sky(self):
        Color(*SKY_TOP_COLOR)
        Rectangle(pos=(0, self.horizon_y), size=(self.width, self.height - self.horizon_y))
        Color(*SKY_HORIZON_COLOR)
        Rectangle(pos=(0, self.horizon_y - self.height * 0.05),
                  size=(self.width, self.height * 0.05))

    def _draw_buildings(self):
        Color(*BUILDING_COLOR)
        offset = (self.elapsed * 12) % (self.width * 1.6) if hasattr(self, "elapsed") else 0
        for b in self.buildings:
            bx = b["x"] - offset
            if bx + b["w"] < -self.width * 0.3:
                bx += self.width * 1.6
            if bx < self.width * 1.3:
                Color(*BUILDING_COLOR)
                Rectangle(pos=(bx, self.horizon_y), size=(b["w"], b["h"]))
                Color(*WINDOW_COLOR)
                for wx_frac, wy_frac in b["windows"]:
                    wx = bx + wx_frac * b["w"]
                    wy = self.horizon_y + wy_frac * b["h"]
                    wsize = max(2, b["w"] * 0.06)
                    Rectangle(pos=(wx, wy), size=(wsize, wsize))

    def _draw_sidewalk_and_road(self):
        sw_bl, sw_br = self.sidewalk_bounds(0)
        sw_tl, sw_tr = self.sidewalk_bounds(self.horizon_y)
        Color(*SIDEWALK_COLOR)
        Mesh(
            vertices=[sw_bl, 0, 0, 0, sw_br, 0, 1, 0,
                      sw_tr, self.horizon_y, 1, 1, sw_tl, self.horizon_y, 0, 1],
            indices=[0, 1, 2, 3], mode="triangle_fan",
        )
        Color(*ROAD_COLOR)
        Mesh(
            vertices=[self.road_bl, 0, 0, 0, self.road_br, 0, 1, 0,
                      self.road_tr, self.horizon_y, 1, 1, self.road_tl, self.horizon_y, 0, 1],
            indices=[0, 1, 2, 3], mode="triangle_fan",
        )

    def _draw_lane_lines(self):
        Color(*LANE_LINE_COLOR)
        for i in range(1, LANE_COUNT):
            frac = i / float(LANE_COUNT)
            bx = lerp(self.road_bl, self.road_br, frac)
            tx = lerp(self.road_tl, self.road_tr, frac)
            Line(points=[bx, 0, tx, self.horizon_y], width=1.3)

    def _draw_distance_marks(self):
        Color(LANE_LINE_COLOR[0], LANE_LINE_COLOR[1], LANE_LINE_COLOR[2], 0.5)
        n_marks = 7
        for k in range(n_marks):
            world_t = ((k / float(n_marks)) + (self.road_scroll / 80.0) / n_marks) % 1.0
            y = world_t * self.horizon_y
            left, right = self.road_bounds(y)
            Line(points=[left, y, right, y], width=1.0)

    def _draw_dust(self):
        for d in self.dust:
            alpha = max(0.0, 1.0 - d["age"] / d["life"]) * 0.55
            Color(DUST_COLOR[0], DUST_COLOR[1], DUST_COLOR[2], alpha)
            r = 6 + (d["age"] / d["life"]) * 10
            Ellipse(pos=(d["x"] - r / 2.0, d["y"] - r / 2.0), size=(r, r))

    def _draw_ground_shadow(self, lx, y, w):
        h = w * 0.28
        Color(0, 0, 0, 0.30)
        Ellipse(pos=(lx - w / 2.0, y - h * 0.6), size=(w, h))

    def _draw_obstacles(self):
        for ob in self.obstacles:
            lx = self.lane_center_x(ob["lane"], ob["y"])
            scale = self.distance_scale(ob["y"])
            lane_w = (self.road_bounds(ob["y"])[1] - self.road_bounds(ob["y"])[0]) / LANE_COUNT

            if ob["type"] == "bin":
                self._draw_ground_shadow(lx, ob["y"], lane_w * 0.5 * scale)
                bw = lane_w * 0.42 * scale
                bh = self.char_h * 0.5 * scale
                Color(*BIN_BODY_COLOR)
                Rectangle(pos=(lx - bw / 2.0, ob["y"] - bh * 0.45), size=(bw, bh))
                Color(*BIN_LID_COLOR)
                Rectangle(pos=(lx - bw * 0.58, ob["y"] - bh * 0.45 + bh * 0.88),
                          size=(bw * 1.16, bh * 0.16))
                Color(*BIN_WHEEL_COLOR)
                wr = bw * 0.14
                Ellipse(pos=(lx - bw * 0.35 - wr, ob["y"] - bh * 0.45 - wr * 0.6), size=(wr * 2, wr * 2))
                Ellipse(pos=(lx + bw * 0.35 - wr, ob["y"] - bh * 0.45 - wr * 0.6), size=(wr * 2, wr * 2))

            elif ob["type"] == "barrier":
                self._draw_ground_shadow(lx, ob["y"], lane_w * 0.85 * scale)
                bw = lane_w * 0.82 * scale
                bh = self.char_h * 0.30 * scale
                seg = bw / 5.0
                by = ob["y"] - bh * 0.2
                for i in range(5):
                    Color(*(BARRIER_COLOR_A if i % 2 == 0 else BARRIER_COLOR_B))
                    Rectangle(pos=(lx - bw / 2.0 + i * seg, by), size=(seg, bh))

            elif ob["type"] == "cone":
                self._draw_ground_shadow(lx, ob["y"], lane_w * 0.30 * scale)
                cw = lane_w * 0.30 * scale
                ch = self.char_h * 0.42 * scale
                base_y = ob["y"] - ch * 0.25
                Color(*CONE_COLOR)
                Triangle(points=[
                    lx, base_y + ch,
                    lx - cw / 2.0, base_y,
                    lx + cw / 2.0, base_y,
                ])
                Color(*CONE_STRIPE_COLOR)
                Rectangle(pos=(lx - cw * 0.32, base_y + ch * 0.32), size=(cw * 0.64, ch * 0.14))

            else:  # beam - havadan gecen bariyer
                w = lane_w * 0.95 * scale
                h = self.char_h * 0.22 * scale
                Color(*BEAM_COLOR)
                Rectangle(pos=(lx - w / 2.0, ob["y"] + self.char_h * 0.30 * scale), size=(w, h))

    def _draw_coins(self):
        for c in self.coins:
            lx = self.lane_center_x(c["lane"], c["y"])
            scale = self.distance_scale(c["y"])
            r = 14 * scale
            Color(COIN_GLOW_COLOR[0], COIN_GLOW_COLOR[1], COIN_GLOW_COLOR[2], 0.35)
            Ellipse(pos=(lx - r * 1.5, c["y"] - r * 1.5), size=(r * 3, r * 3))
            Color(*COIN_COLOR)
            Ellipse(pos=(lx - r, c["y"] - r), size=(r * 2, r * 2))

    def _draw_particles(self):
        for p in self.particles:
            alpha = max(0.0, 1.0 - p["age"] / p["life"])
            Color(PARTICLE_COLOR[0], PARTICLE_COLOR[1], PARTICLE_COLOR[2], alpha)
            s = 6 * (1.0 - p["age"] / p["life"]) + 2
            Rectangle(pos=(p["x"] - s / 2.0, p["y"] - s / 2.0), size=(s, s))

    def _draw_shadow(self):
        jump_offset = getattr(self, "_last_jump_offset", 0.0)
        max_jump_px = self.height * JUMP_HEIGHT_RATIO
        shadow_shrink = 1.0 - min(1.0, jump_offset / max_jump_px) * 0.55
        shadow_alpha = 0.35 * shadow_shrink
        shadow_w = self.char_w * 0.55 * shadow_shrink
        shadow_h = shadow_w * 0.32
        Color(SHADOW_COLOR[0], SHADOW_COLOR[1], SHADOW_COLOR[2], shadow_alpha)
        Ellipse(pos=(self.player_x - shadow_w / 2.0, self.player_y - shadow_h * 0.5),
                size=(shadow_w, shadow_h))

    def _draw_pause_button(self):
        if self.state not in ("playing", "paused"):
            return
        x, y, w, h = self.pause_btn_rect
        Color(0, 0, 0, 0.35)
        Rectangle(pos=(x, y), size=(w, h))
        Color(0.6, 1.0, 0.4, 0.9)
        Line(rectangle=(x, y, w, h), width=1.4)

    def _draw_gameover_panel(self):
        panel_w = self.width * 0.82
        panel_h = self.height * 0.42
        px = self.width / 2.0 - panel_w / 2.0
        py = self.height / 2.0 - panel_h / 2.0

        Color(0, 0, 0, 0.55)
        Rectangle(pos=(0, 0), size=(self.width, self.height))

        Color(BG_DARK_COLOR[0] + 0.03, BG_DARK_COLOR[1] + 0.03, BG_DARK_COLOR[2] + 0.05, 0.96)
        Rectangle(pos=(px, py), size=(panel_w, panel_h))
        Color(0.55, 1.0, 0.35, 0.9)
        Line(rectangle=(px, py, panel_w, panel_h), width=1.6)


class RootWidget(Widget):
    def __init__(self, **kwargs):
        super(RootWidget, self).__init__(**kwargs)
        self.splash = SplashScreen(on_finish=self.show_menu)
        self.splash.size = self.size
        self.splash.pos = self.pos
        self.add_widget(self.splash)
        self.bind(size=self._sync_child_geometry, pos=self._sync_child_geometry)
        self._active = self.splash
        Clock.schedule_interval(self._tick_bg, 1.0 / 30.0)

    def _sync_child_geometry(self, *args):
        if self._active and self._active.parent:
            self._active.size = self.size
            self._active.pos = self.pos

    def _tick_bg(self, dt):
        return True

    def show_menu(self):
        if self.splash and self.splash.parent:
            self.remove_widget(self.splash)
        menu = MenuScreen(on_start=self.start_game)
        menu.size = self.size
        menu.pos = self.pos
        self.add_widget(menu)
        self._active = menu

    def start_game(self):
        if self._active and self._active.parent:
            self.remove_widget(self._active)
        game = GameWidget()
        game.size = self.size
        game.pos = self.pos
        self.add_widget(game)
        self._active = game


class RunnerApp(App):
    def build(self):
        return RootWidget()


if __name__ == "__main__":
    RunnerApp().run()
