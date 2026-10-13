/* SPDX-License-Identifier: GPL-3.0-or-later
 * Localized bloom and flowing gold dust around the supplied cover's sigil.
 * A quarter-resolution glow mask is prepared once, then reused each frame.
 * The source bitmap, logo, landscape, character and menu are untouched.
 */

static void
erdtree_ring_init (grub_gfxmenu_view_t view)
{
  struct grub_erdtree_ambient *motion = view->ambient;
  struct grub_video_bitmap *source = view->scaled_desktop_image;
  grub_err_t saved_errno = grub_errno;
  grub_uint8_t *scratch;
  int w = view->screen.width, h = view->screen.height;
  int hw = (w + 3) / 4, hh = (h + 3) / 4, x, y, pass;
  int bpp = source->mode_info.bytes_per_pixel, radius = 7;
  motion->halo_width = hw;
  motion->halo_height = hh;
  motion->sigil_halo = grub_zalloc (hw * hh);
  scratch = grub_zalloc (hw * hh);
  if (!motion->sigil_halo || !scratch)
    {
      grub_free (motion->sigil_halo);
      grub_free (scratch);
      motion->sigil_halo = 0;
      grub_errno = saved_errno;
      return;
    }
  for (y = 0; y < hh; ++y)
    for (x = 0; x < hw; ++x)
      {
        const grub_uint8_t *p = (const grub_uint8_t *) source->data +
          y * 4 * source->mode_info.pitch + x * 4 * bpp;
        int warm = p[0] - p[2] - 20;
        if (x * 4 < w * 32 / 100 || x * 4 >= w * 68 / 100 ||
            y * 4 < h * 205 / 1000 || y * 4 >= h * 67 / 100) continue;
        if (warm > 0)
          motion->sigil_halo[y * hw + x] = warm * p[0] / 255;
      }
  /* Two separable box passes give a soft halo, without blurring the artwork. */
  for (pass = 0; pass < 2; ++pass)
    {
      for (y = 0; y < hh; ++y)
        {
          int sum = 0;
          for (x = 0; x <= radius && x < hw; ++x)
            sum += motion->sigil_halo[y * hw + x];
          for (x = 0; x < hw; ++x)
            {
              scratch[y * hw + x] = sum / (2 * radius + 1);
              if (x >= radius) sum -= motion->sigil_halo[y * hw + x - radius];
              if (x + radius + 1 < hw) sum += motion->sigil_halo[y * hw + x + radius + 1];
            }
        }
      for (x = 0; x < hw; ++x)
        {
          int sum = 0;
          for (y = 0; y <= radius && y < hh; ++y) sum += scratch[y * hw + x];
          for (y = 0; y < hh; ++y)
            {
              motion->sigil_halo[y * hw + x] = sum / (2 * radius + 1);
              if (y >= radius) sum -= scratch[(y - radius) * hw + x];
              if (y + radius + 1 < hh) sum += scratch[(y + radius + 1) * hw + x];
            }
        }
    }
  grub_free (scratch);
  grub_errno = saved_errno;
}

/* Subpixel soft motes, clipped to the same area that is restored each frame. */
static void
erdtree_ring_mote (struct grub_video_bitmap *frame, int cx, int cy,
                   int radius, int alpha)
{
  int w = frame->mode_info.width, h = frame->mode_info.height;
  int bpp = frame->mode_info.bytes_per_pixel;
  int x, y, r2 = radius * radius * 65536;
  int x0 = grub_max (cx / 256 - radius, w * 27 / 100);
  int x1 = grub_min (cx / 256 + radius + 1, w * 73 / 100);
  int y0 = grub_max (cy / 256 - radius, h * 205 / 1000);
  int y1 = grub_min (cy / 256 + radius + 1, h * 67 / 100);
  for (y = y0; y < y1; ++y)
    for (x = x0; x < x1; ++x)
      {
        int dx = x * 256 - cx, dy = y * 256 - cy;
        int distance = dx * dx + dy * dy, strength, c;
        grub_uint8_t *p;
        if (distance >= r2) continue;
        strength = (r2 - distance) * 256 / r2;
        strength = alpha * strength / 256 * strength / 256;
        p = (grub_uint8_t *) frame->data + y * frame->mode_info.pitch + x * bpp;
        for (c = 0; c < 3; ++c)
          {
            int value = p[c] + strength * (c == 0 ? 255 : c == 1 ? 204 : 92) / 255;
            p[c] = value > 255 ? 255 : value;
          }
      }
}

static void
erdtree_ring_particles (struct grub_video_bitmap *frame, unsigned t)
{
  int w = frame->mode_info.width, h = frame->mode_info.height;
  int i, tail, radius = grub_max (2, w / 800);
  /* Time-derived paths need no particle allocations or accumulated state.
     Dust rises from the ring, curls outward, then fades before wrapping. */
  for (i = 0; i < 38; ++i)
    {
      unsigned period = 7800 + (i * 577) % 5900;
      int age = (t % period + i * 1799U) % period;
      int side = i & 1 ? 1 : -1;
      int fade = grub_min (255, grub_min (age * 255 / (int) (period / 8),
                                         ((int) period - age) * 255 / (int) (period / 5)));
      for (tail = 3; tail >= 0; --tail)
        {
          int sample_age = age - tail * 55;
          int phase, xf, yf, cx, cy, alpha;
          if (sample_age < 0) continue;
          phase = sample_age * 65536 / period;
          xf = 32768 + side * (2300 + (i * 113) % 2400 + phase * 9600 / 65536);
          xf += erdtree_wave (sample_age, period, i * 37) * 500 / 16384;
          yf = 41943 - phase * 26869 / 65536;
          cx = w * xf / 256;
          cy = h * yf / 256;
          alpha = fade * (tail ? 70 - tail * 16 : 210) / 255;
          if (!tail)
            erdtree_ring_mote (frame, cx, cy, radius * 3, fade * 42 / 255);
          erdtree_ring_mote (frame, cx, cy, radius, alpha);
        }
    }
}

static void
erdtree_ring_render (grub_gfxmenu_view_t view, grub_uint64_t now)
{
  struct grub_erdtree_ambient *motion = view->ambient;
  struct grub_video_bitmap *source = view->scaled_desktop_image;
  struct grub_video_bitmap *frame = motion->frame;
  int w = view->screen.width, h = view->screen.height;
  int x0 = w * 32 / 100, x1 = w * 68 / 100;
  int y0 = h * 205 / 1000, y1 = h * 67 / 100;
  int bpp = source->mode_info.bytes_per_pixel, x, y;
  unsigned t = (unsigned) (now - motion->epoch);
  int breath = 68 + erdtree_wave (t, 5200, 0) * 56 / 16384;
  grub_uint8_t filaments[2560];
  int reaction = 0;
  if (view->motion_active && now - view->motion_changed < 360)
    reaction = (360 - (int) (now - view->motion_changed)) * 10 / 360;
  /* Slow crossing waves move light through the existing golden filaments.
     Compute the column wave once; no trig or allocation in the pixel loop. */
  for (x = x0; x < x1; ++x)
    {
      int wave = 128 + erdtree_wave (t, 3600, x * 640 / w) / 128;
      filaments[x] = wave * wave / 4096;
    }
  for (y = y0; y < y1; ++y)
    {
      int edge_y = y - y0 < y1 - y ? y - y0 : y1 - y;
      int wave = 128 + erdtree_wave (t, 4400, y * 768 / h) / 128;
      int trace = 3 + wave * wave * wave / 1048576;
      const grub_uint8_t *p = (const grub_uint8_t *) source->data + y * source->mode_info.pitch + x0 * bpp;
      grub_uint8_t *d = (grub_uint8_t *) frame->data + y * frame->mode_info.pitch + x0 * bpp;
      /* Clear the wider particle field from the immutable source. */
      grub_memcpy ((grub_uint8_t *) frame->data + y * frame->mode_info.pitch + w * 27 / 100 * bpp,
                   (const grub_uint8_t *) source->data + y * source->mode_info.pitch + w * 27 / 100 * bpp,
                   (w * 73 / 100 - w * 27 / 100) * bpp);
      edge_y = edge_y < h / 24 ? edge_y * 256 / (h / 24) : 256;
      for (x = x0; x < x1; ++x, p += bpp, d += bpp)
        {
          int edge_x = x - x0 < x1 - x ? x - x0 : x1 - x;
          int warm = p[0] > p[2] + 20 ? p[0] - p[2] - 20 : 0;
          int halo = motion->sigil_halo ? motion->sigil_halo[(y / 4) * motion->halo_width + x / 4] : 0;
          int light, c;
          edge_x = edge_x < w / 24 ? edge_x * 256 / (w / 24) : 256;
          light = (halo * (breath + reaction) / 72 +
                   warm * (trace + filaments[x]) / 120) * edge_x / 256 * edge_y / 256;
          for (c = 0; c < 3; ++c)
            {
              /* Roll off near white instead of clipping the brightest gold. */
              int value = p[c] + light * (c == 0 ? 255 : c == 1 ? 196 : 67) / 255 * (255 - p[c]) / 170;
              d[c] = value > 255 ? 255 : value;
            }
          if (bpp == 4) d[3] = p[3];
        }
    }
  erdtree_ring_particles (frame, t);
}
