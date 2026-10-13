/* SPDX-License-Identifier: GPL-3.0-or-later
 * Selection artwork computed only during a brief user-triggered transition.
 * Included in gui_list.c after list_impl_t.
 */
#include <grub/env.h>
#include <grub/time.h>

/* Keep entry names and actions intact; only the Ring's presentation changes. */
static void
erdtree_draw_title (const char *title, grub_font_t font,
                    grub_video_color_t color, int width, int baseline)
{
  const char *variant = grub_env_get ("erdtree_variant");
  int left = 0;
  char capitals[512];
  if (variant && !grub_strcmp (variant, "ring"))
    {
      grub_size_t i, length = grub_strlen (title);
      if (length < sizeof (capitals))
        {
          for (i = 0; i <= length; ++i)
            capitals[i] = title[i] >= 'a' && title[i] <= 'z'
              ? title[i] - 'a' + 'A' : title[i];
          title = capitals;
        }
      left = (width - grub_font_get_string_width (font, title)) / 2;
      if (left < 0) left = 0;
      /* A discreet shadow keeps the fine lettering readable over the knight. */
      grub_font_draw_string (title, font, grub_video_map_rgb (4, 8, 5),
                             left + 1, baseline + 1);
    }
  grub_font_draw_string (title, font, color, left, baseline);
}

static int
erdtree_draw_highlight (list_impl_t self, int top, int width, int height)
{
  struct grub_video_bitmap *bitmap;
  const char *enabled = grub_env_get ("erdtree_motion");
  const char *variant = grub_env_get ("erdtree_variant");
  grub_err_t saved_errno = grub_errno;
  grub_uint64_t age;
  int x, y, pulse = 0, center = -1000, radius;
  int color[3] = {200, 163, 94}, tint = 0;
  int ring = variant && !grub_strcmp (variant, "ring");

  if (variant && !grub_strcmp (variant, "carian"))
    { color[0] = 130; color[1] = 184; color[2] = 238; tint = 1; }
  else if (variant && !grub_strcmp (variant, "destined"))
    { color[0] = 203; color[1] = 75; color[2] = 85; tint = 1; }
  else if (variant && !grub_strcmp (variant, "farum"))
    { color[0] = 200; color[1] = 184; color[2] = 150; tint = 1; }

  if (!enabled || grub_strcmp (enabled, "1") || width < 64 ||
      width > 4096 || height < 12 || height > 200)
    return 0;
  bitmap = self->motion_highlight;
  if (bitmap && ((int) bitmap->mode_info.width != width ||
                 (int) bitmap->mode_info.height != height))
    {
      grub_video_bitmap_destroy (bitmap);
      self->motion_highlight = bitmap = 0;
    }
  if (!bitmap)
    {
      if (grub_video_bitmap_create (&bitmap, width, height,
                                   GRUB_VIDEO_BLIT_FORMAT_RGBA_8888))
        {
          grub_errno = saved_errno;
          return 0;
        }
      self->motion_highlight = bitmap;
    }
  age = grub_get_time_ms () - self->view->motion_changed;
  radius = width / 5;
  if (self->view->motion_active && age < 360)
    {
      pulse = (360 - (int) age) * 85 / 360;
      center = -radius + (int) age * (width + 2 * radius) / 360;
    }
  if (self->view->motion_confirming)
    pulse = 125;

  for (y = 0; y < height; ++y)
    for (x = 0; x < width; ++x)
      {
        grub_uint8_t *p = (grub_uint8_t *) bitmap->data +
          y * bitmap->mode_info.pitch + x * 4;
        int distance = x > center ? x - center : center - x;
        int sweep = distance < radius ? (radius - distance) * 70 / radius : 0;
        int vertical = height / 2 - grub_abs (y - height / 2);
        if (ring)
          {
            int horizontal = (width - grub_abs (2 * x - width + 1)) * 256 / width;
            int soft_y = (height - grub_abs (2 * y - height + 1)) * 256 / height;
            int opacity = 135 + pulse / 2 + sweep / 3;
            horizontal = horizontal * horizontal / 256;
            soft_y = soft_y * soft_y / 256 * soft_y / 256;
            p[0] = 218; p[1] = 181; p[2] = 95;
            p[3] = opacity * horizontal / 256 * soft_y / 256;
            continue;
          }
        int a = 13 + (width - x) * 36 / width;
        int edge = x >= 8 && x < width - 8 && (y == 1 || y == height - 2);
        int diamond = (grub_abs (x - 8) + grub_abs (y - height / 2) == 6 ||
                       grub_abs (x - (width - 9)) + grub_abs (y - height / 2) == 6);
        a += (pulse + sweep) * (height / 2 + vertical) / height;
        if (edge) a = 108 + pulse + sweep;
        if (diamond) a = 195 + pulse / 3;
        if (x < 8 || x >= width - 8) a = diamond ? a : 0;
        if (a > 255) a = 255;
        p[0] = 200 + (pulse + sweep) / 7;
        p[1] = 163 + (pulse + sweep) / 5;
        p[2] = 94 + (pulse + sweep) / 4;
        if (tint)
          {
            int c;
            for (c = 0; c < 3; ++c)
              p[c] = color[c] + (255 - color[c]) * (pulse + sweep) / 320;
          }
        p[3] = a;
      }
  grub_video_blit_bitmap (bitmap, GRUB_VIDEO_BLIT_BLEND,
                          0, top, 0, 0, width, height);
  grub_errno = saved_errno;
  return 1;
}
