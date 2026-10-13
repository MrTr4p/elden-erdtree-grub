/* SPDX-License-Identifier: GPL-3.0-or-later
 * A swaying Site of Grace and circling light, rendered entirely in GRUB.
 * One reusable bitmap; no allocations, disk reads or floating point per frame.
 */
#include <grub/trig.h>

struct grub_erdtree_ambient
{
  struct grub_video_bitmap *frame;
  grub_uint64_t epoch, last;
  unsigned frame_ms;
  int variant;
  grub_uint8_t *sigil_halo;
  int halo_width, halo_height;
  grub_uint16_t flame_mask[2560];
};

static void erdtree_ring_init (grub_gfxmenu_view_t view);

static int
erdtree_ambient_enabled (void)
{
  const char *value = grub_env_get ("erdtree_ambient");
  return erdtree_enabled () && (!value || grub_strcmp (value, "0"));
}

static void
erdtree_ambient_destroy (grub_gfxmenu_view_t view)
{
  if (!view->ambient) return;
  grub_video_bitmap_destroy (view->ambient->frame);
  grub_free (view->ambient->sigil_halo);
  grub_free (view->ambient);
  view->ambient = 0;
}

static void
erdtree_ambient_init (grub_gfxmenu_view_t view)
{
  struct grub_video_bitmap *source = view->scaled_desktop_image;
  struct grub_erdtree_ambient *motion;
  const char *variant = grub_env_get ("erdtree_variant");
  grub_err_t saved_errno = grub_errno;
  int x, y, w = view->screen.width, h = view->screen.height;
  if (!erdtree_ambient_enabled () || view->ambient || view->ambient_attempted)
    return;
  view->ambient_attempted = 1;
  if (!source || w < 320 || h < 200 || w > 2560 || h > 1600 ||
      source->mode_info.width != (unsigned) w ||
      source->mode_info.height != (unsigned) h ||
      (source->mode_info.blit_format != GRUB_VIDEO_BLIT_FORMAT_RGB_888 &&
       source->mode_info.blit_format != GRUB_VIDEO_BLIT_FORMAT_RGBA_8888))
    return;
  motion = grub_zalloc (sizeof (*motion));
  if (!motion) goto failed;
  view->ambient = motion;
  if (variant && !grub_strcmp (variant, "carian")) motion->variant = 1;
  else if (variant && !grub_strcmp (variant, "destined")) motion->variant = 2;
  else if (variant && !grub_strcmp (variant, "farum")) motion->variant = 3;
  else if (variant && !grub_strcmp (variant, "ring")) motion->variant = 4;
  if (grub_video_bitmap_create (&motion->frame, w, h, source->mode_info.blit_format))
    goto failed;
  for (y = 0; y < h; ++y)
    grub_memcpy ((grub_uint8_t *) motion->frame->data + y * motion->frame->mode_info.pitch,
                 (grub_uint8_t *) source->data + y * source->mode_info.pitch,
                 w * source->mode_info.bytes_per_pixel);
  motion->epoch = motion->last = grub_get_time_ms ();
  motion->frame_ms = 50;
  for (x = 0; x < w; ++x)
    {
      int distance = grub_abs (x - w * 745 / 1000);
      int mask = 256 - (distance - w * 6 / 100) * 256 / (w * 12 / 100);
      if (mask < 0) mask = 0;
      if (mask > 256) mask = 256;
      motion->flame_mask[x] = mask * mask / 256 * (768 - 2 * mask) / 256;
    }
  if (motion->variant == 4) erdtree_ring_init (view);
  return;
failed:
  erdtree_ambient_destroy (view);
  grub_errno = saved_errno;
}

static struct grub_video_bitmap *
erdtree_background (grub_gfxmenu_view_t view)
{
  if (erdtree_ambient_enabled () && view->ambient) return view->ambient->frame;
  return view->scaled_desktop_image;
}

static void
erdtree_tinted_spark (struct grub_video_bitmap *frame, int cx, int cy, int radius,
                       int alpha, int red, int green, int blue)
{
  int dx, dy, c, w = frame->mode_info.width, h = frame->mode_info.height;
  int bpp = frame->mode_info.bytes_per_pixel;
  for (dy = -radius; dy <= radius; ++dy)
    for (dx = -radius; dx <= radius; ++dx)
      {
        int distance = dx * dx + dy * dy;
        int strength;
        grub_uint8_t *p;
        if (distance >= radius * radius || cx + dx < w / 2 || cx + dx >= w ||
            cy + dy < 0 || cy + dy >= h) continue;
        strength = alpha * (radius * radius - distance) / (radius * radius);
        strength = strength * strength / 255;
        p = (grub_uint8_t *) frame->data + (cy + dy) * frame->mode_info.pitch +
          (cx + dx) * bpp;
        for (c = 0; c < 3; ++c)
          {
            int value = p[c] + strength * (c == 0 ? red : c == 1 ? green : blue) / 255;
            p[c] = value > 255 ? 255 : value;
          }
      }
}

static void
erdtree_spark (struct grub_video_bitmap *frame, int cx, int cy, int radius, int alpha)
{
  erdtree_tinted_spark (frame, cx, cy, radius, alpha, 255, 209, 123);
}

/* Interpolate the integer sine table so a slow wave has no visible steps. */
static int
erdtree_wave (unsigned t, unsigned period, unsigned offset)
{
  unsigned phase = (t % period) * 65536U / period + offset * 256U;
  int fraction = phase & 255;
  return (grub_sin (phase >> 8) * (256 - fraction) +
          grub_sin ((phase >> 8) + 1) * fraction) / 256;
}

#include "erdtree_ring.h"
#include "erdtree_scenes.h"

static void
erdtree_ambient_render (grub_gfxmenu_view_t view, grub_uint64_t now)
{
  struct grub_erdtree_ambient *motion = view->ambient;
  struct grub_video_bitmap *source = view->scaled_desktop_image;
  struct grub_video_bitmap *frame = motion->frame;
  int w = view->screen.width, h = view->screen.height;
  int bpp = source->mode_info.bytes_per_pixel, x0 = w / 2;
  unsigned t = (unsigned) (now - motion->epoch);
  int root = h * 645 / 1000;
  int sway = erdtree_wave (t, 5600, 0) * (w * 26 / 1000) / 64;
  int breath = 7 + erdtree_wave (t, 3800, 0) * 5 / 16384;
  int reaction = 0, x, y, i;
  if (motion->variant == 4)
    {
      erdtree_ring_render (view, now);
      return;
    }
  if (motion->variant)
    {
      erdtree_scene_render (view, now);
      return;
    }
  if (view->motion_active && now - view->motion_changed < 360)
    reaction = (360 - (int) (now - view->motion_changed)) * 12 / 360;

  /* Inverse-sample the immutable artwork. The root and mound never move;
     the upper flame bends farther, with a smaller wave travelling upward. */
  for (y = 0; y < h; ++y)
    {
      int bend = y < root ? (root - y) * 256 / (h / 2) : 0;
      int ripple = erdtree_wave (t, 2700, y * 140 / h) * (w * 5 / 1000) / 64;
      int offset;
      const grub_uint8_t *row = (const grub_uint8_t *) source->data + y * source->mode_info.pitch;
      grub_uint8_t *d = (grub_uint8_t *) frame->data +
        y * frame->mode_info.pitch + x0 * bpp;
      if (bend > 256) bend = 256;
      if (y < h / 12) bend = bend * y / (h / 12);
      offset = (sway + ripple) * bend / 256;
      if (!bend)
        {
          grub_memcpy (d, row + x0 * bpp, (w - x0) * bpp);
          continue;
        }
      for (x = x0; x < w; ++x, d += bpp)
        {
          int sx = x * 256 - offset * motion->flame_mask[x] / 256;
          int fraction, c, glow;
          const grub_uint8_t *p, *next;
          if (sx < x0 * 256) sx = x0 * 256;
          if (sx > (w - 1) * 256) sx = (w - 1) * 256;
          fraction = sx & 255;
          p = row + (sx >> 8) * bpp;
          next = (sx >> 8) < w - 1 ? p + bpp : p;
          glow = (p[0] > p[2] ? p[0] - p[2] : 0) *
            (breath + reaction) / 128 * motion->flame_mask[x] / 256 * bend / 256;
          for (c = 0; c < 3; ++c)
            {
              int value = (p[c] * (256 - fraction) + next[c] * fraction) / 256;
              value += glow * (c == 0 ? 5 : c == 1 ? 4 : 2) / 5;
              d[c] = value > 255 ? 255 : value;
            }
          if (bpp == 4) d[3] = p[3];
        }
    }

  /* Soft moving accents follow the existing elliptical grace ring. */
  for (i = 0; i < 3; ++i)
    {
      int trail, radius = w * 3 / 1920;
      if (radius < 2) radius = 2;
      for (trail = 0; trail < 28; ++trail)
        {
          unsigned angle = i * 85 + trail;
          int px = w * 743 / 1000 + erdtree_wave (t, 11000, angle + 64) * (w * 211 / 1000) / 16384;
          int py = h * 760 / 1000 + erdtree_wave (t, 11000, angle) * (h * 143 / 1000) / 16384;
          int alpha = 30 + trail * 3;
          erdtree_spark (frame, px, py, radius, alpha);
        }
    }

  /* A few motes rise beside the flame, fading before they wrap. */
  for (i = 0; i < 18; ++i)
    {
      unsigned seed = (unsigned) (i + 1) * 2654435761U;
      unsigned life = 8000 + seed % 7000;
      unsigned age = (t + seed % life) % life;
      int fade = age < life / 2 ? age : life - age;
      int alpha = fade < 1400 ? fade * 130 / 1400 : 130;
      int px = w * (650 + (seed >> 12) % 200) / 1000 +
        erdtree_wave (t, 5700 + i * 200, i * 29) * (w / 90) / 16384;
      int py = h * 60 / 100 - (int) (age * (h / 2) / life);
      int radius = (2 + i % 2) * w / 1920;
      if (radius < 2) radius = 2;
      erdtree_spark (frame, px, py, radius, alpha);
    }
}
