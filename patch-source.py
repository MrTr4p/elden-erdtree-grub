#!/usr/bin/env python3
"""Apply an opt-in interaction patch to a private, clean GRUB 2.14 tree."""
from pathlib import Path
import shutil
import difflib

BASE = Path(__file__).resolve().parent
SRC = BASE / 'vendor/grub-2.14'
BACKUP = BASE / 'vendor/original'

def replace(file, old, new):
    path = SRC / file
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'{file}: expected one patch location, got {text.count(old)}')
    original = BACKUP / file
    original.parent.mkdir(parents=True, exist_ok=True)
    if not original.exists():
        shutil.copy2(path, original)
    path.write_text(text.replace(old, new))

replace('include/grub/menu_viewer.h', '  void (*fini) (void *fini);',
        '  void (*fini) (void *fini);\n  void (*idle) (void *data);\n  void (*confirm) (void *data);')
replace('include/grub/gfxmenu_view.h', '  int selected;', '''  int selected;
  grub_uint64_t motion_changed, motion_last;
  int motion_active, motion_confirming;''')
replace('include/grub/gfxmenu_view.h', 'void grub_gfxmenu_view_draw (grub_gfxmenu_view_t view);',
        '''void grub_gfxmenu_view_draw (grub_gfxmenu_view_t view);
void grub_gfxmenu_motion_idle (void *data);
void grub_gfxmenu_motion_confirm (void *data);''')
replace('grub-core/gfxmenu/gfxmenu.c', '  instance->clear_timeout = grub_gfxmenu_clear_timeout;',
        '''  instance->clear_timeout = grub_gfxmenu_clear_timeout;
  instance->idle = grub_gfxmenu_motion_idle;
  instance->confirm = grub_gfxmenu_motion_confirm;''')
replace('grub-core/normal/menu.c', 'static struct grub_menu_viewer *viewers;',
        '''static struct grub_menu_viewer *viewers;

static void
menu_confirm (void)
{
  struct grub_menu_viewer *viewer;
  for (viewer = viewers; viewer; viewer = viewer->next)
    if (viewer->confirm) viewer->confirm (viewer->data);
}''')
replace('grub-core/normal/menu.c', '      c = grub_getkey_noblock ();\n\n      /* Negative values',
        '''      c = grub_getkey_noblock ();
      if (c == GRUB_TERM_NO_KEY)
        {
          struct grub_menu_viewer *viewer;
          for (viewer = viewers; viewer; viewer = viewer->next)
            if (viewer->idle) viewer->idle (viewer->data);
        }

      /* Negative values''')
replace('grub-core/normal/menu.c',
        "\t    case GRUB_TERM_CTRL | 'f':\n\t      menu_fini ();",
        "\t    case GRUB_TERM_CTRL | 'f':\n              menu_confirm ();\n\t      menu_fini ();")
replace('grub-core/normal/menu.c',
        '          *auto_boot = 1;\n\t  menu_fini ();',
        '          *auto_boot = 1;\n          menu_confirm ();\n\t  menu_fini ();')
replace('grub-core/normal/menu.c',
        '\t\tif (entry >= 0)\n\t\t  {\n\t\t    menu_fini ();',
        '\t\tif (entry >= 0)\n\t\t  {\n                    menu_set_chosen_entry (entry);\n                    menu_confirm ();\n\t\t    menu_fini ();')
replace('grub-core/gfxmenu/view.c', 'static grub_gfxmenu_view_t term_view;',
        'static grub_gfxmenu_view_t term_view;\n#include "erdtree_view.h"')
replace('include/grub/gfxmenu_view.h', '  struct grub_video_bitmap *scaled_desktop_image;',
        '''  struct grub_video_bitmap *scaled_desktop_image;
  struct grub_erdtree_ambient *ambient;
  int ambient_attempted;''')
replace('grub-core/gfxmenu/view.c', '  view->scaled_desktop_image = 0;',
        '''  view->scaled_desktop_image = 0;
  view->ambient = 0;
  view->ambient_attempted = 0;''')
replace('grub-core/gfxmenu/view.c', '  grub_video_bitmap_destroy (view->raw_desktop_image);',
        '  erdtree_ambient_destroy (view);\n  grub_video_bitmap_destroy (view->raw_desktop_image);')
replace('grub-core/gfxmenu/view.c', '      struct grub_video_bitmap *img = view->scaled_desktop_image;',
        '      struct grub_video_bitmap *img = erdtree_background (view);')
replace('grub-core/gfxmenu/view.c', '  init_background (view);',
        '  init_background (view);\n  erdtree_ambient_init (view);')
replace('grub-core/gfxmenu/view.c', '  view->need_to_check_sanity = 1;',
        '''  view->motion_changed = view->motion_last = 0;
  view->motion_active = view->motion_confirming = 0;
  view->need_to_check_sanity = 1;''')
replace('grub-core/gfxmenu/view.c', '  view->selected = entry;\n  grub_gfxmenu_redraw_menu (view);',
        '''  if (entry != view->selected && erdtree_enabled ())
    {
      view->motion_changed = grub_get_time_ms ();
      view->motion_last = 0;
      view->motion_active = 1;
    }
  view->selected = entry;
  grub_gfxmenu_redraw_menu (view);''')
replace('grub-core/gfxmenu/gui_list.c', '  grub_gfxmenu_view_t view;',
        '  grub_gfxmenu_view_t view;\n  struct grub_video_bitmap *motion_highlight;')
replace('grub-core/gfxmenu/gui_list.c', 'typedef struct grub_gui_list_impl *list_impl_t;',
        'typedef struct grub_gui_list_impl *list_impl_t;\n#include "erdtree_highlight.h"')
replace('grub-core/gfxmenu/gui_list.c', '  grub_free (self->theme_dir);\n  grub_free (self->menu_box_pattern);',
        '  grub_video_bitmap_destroy (self->motion_highlight);\n  grub_free (self->theme_dir);\n  grub_free (self->menu_box_pattern);')
replace('grub-core/gfxmenu/gui_list.c',
        '          selbox->draw (selbox, 0, item_top + sel_box_top_offset);',
        '''          if (!erdtree_draw_highlight (self, item_top + sel_box_top_offset,
                                      cwidth, text_box_height))
            selbox->draw (selbox, 0, item_top + sel_box_top_offset);''')
replace('grub-core/gfxmenu/gui_list.c',
        '''      grub_font_draw_string (item_title,
                             font,
                             color,
                             0,
                             text_top_offset);''',
        '''      erdtree_draw_title (item_title, font, color,
                           viewport_width, text_top_offset);''')

for name in ['erdtree_view.h', 'erdtree_highlight.h', 'erdtree_ambient.h', 'erdtree_scenes.h', 'erdtree_ring.h']:
    shutil.copy2(BASE / name, SRC / 'grub-core/gfxmenu' / name)
patch = []
for original in sorted(BACKUP.rglob('*')):
    if not original.is_file(): continue
    rel = original.relative_to(BACKUP)
    patch.extend(difflib.unified_diff(original.read_text().splitlines(True),
                 (SRC / rel).read_text().splitlines(True), 'a/' + str(rel), 'b/' + str(rel)))
for name in ['erdtree_view.h', 'erdtree_highlight.h', 'erdtree_ambient.h', 'erdtree_scenes.h', 'erdtree_ring.h']:
    patch.extend(difflib.unified_diff([], (BASE / name).read_text().splitlines(True),
                                    '/dev/null', 'b/grub-core/gfxmenu/' + name))
(BASE / 'patches').mkdir(exist_ok=True)
(BASE / 'patches/grub-2.14-erdtree-interactions.patch').write_text(''.join(patch))
print('Patched private GRUB tree: ambient grace + selection shimmer + confirmation flash/fade.')
