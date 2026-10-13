/* SPDX-License-Identifier: GPL-3.0-or-later
 * Alternate native scenes: Carian moonlight, Destined Death, Farum Azula.
 * Original geometry stays fixed; only light and sparse particles change.
 */

static void
erdtree_lightning_segment (struct grub_video_bitmap *frame,
                           int x1, int y1, int x2, int y2, int alpha)
{
  int i, steps = grub_abs (x2 - x1) + grub_abs (y2 - y1);
  int radius = frame->mode_info.width / 900;
  if (radius < 2) radius = 2;
  for (i = 0; i <= steps; ++i)
    {
      int x = x1 + (x2 - x1) * i / (steps ? steps : 1);
      int y = y1 + (y2 - y1) * i / (steps ? steps : 1);
      erdtree_tinted_spark (frame, x, y, radius, alpha, 255, 234, 193);
    }
}

static void
erdtree_scene_render (grub_gfxmenu_view_t view, grub_uint64_t now)
{
  struct grub_erdtree_ambient *motion = view->ambient;
  struct grub_video_bitmap *source = view->scaled_desktop_image;
  struct grub_video_bitmap *frame = motion->frame;
  int w = view->screen.width, h = view->screen.height, x0 = w / 2;
  int bpp = source->mode_info.bytes_per_pixel, variant = motion->variant;
  unsigned t = (unsigned) (now - motion->epoch), storm = t % 9300;
  int breath = 13 + erdtree_wave (t, variant == 2 ? 4200 : 7300, 0) * 11 / 16384;
  int flash = 0, reaction = 0, x, y, i;
  if (variant == 3 && storm >= 3100 && storm < 3500)
    {
      int phase = storm - 3100;
      flash = phase < 100 ? phase * 150 / 100 : (400 - phase) * 150 / 300;
    }
  if (view->motion_active && now - view->motion_changed < 360)
    reaction = (360 - (int) (now - view->motion_changed)) * 12 / 360;

  for (y = 0; y < h; ++y)
    {
      int shimmer = 6 + erdtree_wave (t, 5800, y * 180 / h) * 6 / 16384;
      const grub_uint8_t *p = (const grub_uint8_t *) source->data +
        y * source->mode_info.pitch + x0 * bpp;
      grub_uint8_t *d = (grub_uint8_t *) frame->data + y * frame->mode_info.pitch + x0 * bpp;
      for (x = x0; x < w; ++x, p += bpp, d += bpp)
        {
          int edge = x - x0 < w / 12 ? (x - x0) * 256 / (w / 12) : 256;
          int light, red, green, blue;
          if (variant == 1)
            {
              int blue_light = p[2] > p[0] ? p[2] - p[0] : 0;
              light = blue_light * (breath + shimmer + reaction) / 160 * edge / 256;
              red = p[0] + light / 2;
              green = p[1] + light * 4 / 5;
              blue = p[2] + light;
            }
          else if (variant == 2)
            {
              int crimson = p[0] > p[1] ? p[0] - p[1] : 0;
              light = crimson * (breath + shimmer + reaction) / 64 * edge / 256;
              red = p[0] + light;
              green = p[1] + light / 6;
              blue = p[2] + light / 8;
            }
          else
            {
              int sky = y < h * 55 / 100 ? (h * 55 / 100 - y) * 256 / (h * 55 / 100) : 0;
              light = (p[0] + p[1] + p[2]) / 3 *
                (breath / 2 + shimmer + reaction + flash / 7) / 256 * edge / 256 * sky / 256;
              red = p[0] + light;
              green = p[1] + light * 9 / 10;
              blue = p[2] + light * 3 / 4;
            }
          d[0] = red > 255 ? 255 : red;
          d[1] = green > 255 ? 255 : green;
          d[2] = blue > 255 ? 255 : blue;
          if (bpp == 4) d[3] = p[3];
        }
    }

  if (variant == 1)
    {
      /* Fixed constellations twinkle slowly; nearby blue dust drifts. */
      for (i = 0; i < 28; ++i)
        {
          unsigned seed = (unsigned) (i + 1) * 2654435761U;
          int px = w * (550 + (seed >> 12) % 420) / 1000;
          int py = h * (30 + (seed >> 22) % 480) / 1000;
          int alpha = 100 + erdtree_wave (t, 3000 + i * 113, i * 31) * 85 / 16384;
          int radius = (i % 5 == 0 ? 4 : 2) * w / 1920;
          if (radius < 2) radius = 2;
          erdtree_tinted_spark (frame, px, py, radius, alpha, 130, 199, 255);
        }
    }

  for (i = 0; i < (variant == 2 ? 30 : 20); ++i)
    {
      unsigned seed = (unsigned) (i + 1) * 2246822519U;
      unsigned life = 8500 + seed % 11000, age = (t + seed % life) % life;
      int fade = age < life / 2 ? age : life - age;
      int alpha = fade < 1200 ? fade * 155 / 1200 : 155;
      int px = w * (550 + (seed >> 12) % 380) / 1000 +
        erdtree_wave (t, 7300 + i * 173, i * 31) * (w / 80) / 16384;
      int py = h * 93 / 100 - (int) (age * (h * 83 / 100) / life);
      int radius = (2 + i % 2) * w / 1920;
      if (radius < 2) radius = 2;
      if (variant == 1)
        erdtree_tinted_spark (frame, px, py, radius, alpha, 118, 187, 255);
      else if (variant == 2)
        {
          erdtree_tinted_spark (frame, px, py, radius, alpha + 25, 255, 69, 46);
          erdtree_tinted_spark (frame, px - 1, py + radius, radius, alpha / 2, 255, 42, 33);
        }
      else
        {
          px += (int) (age * (w / 24) / life);
          py = h - py;
          erdtree_tinted_spark (frame, px, py, radius, alpha / 2, 209, 194, 167);
        }
    }

  if (variant == 2)
    {
      /* Thin red energy coils rise beside the blade, never warping its edge. */
      for (i = 0; i < 3; ++i)
        {
          int trail;
          unsigned age = (t + i * 2100) % 6500;
          for (trail = 0; trail < 26; ++trail)
            {
              int py = h * 82 / 100 - (int) (age * (h * 61 / 100) / 6500) + trail * h / 1600;
              int px = w * 765 / 1000 + erdtree_wave (t, 4800, py * 400 / h + i * 60) * (w / 25) / 16384;
              int edge = age < 800 ? age : age > 5700 ? 6500 - age : 800;
              int radius = w / 700;
              if (radius < 2) radius = 2;
              erdtree_tinted_spark (frame, px, py, radius, (95 - trail * 2) * edge / 800, 255, 50, 55);
            }
        }
    }

  if (flash)
    {
      static const int points[][2] = {{918,100},{901,158},{911,180},{884,230},{896,238},{872,302}};
      for (i = 0; i < 5; ++i)
        erdtree_lightning_segment (frame, w * points[i][0] / 1000, h * points[i][1] / 1000,
                                   w * points[i+1][0] / 1000, h * points[i+1][1] / 1000, flash);
      erdtree_lightning_segment (frame, w * 911 / 1000, h * 180 / 1000,
                                 w * 934 / 1000, h * 225 / 1000, flash / 2);
    }
}
