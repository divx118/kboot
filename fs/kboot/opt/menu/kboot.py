#! /usr/bin/python
#
# Kboot menu by alephzain
#

import os
import sys
import pygame
import subprocess
import struct
import time
import ConfigParser

from stat import *
from menu import *
from image import *

# for timer loop
key_pressed = False
last_selection_file = "/dev/null"
last_selection = 0
timeout = 30

def write_last(line):
   global last_selection_file
   global last_selection

   if last_selection != 0:
      last_file = open(last_selection_file, 'w')
      last_file.write(line)
      last_file.close()

   pygame.quit()

# write sequence for softreboot
def softreboot(sequence):
   write_last("softboot:%s" % sequence)
   subprocess.call(["/bin/sync"])

   procfile = open("/proc/omap_softreboot","w")
   procfile.write(sequence)
   procfile.close()

# execute the kernel
def kexec_launch():
   subprocess.call(["/usr/sbin/kexec","-e"])

# load the kernel to boot into
def kexec_load(zimage, initramfs, cmdline):
   cmd = ['/usr/sbin/kexec', '-l', zimage, '--initrd', initramfs]
   if cmdline:
      cmd.append('--command-line')
      cmd.append(cmdline.strip())
   subprocess.call(["/bin/sync"])
   subprocess.call(["/bin/umount","/mnt/rawfs"])
   subprocess.call(cmd)

# load and execute kernel
def kboot(zimage, initram):
   path = os.path.dirname(zimage)
   cmdline = None
   if os.path.exists(os.path.join(path, 'cmdline')):
      cmd = open(os.path.join(path, 'cmdline'), "r")
      cmdline = cmd.read().replace("\r\n", " ").replace("\n", " ")
      cmd.close()
   write_last("custom:" + path)
   kexec_load(zimage, initram, cmdline)
   kexec_launch()

# extract the current kernel and initramfs from init or recovery
def unpack(image):
   block = 32768

   rawfile = open("/mnt/rawfs/" + image,"rb")

   header = rawfile.read(0x100)

   (total_size,) = struct.unpack("<L", header[0x8C:0x90])
   (init_offset,) = struct.unpack("<L", header[0x94:0x98])
   (init_size,) = struct.unpack("<L", header[0x98:0x9C])

   if (total_size - init_offset) == init_size:
      kernel_file = "/dev/shm/zImage"
      kernel = open(kernel_file, "w+b")
      kernel_size = init_offset - 0x100
      while(kernel_size > 0):
         if kernel_size - block < 0:
            block = kernel_size
         data = rawfile.read(block)
         kernel.write(data)
         kernel_size -= block
      kernel.close()

      block = 32768

      initrd_file = "/dev/shm/initramfs.cpio.gz"
      initrd = open(initrd_file, "w+b")
      while(init_size > 0):
         if init_size - block < 0:
            block = init_size
         data = rawfile.read(block)
         initrd.write(data)
         init_size -= block
      initrd.close()
      rawfile.close()

      write_last("system:" + image)
      kexec_load(kernel_file, initrd_file, None)
      os.remove(kernel_file)
      os.remove(initrd_file)
      kexec_launch()

   rawfile.close()

# exit program and halt board
def halt():
   pygame.quit()
   sys.exit()

# no comment
def nofunc():
   pass

# menu and submenu loop
def loopmenu(menu, menutitle, bkg, title_color, title_size):
   global key_pressed
   global timeout

   screen = menu.draw_surface

   rect_list = []

   state = [nofunc, None]

   desc_font = pygame.font.Font(None, title_size)    # Font to use
   title = desc_font.render(menutitle, True, title_color)

   pygame.event.post(pygame.event.Event(EVENT_CHANGE_STATE, key = 0))

   # The main while loop
   while 1:
      # Get the next event
      e = pygame.event.wait()

      if e.type == EVENT_CHANGE_STATE:
         screen.fill(0)
         if bkg:
            screen.blit(bkg,(0,0))
         screen.blit(title,(10,10))
         rect_list, func = menu.update(e, state)
         pygame.display.flip()

      if e.type == EVENT_CHECK_KEY_PRESSED:
         if key_pressed == True:
            pygame.time.set_timer(EVENT_CHECK_KEY_PRESSED, 0)
            title = desc_font.render(menutitle, True, title_color)
         else:
            timeout -= 1
            title = desc_font.render(menutitle + " (default in %ds)" % timeout, True, title_color)
         screen.fill(0)
         if bkg:
            screen.blit(bkg,(0,0))
         screen.blit(title,(10,10))
         rect_list, func = menu.update(e, state, True)
         pygame.display.flip()

         if timeout == 0:
            last_file = open(last_selection_file, "r")
            line = last_file.read()
            bootline = line.split(':')
            if bootline[0] == 'system':
               unpack(bootline[1])
            elif bootline[0] == 'softboot':
               softreboot(bootline[1])
            elif bootline[0] == 'custom':
               path = bootline[1]
               kboot(os.path.join(path, 'zImage'), os.path.join(path, 'initramfs.cpio.gz'))
            else:
               halt()

      # Update the menu, based on which "state" we are in - When using the menu
      # in a more complex program, definitely make the states global variables
      # so that you can refer to them by a name
      if e.type == pygame.KEYDOWN:
         if key_pressed == False:
            pygame.event.post(pygame.event.Event(EVENT_CHECK_KEY_PRESSED, key = 0))
            key_pressed = True
         rect_list, func = menu.update(e, state)
         if func == None:
            pygame.event.post(pygame.event.Event(EVENT_CHANGE_STATE, key = 0))
            break
         if func[1]:
            func[0](*func[1])
         else:
            func[0]()

      # Update the screen
      pygame.display.update(rect_list)

# walk through os dir to make system to boot available in menu
def osdirwalk(items, dirname, names):
   if len(names):
      if os.path.isfile(os.path.join(dirname,names[0])):
         if names.count('zImage') == 1 and names.count('initramfs.cpio.gz') == 1:
            zimage = os.path.join(dirname, names[names.index('zImage')])
            initram = os.path.join(dirname, names[names.index('initramfs.cpio.gz')])
            items.append((os.path.basename(dirname), [kboot,[zimage,initram]], None))

# start menu
def initmenu():
   global last_selection
   global last_selection_file
   global timeout

   title_color = WHITE
   menu_ucolor = GRAY
   menu_scolor = BLUE

   title_size = 36
   menu_size = 32
   error_size = 16

   os.environ['SDL_NOMOUSE'] = '1'

   pygame.init()

   pygame.mouse.set_visible(0)

   boardnum = int(sys.argv[1])
   storage = sys.argv[2]
   init_ko = int(sys.argv[3])

   if boardnum == 1:
      resolution = (240,320)
   elif boardnum == 2 or boardnum == 3:
      resolution = (240,400)
   elif boardnum == 4:
      resolution = (272,480)
   elif boardnum == 5:
      resolution = (480,854)
   elif boardnum == 6 or boardnum == 7:
      resolution = (800,480)
   else:
      resolution = (1024,600)

   screen = pygame.display.set_mode(resolution)

   if os.path.exists(storage + "/kboot/images/bkg.png"):
      bkg = load_image('bkg.png', storage + "/kboot/images")
      screen.blit(bkg, (0, 0))
   else:
      bkg = None

   selectos_items = []
   if os.path.exists(storage + "/kboot/os"):
      os.path.walk(storage + "/kboot/os", osdirwalk, selectos_items)

   config = ConfigParser.ConfigParser()
   config.read(storage + '/kboot/conf/config.ini')

   if config.has_option('kboot','title_color'):
      rgb_color = config.get('kboot','title_color')
      color = rgb_color.replace(" ", "").split(",")
      if len(color) == 3:
         title_color = (int(color[0]), int(color[1]), int(color[2]))

   if config.has_option('kboot','menu_item_color'):
      rgb_color = config.get('kboot','menu_item_color')
      color = rgb_color.replace(" ", "").split(",")
      if len(color) == 3:
         menu_ucolor = (int(color[0]), int(color[1]), int(color[2]))

   if config.has_option('kboot','menu_item_selected_color'):
      rgb_color = config.get('kboot','menu_item_selected_color')
      color = rgb_color.replace(" ", "").split(",")
      if len(color) == 3:
         menu_scolor = (int(color[0]), int(color[1]), int(color[2]))

   if config.has_option('kboot','title_font_size'):
      title_size = config.getint('kboot','title_font_size')

   if config.has_option('kboot','menu_font_size'):
      menu_size = config.getint('kboot','menu_font_size')

   if config.has_option('kboot','error_font_size'):
      error_size = config.getint('kboot','error_font_size')

   soft_items = []
   if config.has_section('softboot'):
      for item, value in config.items('softboot'):
         soft_items.append((value,[softreboot,[value]], None))

   softmenu = cMenu(50, 50, 20, 5, 'vertical', 100, screen, menu_ucolor, menu_scolor,
                 menu_size, [('Back to menu', None, None)])
   softmenu.set_center(True, True)
   if len(soft_items):
      softmenu.add_buttons(soft_items)

   advanced_items = []
   advancedmenu = cMenu(50, 50, 20, 5, 'vertical', 100, screen, menu_ucolor, menu_scolor,
                 menu_size, [('Back to menu', None, None)])
   advancedmenu.set_center(True, True)

   if init_ko == 0:
      advanced_items.append(('Boot init', [unpack, ["init"]], None))
   advanced_items.append(('Boot recovery', [unpack, ["recovery"]], None))

   if config.has_option('kboot','softboot'):
      if config.getint('kboot', 'softboot') != 0:
         advanced_items.append(('Soft boot', [loopmenu, [softmenu, "Kboot > Soft boot", bkg, title_color, title_size]], None))

   advancedmenu.add_buttons(advanced_items)

   mainmenu = cMenu(50, 50, 20, 5, 'vertical', 100, screen, menu_ucolor, menu_scolor, menu_size, [])

   mainmenu.set_center(True, True)
   mainmenu.add_buttons(selectos_items)
   mainmenu.add_buttons(
      [('Advanced boot', [loopmenu, [advancedmenu, "Kboot > Advanced boot", bkg, title_color, title_size]], None),
       ('Halt', [halt, None], None)])

   pygame.event.set_blocked(pygame.MOUSEMOTION)

   if config.has_option('kboot','last_selection'):
      last_selection = config.getint('kboot','last_selection')

   if last_selection != 0:
      last_selection_file = storage + "/kboot/conf/.last_selection"
      if os.path.exists(last_selection_file):
         pygame.time.set_timer(EVENT_CHECK_KEY_PRESSED, 1000)
         if config.has_option('kboot', 'last_selection_timeout'):
            timeout = config.getint('kboot', 'last_selection_timeout')

   loopmenu(mainmenu, "Kboot", bkg, title_color, title_size)

if __name__ == "__main__":
   initmenu()
