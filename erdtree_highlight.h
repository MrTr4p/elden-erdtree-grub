/* SPDX-License-Identifier: GPL-3.0-or-later
 * Selection artwork computed only during a brief user-triggered transition.
 * Included in gui_list.c after list_impl_t. The background never changes.
 */
#include <grub/env.h>
#include <grub/time.h>

static int
erdtree_draw_highlight (list_impl_t self, int top, int width, int height)
{
  struct grub_video_bitmap *bitmap;
  const char *enabled = grub_env_get ("erdtree_motion");
  grub_err_t saved_errno = grub_errno;
  grub_uint64_t age;
  int x, y, pulse = 0, center = -1000, radius;

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
        p[3] = a;
      }
  grub_video_blit_bitmap (bitmap, GRUB_VIDEO_BLIT_BLEND,
                          0, top, 0, 0, width, height);
  grub_errno = saved_errno;
  return 1;
}
