/* SPDX-License-Identifier: GPL-3.0-or-later
 * Event-driven menu effects. No scene animation and no disk I/O in a frame.
 * Included by gfxmenu/view.c. Opt in with set erdtree_motion=1.
 */
#include <grub/env.h>

static int
erdtree_enabled (void)
{
  const char *value = grub_env_get ("erdtree_motion");
  return value && !grub_strcmp (value, "1");
}

void
grub_gfxmenu_motion_idle (void *data)
{
  grub_gfxmenu_view_t view = data;
  grub_uint64_t now;
  grub_err_t saved_errno = grub_errno;
  if (!erdtree_enabled () || !view->motion_active)
    return;
  now = grub_get_time_ms ();
  if (now - view->motion_last < 25)
    return;
  view->motion_last = now;
  if (now - view->motion_changed >= 360)
    view->motion_active = 0;
  grub_gfxmenu_redraw_menu (view);
  grub_errno = saved_errno;
}

void
grub_gfxmenu_motion_confirm (void *data)
{
  grub_gfxmenu_view_t view = data;
  struct grub_video_bitmap *fade = 0;
  grub_menu_entry_t entry;
  grub_uint64_t start, age;
  grub_err_t saved_errno = grub_errno;
  int w = view->screen.width, h = view->screen.height, duration, last_alpha = -1;

  if (!erdtree_enabled () || w < 320 || h < 200 || w > 2560 || h > 1600)
    return;
  entry = grub_menu_get_entry (view->menu, view->selected);
  if (!entry)
    return;
  /* A submenu gets the acknowledgement flash without the full boot fade. */
  duration = entry->submenu ? 170 : 850;
  if (!entry->submenu &&
      grub_video_bitmap_create (&fade, w, h, GRUB_VIDEO_BLIT_FORMAT_RGBA_8888))
    {
      grub_errno = saved_errno;
      return;
    }
  if (fade)
    grub_memset (fade->data, 0, fade->mode_info.pitch * h);
  view->motion_confirming = 1;
  view->motion_active = 0;
  start = grub_get_time_ms ();

  do
    {
      int alpha, pass;
      age = grub_get_time_ms () - start;
      if (age > (unsigned) duration) age = duration;
      alpha = age > 170 ? (int) (age - 170) * 255 / (duration - 170) : 0;
      /* Smoothstep fade: no abrupt cut at either end. */
      alpha = alpha * alpha * (765 - 2 * alpha) / 65025;
      if (fade && alpha != last_alpha)
        {
          int x, y;
          for (y = 0; y < h; ++y)
            for (x = 0; x < w; ++x)
              ((grub_uint8_t *) fade->data)[y * fade->mode_info.pitch + x * 4 + 3] = alpha;
          last_alpha = alpha;
        }
      for (pass = 0; pass < (view->double_repaint ? 2 : 1); ++pass)
        {
          grub_video_set_viewport (0, 0, w, h);
          grub_video_set_area_status (GRUB_VIDEO_AREA_DISABLED);
          grub_gfxmenu_view_redraw (view, &view->screen);
          if (fade && alpha)
            grub_video_blit_bitmap (fade, GRUB_VIDEO_BLIT_BLEND, 0, 0, 0, 0, w, h);
          if (pass == 0) grub_video_swap_buffers ();
        }
      if (age < (unsigned) duration) grub_millisleep (20);
    }
  while (age < (unsigned) duration);

  grub_video_bitmap_destroy (fade);
  view->motion_confirming = 0;
  grub_errno = saved_errno;
}
