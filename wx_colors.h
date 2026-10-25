#pragma once
// ---------------------------------------------------------------------------
// Shared C++ helpers for the Lanai Dashboard.
// Included from the main YAML via:  esphome: includes: - common/wx_colors.h
//
//  * colour bands that replace the long on_value_range blocks
//  * label formatters (NaN-safe, no dangling c_str() pointers)
//  * weather icon key builder (day/night variants)
// ---------------------------------------------------------------------------
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include "esphome/components/lvgl/lvgl_esphome.h"

namespace wx {

// ---- Palette ---------------------------------------------------------------
// These four match your common/color.yaml. If the tiles look different from
// before on first boot, swap in the CSS values: crimson 0xDC143C,
// green 0x008000, white 0xFFFFFF, black 0x000000.
constexpr uint32_t kWhite = 0xF2F0EB;
constexpr uint32_t kBlack = 0x0D0D0D;
constexpr uint32_t kCrimson = 0xF5075C;
constexpr uint32_t kGreen = 0x5CA848;
// CSS named colours used by the old config
constexpr uint32_t kDarkOrange = 0xFF8C00;
constexpr uint32_t kSeaGreen = 0x3CB371;   // mediumseagreen
constexpr uint32_t kTeal = 0x008080;
constexpr uint32_t kTurquoise = 0x00CED1;  // darkturquoise
constexpr uint32_t kYellowGreen = 0x9ACD32;
constexpr uint32_t kKhaki = 0xF0E68C;

// ---- Colour bands ------------------------------------------------------------
// A band applies while value < below. The last entry is the catch-all.
struct Band {
  float below;
  uint32_t bg;
  uint32_t fg;
};

inline constexpr Band POOL[] = {
    {75.0f, kTurquoise, kWhite}, {80.0f, kTeal, kBlack},       {83.0f, kSeaGreen, kBlack},
    {85.0f, kGreen, kWhite},     {90.0f, kDarkOrange, kBlack}, {1e9f, kCrimson, kWhite}};

inline constexpr Band OUTSIDE[] = {
    {60.0f, kTurquoise, kWhite}, {70.0f, kTeal, kWhite},       {80.0f, kGreen, kWhite},
    {90.0f, kYellowGreen, kBlack}, {95.0f, kDarkOrange, kBlack}, {1e9f, kCrimson, kWhite}};

inline constexpr Band FEELS[] = {
    {70.0f, kTurquoise, kWhite},   {80.0f, kSeaGreen, kWhite},   {90.0f, kGreen, kWhite},
    {100.0f, kYellowGreen, kBlack}, {110.0f, kDarkOrange, kBlack}, {1e9f, kCrimson, kWhite}};

// Humidity <35% was white text on khaki (hard to read); now dark text.
inline constexpr Band HUMIDITY[] = {
    {35.0f, kKhaki, kBlack}, {60.0f, kGreen, kWhite}, {80.0f, kDarkOrange, kBlack}, {1e9f, kCrimson, kWhite}};

template <size_t N>
inline void paint(lv_obj_t *cell, lv_obj_t *value, lv_obj_t *label, float x, const Band (&bands)[N]) {
  if (std::isnan(x)) return;
  size_t i = 0;
  while (i < N - 1 && x >= bands[i].below) i++;
  lv_obj_set_style_bg_color(cell, lv_color_hex(bands[i].bg), 0);
  lv_obj_set_style_text_color(value, lv_color_hex(bands[i].fg), 0);
  lv_obj_set_style_text_color(label, lv_color_hex(bands[i].fg), 0);
}

// ---- Label formatters -----------------------------------------------------------
// lv_label_set_text() copies the string, so stack buffers are safe here.
inline void show(lv_obj_t *lbl, const char *text) { lv_label_set_text(lbl, text); }

inline void deg(lv_obj_t *lbl, float v) {
  if (std::isnan(v)) return show(lbl, "--");
  char b[16];
  snprintf(b, sizeof(b), "%.1f\u00B0", v);
  show(lbl, b);
}
inline void pct(lv_obj_t *lbl, float v) {
  if (std::isnan(v)) return show(lbl, "--");
  char b[16];
  snprintf(b, sizeof(b), "%.0f%%", v);
  show(lbl, b);
}
inline void inches(lv_obj_t *lbl, float v) {
  if (std::isnan(v)) return show(lbl, "--");
  char b[16];
  snprintf(b, sizeof(b), "%.2f\"", v);
  show(lbl, b);
}
// Pressure value without a unit (the trend arrow sits where "Hg used to be).
inline void fixed3(lv_obj_t *lbl, float v) {
  if (std::isnan(v)) return show(lbl, "--");
  char b[16];
  snprintf(b, sizeof(b), "%.3f", v);
  show(lbl, b);
}
inline void count(lv_obj_t *lbl, float v) {
  if (std::isnan(v)) return show(lbl, "--");
  char b[12];
  snprintf(b, sizeof(b), "%d", (int) v);
  show(lbl, b);
}
inline void num1(lv_obj_t *lbl, float v) {
  if (std::isnan(v)) return show(lbl, "--");
  char b[12];
  snprintf(b, sizeof(b), "%.1f", v);
  show(lbl, b);
}

// ---- Pool sensor battery icon (Material Design Icons glyphs) -----------------------
inline void battery(lv_obj_t *lbl, float pct_value) {
  if (std::isnan(pct_value)) return;
  const char *glyph;
  uint32_t color;
  if (pct_value > 70.0f) {
    glyph = "\U000F0081";  // battery-80
    color = 0x00FF00;
  } else if (pct_value > 40.0f) {
    glyph = "\U000F007E";  // battery-50
    color = 0x00FF00;
  } else if (pct_value > 10.0f) {
    glyph = "\U000F007C";  // battery-30
    color = 0xF7FA00;
  } else {
    glyph = "\U000F10CD";  // battery-alert-variant
    color = 0xFF0000;
  }
  lv_label_set_text(lbl, glyph);
  lv_obj_set_style_text_color(lbl, lv_color_hex(color), 0);
}

// ---- Pressure trend arrow ---------------------------------------------------------------
// rate  = pressure change per hour (from the Home Assistant Derivative helper)
// rapid = rate treated as a "rapid" rise/fall (NWS: 0.06 inHg/hr = about 2.03 hPa/hr)
// The arrow image points RIGHT at 0 degrees. LVGL angles are tenths of a degree,
// clockwise, so a rise (arrow up) is 270 degrees and a fall (arrow down) is 90.
// Angle scales linearly between steady (0) and +/-rapid (straight up/down).
inline int trend_angle(float rate, float rapid) {
  if (std::isnan(rate) || rapid <= 0.0f) return 0;
  float n = rate / rapid;
  if (n > 1.0f) n = 1.0f;
  if (n < -1.0f) n = -1.0f;
  int a = (int) std::lround(-n * 900.0f);
  if (a < 0) a += 3600;
  return a;
}

// Hide the arrow while there is no valid reading instead of pointing the wrong way.
inline void show_if_valid(lv_obj_t *obj, float v) {
  if (std::isnan(v))
    lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
  else
    lv_obj_clear_flag(obj, LV_OBJ_FLAG_HIDDEN);
}

// ---- Weather icon key -----------------------------------------------------------------
// Only these Google condition types have a distinct night icon; every other
// type uses the same icon day and night, so no *_NIGHT entry is needed.
inline std::string icon_key(const char *type, bool night) {
  std::string key(type);
  if (!night) return key;
  static const char *const NIGHT_TYPES[] = {"CLEAR",
                                            "MOSTLY_CLEAR",
                                            "MOSTLY_CLOUDY",
                                            "PARTLY_CLOUDY",
                                            "SCATTERED_SHOWERS",
                                            "SCATTERED_SNOW_SHOWERS",
                                            "ISOLATED_SCATTERED_THUNDERSTORMS"};
  for (const char *t : NIGHT_TYPES) {
    if (key == t) {
      key += "_NIGHT";
      break;
    }
  }
  return key;
}

}  // namespace wx
