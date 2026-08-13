# -*- coding: utf-8 -*-
"""
Kosu Oyunu (Subway Surfers tarzi) - 3 seritli, karakter fotografli
Python + Kivy | Pydroid 3 / Android uyumlu
main.py ile AYNI klasorde "character.png" dosyasi olmalidir.

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
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.clock import Clock

# ---------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------
LANE_COUNT = 3

BASE_SPEED = 420.0          # px/sn, baslangic hizi
MAX_SPEED = 1150.0
SPEED_RAMP = 6.0            # zamanla hiz artis katsayisi

JUMP_DURATION = 0.55
JUMP_HEIGHT_RATIO = 0.24     # ekran yuksekligine oranla ziplama yuksekligi
SLIDE_DURATION = 0.55

OBSTACLE_MIN_GAP = 0.9       # saniye
OBSTACLE_MAX_GAP = 1.6
COIN_CHANCE = 0.55           # engelsiz araliklarda para cikma ihtimali

CRATE_COLOR = (0.75, 0.42, 0.15, 1)
BEAM_COLOR = (0.78, 0.15, 0.15, 1)
COIN_COLOR = (1.0, 0.85, 0.15, 1)

LANE_BG_COLOR = (0.14, 0.14, 0.17, 1)
LANE_LINE_COLOR = (0.4, 0.4, 0.46, 1)


class GameWidget(Widget):
    def __init__(self, **kwargs):
        super(GameWidget, self).__init__(**kwargs)

        self.state = "playing"          # "playing" | "gameover"
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

        self.obstacles = []             # her biri dict: lane,type,y,resolved
        self.coins = []                 # her biri dict: lane,y,collected
        self.spawn_timer = 0.0
        self.road_scroll = 0.0

        self.char_w = 60.0
        self.char_h = 100.0

        # --- karakter gorseli ---
        self.char_img = Image(
            source="character.png",
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
        )
        self.add_widget(self.char_img)

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
        self.char_w = self.width * 0.16
        self.char_h = self.char_w / (283.0 / 460.0)
        self.player_y = self.height * 0.16
        self.player_x = self.lane_x(self.player_lane)
        self.char_img.size = (self.char_w, self.char_h)

    def lane_x(self, lane_index):
        return self.width * (lane_index + 1) / (LANE_COUNT + 1)

    # -------------------------------------------------------
    # OYUNU SIFIRLA
    # -------------------------------------------------------
    def reset_game(self):
        self.state = "playing"
        self.player_lane = 1
        self.player_x = self.lane_x(1)
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

        # yatay hareket - serit merkezine yumusak gecis
        target_x = self.lane_x(self.player_lane)
        self.player_x += (target_x - self.player_x) * min(1.0, dt * 12.0)

        # ziplama
        if self.jumping:
            self.jump_t += dt
            if self.jump_t >= JUMP_DURATION:
                self.jumping = False
                self.jump_t = 0.0

        # kayma
        if self.sliding:
            self.slide_t += dt
            if self.slide_t >= SLIDE_DURATION:
                self.sliding = False
                self.slide_t = 0.0

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
                "y": self.height + 40,
                "resolved": False,
            })

            # bos seritlerden birine para dizisi koy (kolay ulasilabilir)
            if random.random() < COIN_CHANCE:
                coin_lane = random.randrange(LANE_COUNT)
                if coin_lane != lane:
                    base_y = self.height + 140
                    for i in range(4):
                        self.coins.append({
                            "lane": coin_lane,
                            "y": base_y + i * 46,
                            "collected": False,
                        })

    def _move_and_check(self, dt):
        move = self.speed * dt
        char_band_low = self.player_y - self.char_h * 0.30
        char_band_high = self.player_y + self.char_h * 0.55

        still_obstacles = []
        for ob in self.obstacles:
            ob["y"] -= move
            if ob["y"] < -80:
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
            c["y"] -= move
            if c["y"] < -40:
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

        # karakter gorseli konumu (zipla / kay animasyonu)
        jump_offset = 0.0
        squash = 1.0
        if self.jumping:
            phase = self.jump_t / JUMP_DURATION
            jump_offset = math.sin(phase * math.pi) * self.height * JUMP_HEIGHT_RATIO
        if self.sliding:
            squash = 0.55

        w = self.char_w
        h = self.char_h * squash
        self.char_img.size = (w, h)
        self.char_img.pos = (self.player_x - w / 2.0, self.player_y + jump_offset)

    def redraw(self):
        self.canvas.clear()
        with self.canvas:
            # yol zemini
            Color(*LANE_BG_COLOR)
            Rectangle(pos=(0, 0), size=(self.width, self.height))

            # serit ayrac cizgileri (hareket eden kesikli hatlar)
            Color(*LANE_LINE_COLOR)
            for i in range(1, LANE_COUNT):
                x = self.width * i / LANE_COUNT
                y = -80 + self.road_scroll
                while y < self.height:
                    Line(points=[x, y, x, y + 40], width=1.5)
                    y += 80

            # engeller
            for ob in self.obstacles:
                lx = self.lane_x(ob["lane"])
                lane_w = self.width / LANE_COUNT
                if ob["type"] == "crate":
                    w = lane_w * 0.42
                    h = self.char_h * 0.55
                    Color(*CRATE_COLOR)
                    Rectangle(pos=(lx - w / 2.0, ob["y"] - h / 2.0), size=(w, h))
                else:
                    w = lane_w * 0.78
                    h = self.char_h * 0.22
                    Color(*BEAM_COLOR)
                    Rectangle(pos=(lx - w / 2.0, ob["y"] + self.char_h * 0.30), size=(w, h))

            # paralar
            Color(*COIN_COLOR)
            for c in self.coins:
                lx = self.lane_x(c["lane"])
                r = 14
                Ellipse(pos=(lx - r, c["y"] - r), size=(r * 2, r * 2))

            # oyun bitti karartma
            if self.state == "gameover":
                Color(0, 0, 0, 0.6)
                Rectangle(pos=(0, 0), size=(self.width, self.height))

        for child in reversed(self.children):
            self.canvas.add(child.canvas)


class RunnerApp(App):
    def build(self):
        return GameWidget()


if __name__ == "__main__":
    RunnerApp().run()
