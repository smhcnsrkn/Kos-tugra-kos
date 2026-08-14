# -*- coding: utf-8 -*-
"""
Kosu Oyunu (Subway Surfers tarzi) - 3 seritli, perspektifli, 6 kareli gercek kosu animasyonlu
Python + Kivy | Pydroid 3 / Android uyumlu
main.py ile AYNI klasorde run_1.png ... run_6.png dosyalari olmalidir.

Kontroller:
  - Sola/saga kaydir  -> serit degistir
  - Yukari kaydir      -> zipla (kutu engelini gecmek icin)
  - Asagi kaydir       -> kay (bariyer engelini gecmek icin)
"""

import math
import random

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Ellipse, Line, Mesh, PushMatrix, PopMatrix, Rotate
from kivy.clock import Clock

# ---------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------
SPLASH_FRAME_COUNT = 42
SPLASH_FPS = 15.0
SPLASH_HOLD_SECONDS = 0.7
SPLASH_BG_COLOR = (0.043, 0.055, 0.098, 1)

LANE_COUNT = 3

BASE_SPEED = 420.0
MAX_SPEED = 1150.0
SPEED_RAMP = 6.0

JUMP_DURATION = 0.55
JUMP_HEIGHT_RATIO = 0.24
SLIDE_DURATION = 0.55

OBSTACLE_MIN_GAP = 0.9
OBSTACLE_MAX_GAP = 1.6
COIN_CHANCE = 0.55

CRATE_COLOR = (0.75, 0.42, 0.15, 1)
BEAM_COLOR = (0.78, 0.15, 0.15, 1)
COIN_COLOR = (1.0, 0.85, 0.15, 1)

ROAD_COLOR = (0.16, 0.16, 0.19, 1)
LANE_LINE_COLOR = (0.55, 0.55, 0.62, 1)
SKY_TOP_COLOR = (0.35, 0.45, 0.65, 1)
SKY_HORIZON_COLOR = (0.72, 0.78, 0.85, 1)
BUILDING_COLOR = (0.22, 0.25, 0.34, 1)
SHADOW_COLOR = (0, 0, 0, 1)

# --- kosu animasyonu (gercek kareler) ---
FRAME_COUNT = 6
FRAME_PATHS = ["run_{}.png".format(i) for i in range(1, FRAME_COUNT + 1)]
FRAME_ASPECT = 466.0 / 460.0     # genislik / yukseklik (run_N.png dosyalarinin orani)

BOB_AMPLITUDE_RATIO = 0.018       # kareler zaten hareket gosterdigi icin hafif tutuldu
TILT_MAX_DEG = 3.5
RUN_CYCLE_BASE = 7.5
DUST_COLOR = (0.55, 0.55, 0.55, 1)

# --- perspektif ayarlari ---
HORIZON_RATIO = 0.80
ROAD_BOTTOM_MARGIN = 0.04
ROAD_TOP_HALF_RATIO = 0.09
MIN_DISTANCE_SCALE = 0.22
PERSPECTIVE_EASE_POWER = 2.3   # nesnelerin uzakta yavas, yakinda hizli gelmesini saglar
OBSTACLE_SHADOW_COLOR = (0, 0, 0, 1)


def lerp(a, b, t):
    return a + (b - a) * t


class SplashScreen(Widget):
    """Acilis animasyonu: logo kareleri sirayla oynatilir, sonra oyuna gecilir."""

    def __init__(self, on_finish, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)
        self.on_finish = on_finish
        self.frame_idx = 0
        self.finished = False
        self._timer = 0.0

        self.logo_img = Image(
            source="splash_1.png",
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
        )
        self.add_widget(self.logo_img)

        self.bind(size=self._layout, pos=self._layout)
        Clock.schedule_once(self._layout, 0)
        Clock.schedule_interval(self._advance, 1.0 / SPLASH_FPS)

    def _layout(self, *args):
        if self.width <= 0 or self.height <= 0:
            return
        side = min(self.width, self.height) * 0.72
        self.logo_img.size = (side, side)
        self.logo_img.pos = (self.center_x - side / 2.0, self.center_y - side / 2.0)

    def _advance(self, dt):
        if self.finished:
            return False

        if self.frame_idx < SPLASH_FRAME_COUNT - 1:
            self.frame_idx += 1
            self.logo_img.source = "splash_{}.png".format(self.frame_idx + 1)
            return True

        # son karedeyiz - kisa sure bekleyip oyuna gec
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
        # ekrana dokununca acilisi atla
        if not self.finished:
            self._finish()
        return True

    def redraw_background(self):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*SPLASH_BG_COLOR)
            Rectangle(pos=(0, 0), size=(self.width, self.height))


class RootWidget(Widget):
    """Once acilis animasyonunu, ardindan oyunu gosteren kok widget."""

    def __init__(self, **kwargs):
        super(RootWidget, self).__init__(**kwargs)
        self.splash = SplashScreen(on_finish=self.start_game)
        self.splash.size = self.size
        self.splash.pos = self.pos
        self.add_widget(self.splash)
        self.bind(size=self._sync_splash_geometry, pos=self._sync_splash_geometry)
        Clock.schedule_interval(self._draw_splash_bg, 1.0 / 30.0)

    def _sync_splash_geometry(self, *args):
        if self.splash and self.splash.parent:
            self.splash.size = self.size
            self.splash.pos = self.pos

    def _draw_splash_bg(self, dt):
        if self.splash and self.splash.parent:
            self.splash.redraw_background()
            return True
        return False

    def start_game(self):
        if self.splash and self.splash.parent:
            self.remove_widget(self.splash)
        game = GameWidget()
        game.size = self.size
        game.pos = self.pos
        self.add_widget(game)
        self.bind(size=lambda inst, val: setattr(game, "size", val))
        self.bind(pos=lambda inst, val: setattr(game, "pos", val))


class GameWidget(Widget):
    def __init__(self, **kwargs):
        super(GameWidget, self).__init__(**kwargs)

        self.state = "playing"
        self._ready = False

        self.player_lane = 1
        self.player_x = 0.0
        self.player_y = 0.0

        self.jumping = False
        self.jump_t = 0.0
        self.sliding = False
        self.slide_t = 0.0

        self.speed = BASE_SPEED
        self.elapsed = 0.0
        self.score = 0.0
        self.high_score = 0

        self.obstacles = []
        self.coins = []
        self.spawn_timer = 0.0
        self.road_scroll = 0.0

        self.run_cycle = 0.0
        self.current_frame_idx = 0
        self.dust = []
        self.dust_timer = 0.0

        self.char_w = 60.0
        self.char_h = 100.0

        self.horizon_y = 0.0
        self.vp_x = 0.0
        self.road_bl = 0.0
        self.road_br = 0.0
        self.road_tl = 0.0
        self.road_tr = 0.0

        self.buildings = []

        # --- karakter gorseli (6 kareli kosu animasyonu) ---
        self.char_img = Image(
            source=FRAME_PATHS[0],
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
        )
        self.add_widget(self.char_img)

        with self.char_img.canvas.before:
            PushMatrix()
            self.char_rotate = Rotate(angle=0, origin=(0, 0), axis=(0, 0, 1))
        with self.char_img.canvas.after:
            PopMatrix()

        # --- skor / mesaj etiketleri ---
        self.score_label = Label(
            text="0", font_size="26sp", bold=True, color=(1, 1, 1, 1),
            size_hint=(None, None), size=(220, 44), halign="left", valign="middle"
        )
        self.score_label.bind(size=self.score_label.setter("text_size"))
        self.add_widget(self.score_label)

        self.gameover_label = Label(
            text="", font_size="56sp", bold=True, color=(1, 0.15, 0.15, 1),
            size_hint=(None, None), size=(620, 130),
            halign="center", valign="middle"
        )
        self.gameover_label.bind(size=self.gameover_label.setter("text_size"))
        self.add_widget(self.gameover_label)

        self.score_final_label = Label(
            text="", font_size="24sp", color=(1, 1, 1, 1),
            size_hint=(None, None), size=(500, 44),
            halign="center", valign="middle"
        )
        self.score_final_label.bind(size=self.score_final_label.setter("text_size"))
        self.add_widget(self.score_final_label)

        self.restart_label = Label(
            text="", font_size="18sp", color=(0.85, 0.85, 0.85, 1),
            size_hint=(None, None), size=(500, 40),
            halign="center", valign="middle"
        )
        self.restart_label.bind(size=self.restart_label.setter("text_size"))
        self.add_widget(self.restart_label)

        self.bind(size=self._on_size_change, pos=self._on_size_change)
        Clock.schedule_once(self._init_after_layout, 0)
        Clock.schedule_interval(self.update, 1.0 / 60.0)

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
        self.char_w = self.width * 0.17
        self.char_h = self.char_w / FRAME_ASPECT
        self.player_y = self.height * 0.14
        self.char_img.size = (self.char_w, self.char_h)

        self.horizon_y = self.height * HORIZON_RATIO
        self.vp_x = self.width * 0.5
        self.road_bl = self.width * ROAD_BOTTOM_MARGIN
        self.road_br = self.width * (1.0 - ROAD_BOTTOM_MARGIN)
        self.road_tl = self.vp_x - self.width * ROAD_TOP_HALF_RATIO
        self.road_tr = self.vp_x + self.width * ROAD_TOP_HALF_RATIO

        self.player_x = self.lane_center_x(self.player_lane, self.player_y)

        rnd = random.Random(42)
        self.buildings = []
        x = -self.width * 0.2
        while x < self.width * 1.4:
            w = rnd.uniform(self.width * 0.05, self.width * 0.11)
            h = rnd.uniform(self.height * 0.05, self.height * 0.16)
            self.buildings.append({"x": x, "w": w, "h": h})
            x += w + rnd.uniform(self.width * 0.01, self.width * 0.04)

    def road_bounds(self, y):
        t = max(0.0, min(1.0, y / self.horizon_y)) if self.horizon_y > 0 else 0.0
        left = lerp(self.road_bl, self.road_tl, t)
        right = lerp(self.road_br, self.road_tr, t)
        return left, right

    def lane_center_x(self, lane_index, y):
        left, right = self.road_bounds(y)
        frac = (lane_index + 1) / (LANE_COUNT + 1)
        return left + frac * (right - left)

    def perspective_y(self, t):
        # t: 1.0 = ufukta (uzak/yeni dogan), 0.0 = oyuncunun hizasinda (yakin)
        t = max(0.0, min(1.2, t))
        eased = 1.0 - (max(0.0, 1.0 - t)) ** PERSPECTIVE_EASE_POWER
        return self.player_y + (self.horizon_y - self.player_y) * eased

    def distance_scale(self, y):
        t = max(0.0, min(1.0, y / self.horizon_y)) if self.horizon_y > 0 else 0.0
        return lerp(1.0, MIN_DISTANCE_SCALE, t)

    # -------------------------------------------------------
    # OYUNU SIFIRLA
    # -------------------------------------------------------
    def reset_game(self):
        self.state = "playing"
        self.player_lane = 1
        self.player_x = self.lane_center_x(1, self.player_y)
        self.jumping = False
        self.jump_t = 0.0
        self.sliding = False
        self.slide_t = 0.0
        self.speed = BASE_SPEED
        self.elapsed = 0.0
        self.score = 0.0
        self.obstacles = []
        self.coins = []
        self.spawn_timer = 1.0
        self.road_scroll = 0.0
        self.run_cycle = 0.0
        self.current_frame_idx = 0
        self.char_img.source = FRAME_PATHS[0]
        self.dust = []
        self.dust_timer = 0.0
        self.gameover_label.text = ""
        self.score_final_label.text = ""
        self.restart_label.text = ""

    # -------------------------------------------------------
    # DOKUNMA / KAYDIRMA
    # -------------------------------------------------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super(GameWidget, self).on_touch_down(touch)
        touch.ud["start_pos"] = touch.pos
        return True

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return super(GameWidget, self).on_touch_up(touch)

        if self.state == "gameover":
            self.reset_game()
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

    def start_slide(self):
        if not self.sliding and not self.jumping:
            self.sliding = True
            self.slide_t = 0.0

    # -------------------------------------------------------
    # ANA DONGU
    # -------------------------------------------------------
    def update(self, dt):
        if not self._ready:
            return

        if self.state == "playing":
            self._update_playing(dt)

        self._update_labels()
        self.redraw()

    def _update_playing(self, dt):
        self.elapsed += dt
        self.speed = min(BASE_SPEED + self.elapsed * SPEED_RAMP * 10, MAX_SPEED)
        self.score += self.speed * dt * 0.02

        target_x = self.lane_center_x(self.player_lane, self.player_y)
        self.player_x += (target_x - self.player_x) * min(1.0, dt * 12.0)

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

        # kosu animasyon karesini guncelle (sadece yerde kosarken)
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
                    "age": 0.0,
                    "life": 0.32,
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
            obstacle_type = random.choice(["crate", "beam"])
            self.obstacles.append({
                "lane": lane,
                "type": obstacle_type,
                "t": 1.0,
                "y": self.horizon_y,
                "resolved": False,
            })

            if random.random() < COIN_CHANCE:
                coin_lane = random.randrange(LANE_COUNT)
                if coin_lane != lane:
                    for i in range(4):
                        self.coins.append({
                            "lane": coin_lane,
                            "t": 1.0 + i * 0.055,
                            "y": self.horizon_y,
                            "collected": False,
                        })

    def _move_and_check(self, dt):
        # t: 1.0 (ufuk) -> 0.0 (oyuncu). Sabit hizla azalir, ama gorsel y konumu
        # perspective_y() ile "uzakta yavas, yakinda hizli" egrisine cevrilir.
        span = max(1.0, self.horizon_y - self.player_y)
        t_rate = (self.speed / span) * dt

        char_band_low = self.player_y - self.char_h * 0.30
        char_band_high = self.player_y + self.char_h * 0.55

        still_obstacles = []
        for ob in self.obstacles:
            ob["t"] -= t_rate
            ob["y"] = self.perspective_y(ob["t"])
            if ob["t"] < -0.08:
                continue

            if (not ob["resolved"]) and ob["lane"] == self.player_lane:
                if char_band_low <= ob["y"] <= char_band_high:
                    avoided = False
                    if ob["type"] == "crate" and self.jumping and self.jump_t < JUMP_DURATION * 0.85:
                        avoided = True
                    if ob["type"] == "beam" and self.sliding:
                        avoided = True
                    if not avoided:
                        self.trigger_game_over()
                        return
                    ob["resolved"] = True

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
                    self.score += 15
                    continue
            still_coins.append(c)
        self.coins = still_coins

    def trigger_game_over(self):
        self.state = "gameover"
        final = int(self.score)
        if final > self.high_score:
            self.high_score = final
        self.gameover_label.text = "OYUN BITTI"
        self.score_final_label.text = "Skor: {}   En Iyi: {}".format(final, self.high_score)
        self.restart_label.text = "Tekrar baslamak icin ekrana dokun"

    # -------------------------------------------------------
    # ARAYUZ / CIZIM
    # -------------------------------------------------------
    def _update_labels(self):
        self.score_label.text = str(int(self.score))
        self.score_label.pos = (14, self.height - 50)

        self.gameover_label.pos = ((self.width - self.gameover_label.width) / 2.0,
                                    self.height / 2.0 + 10)
        self.score_final_label.pos = ((self.width - self.score_final_label.width) / 2.0,
                                       self.height / 2.0 - 50)
        self.restart_label.pos = ((self.width - self.restart_label.width) / 2.0,
                                   self.height / 2.0 - 95)

        jump_offset = 0.0
        squash = 1.0
        bob_offset = 0.0
        tilt_deg = 0.0

        if self.jumping:
            phase = self.jump_t / JUMP_DURATION
            jump_offset = math.sin(phase * math.pi) * self.height * JUMP_HEIGHT_RATIO
        if self.sliding:
            squash = 0.55

        if self.state == "playing" and not self.jumping and not self.sliding:
            bob_offset = abs(math.sin(self.run_cycle)) * self.height * BOB_AMPLITUDE_RATIO
            tilt_deg = math.sin(self.run_cycle) * TILT_MAX_DEG

        self._last_jump_offset = jump_offset

        w = self.char_w
        h = self.char_h * squash
        self.char_img.size = (w, h)
        self.char_img.pos = (self.player_x - w / 2.0, self.player_y + jump_offset + bob_offset)

        self.char_rotate.origin = self.char_img.center
        self.char_rotate.angle = tilt_deg

    def redraw(self):
        self.canvas.clear()
        with self.canvas:
            Color(*SKY_TOP_COLOR)
            Rectangle(pos=(0, self.horizon_y), size=(self.width, self.height - self.horizon_y))
            Color(*SKY_HORIZON_COLOR)
            Rectangle(pos=(0, self.horizon_y - self.height * 0.05),
                      size=(self.width, self.height * 0.05))

            Color(*BUILDING_COLOR)
            offset = (self.elapsed * 12) % (self.width * 1.6) if hasattr(self, "elapsed") else 0
            for b in self.buildings:
                bx = b["x"] - offset
                if bx + b["w"] < -self.width * 0.3:
                    bx += self.width * 1.6
                if bx < self.width * 1.3:
                    Rectangle(pos=(bx, self.horizon_y), size=(b["w"], b["h"]))

            Color(*ROAD_COLOR)
            Mesh(
                vertices=[
                    self.road_bl, 0, 0, 0,
                    self.road_br, 0, 1, 0,
                    self.road_tr, self.horizon_y, 1, 1,
                    self.road_tl, self.horizon_y, 0, 1,
                ],
                indices=[0, 1, 2, 3],
                mode="triangle_fan",
            )

            Color(*LANE_LINE_COLOR)
            for i in range(1, LANE_COUNT):
                frac = i / float(LANE_COUNT)
                bx = lerp(self.road_bl, self.road_br, frac)
                tx = lerp(self.road_tl, self.road_tr, frac)
                Line(points=[bx, 0, tx, self.horizon_y], width=1.3)

            Color(LANE_LINE_COLOR[0], LANE_LINE_COLOR[1], LANE_LINE_COLOR[2], 0.5)
            n_marks = 7
            for k in range(n_marks):
                world_t = ((k / float(n_marks)) + (self.road_scroll / 80.0) / n_marks) % 1.0
                y = world_t * self.horizon_y
                left, right = self.road_bounds(y)
                Line(points=[left, y, right, y], width=1.0)

            for d in self.dust:
                alpha = max(0.0, 1.0 - d["age"] / d["life"]) * 0.55
                Color(DUST_COLOR[0], DUST_COLOR[1], DUST_COLOR[2], alpha)
                r = 6 + (d["age"] / d["life"]) * 10
                Ellipse(pos=(d["x"] - r / 2.0, d["y"] - r / 2.0), size=(r, r))

            for ob in self.obstacles:
                lx = self.lane_center_x(ob["lane"], ob["y"])
                scale = self.distance_scale(ob["y"])
                lane_w = (self.road_bounds(ob["y"])[1] - self.road_bounds(ob["y"])[0]) / LANE_COUNT

                # yere oturmus hissi icin golge
                shadow_w = lane_w * 0.5 * scale
                shadow_h = shadow_w * 0.28
                Color(OBSTACLE_SHADOW_COLOR[0], OBSTACLE_SHADOW_COLOR[1], OBSTACLE_SHADOW_COLOR[2], 0.30)
                Ellipse(pos=(lx - shadow_w / 2.0, ob["y"] - shadow_h * 0.6), size=(shadow_w, shadow_h))

                if ob["type"] == "crate":
                    w = lane_w * 0.55 * scale
                    h = self.char_h * 0.55 * scale
                    Color(*CRATE_COLOR)
                    Rectangle(pos=(lx - w / 2.0, ob["y"] - h / 2.0), size=(w, h))
                else:
                    w = lane_w * 0.95 * scale
                    h = self.char_h * 0.22 * scale
                    Color(*BEAM_COLOR)
                    Rectangle(pos=(lx - w / 2.0, ob["y"] + self.char_h * 0.30 * scale), size=(w, h))

            Color(*COIN_COLOR)
            for c in self.coins:
                lx = self.lane_center_x(c["lane"], c["y"])
                scale = self.distance_scale(c["y"])
                r = 14 * scale
                Ellipse(pos=(lx - r, c["y"] - r), size=(r * 2, r * 2))

            jump_offset = getattr(self, "_last_jump_offset", 0.0)
            max_jump_px = self.height * JUMP_HEIGHT_RATIO
            shadow_shrink = 1.0 - min(1.0, jump_offset / max_jump_px) * 0.55
            shadow_alpha = 0.35 * shadow_shrink
            shadow_w = self.char_w * 0.55 * shadow_shrink
            shadow_h = shadow_w * 0.32
            Color(SHADOW_COLOR[0], SHADOW_COLOR[1], SHADOW_COLOR[2], shadow_alpha)
            Ellipse(pos=(self.player_x - shadow_w / 2.0, self.player_y - shadow_h * 0.5),
                    size=(shadow_w, shadow_h))

            if self.state == "gameover":
                Color(0, 0, 0, 0.6)
                Rectangle(pos=(0, 0), size=(self.width, self.height))

        for child in reversed(self.children):
            self.canvas.add(child.canvas)


class RunnerApp(App):
    def build(self):
        return RootWidget()


if __name__ == "__main__":
    RunnerApp().run()
