#! /usr/bin/python
#
# Kboot menu by alephzain
#

import os
import sys
import pygame
import subprocess
import struct

from stat import *
from menu import *
from image import *

# write sequence for softreboot
def softreboot(sequence):
   procfile = open("/proc/omap_softreboot","w")
   procfile.write(sequence)
   procfile.close()

# execute the kernel
def kexec_launch():
   ret = subprocess.call(["/bin/sync"])
   if ret:
      print "sync error"
      return
   ret = subprocess.call(["/usr/sbin/kexec","-e"])
   if ret:
      print "kexec launch error"
      return

# load the kernel to boot into
def kexec_load(zimage, initramfs):
   ret = subprocess.call(["/usr/sbin/kexec","-l",zimage,"--initrd",initramfs])
   if ret:
      print "kexec load error"
      return

# load and execute kernel
def kboot(zimage,initram):
   kexec_load(zimage,initram)
   kexec_launch()

# extract the current kernel and initramfs in init or recovery
def unpack(image):
   block=32768

   rawfile = open("/mnt/rawfs/"+image,"rb")

   header = rawfile.read(0x100)

   (total_size,) = struct.unpack("<L",header[0x8C:0x90])
   (init_offset,) = struct.unpack("<L",header[0x94:0x98])
   (init_size,) = struct.unpack("<L",header[0x98:0x9C])

   if (total_size-init_offset) == init_size:
      kernel_file = "/dev/shm/zImage"
      kernel = open(kernel_file,"w+b")
      kernel_size = init_offset-0x100
      while(kernel_size > 0):
         if kernel_size - block < 0:
	    block = kernel_size
         data = rawfile.read(block)
         kernel.write(data)
         kernel_size -= block
      kernel.close()

      block = 32768

      initrd_file = "/dev/shm/initramfs.cpio.gz"
      initrd = open(initrd_file,"w+b")
      while(init_size > 0):
         if init_size - block < 0:
	    block = init_size
         data = rawfile.read(block)
         initrd.write(data)
         init_size -= block
      initrd.close()
      rawfile.close()

      kboot(kernel_file, initrd_file)

   rawfile.close()

# exit program and halt board
def halt():
   pygame.quit()
   sys.exit()

# no comment
def nofunc():
   pass

# menu and submenu loop
def loopmenu(menu, menutitle, bkg):
   screen = menu.draw_surface
   rect_list = []

   state = [nofunc, None]

   desc_font = pygame.font.Font(None, 36)    # Font to use
   title = desc_font.render(menutitle, True, WHITE)

   pygame.event.post(pygame.event.Event(EVENT_CHANGE_STATE, key = 0))

   # The main while loop
   while 1:
      # Get the next event
      e = pygame.event.wait()

      if e.type == EVENT_CHANGE_STATE:
        screen.fill(0)
        screen.blit(bkg,(0,0))
        screen.blit(title,(10,10))
        pygame.display.flip()
        rect_list, func = menu.update(e, state)

      # Update the menu, based on which "state" we are in - When using the menu
      # in a more complex program, definitely make the states global variables
      # so that you can refer to them by a name
      if e.type == pygame.KEYDOWN:
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
   os.environ['SDL_NOMOUSE'] = '1'

   pygame.init()

   pygame.mouse.set_visible(0)

   script_path = os.path.dirname(sys.argv[0])
   boardnum = sys.argv[1]
   storage = sys.argv[2]

   if boardnum == 1:
      resolution = (240,320)
   elif boardnum == 2 or boardnum == 3:
      resolution = (240,400)
   elif boardnum == 4:
      resolution = (272,480)
   elif boardnum == 5:
      resolution = (480,854)
   elif boardnum == 6 or boardnum == 7:
      resolution = (800,400)
   else:
      resolution = (1024,600)

   screen = pygame.display.set_mode(resolution)

   bkg = load_image('bkg.png',script_path+os.sep+'images')

   screen.blit(bkg, (0, 0))

   items = []
   os.path.walk(storage+"/kboot/os",osdirwalk, items)

   items2 = []
   if os.path.exists(storage+"/kboot/conf/advanced"):
      seq = open(storage+"/kboot/conf/advanced","r")
      for line in seq.readlines():
         sline = line.strip("\r\n")
         items2.append((sline,[softreboot,[sline]], None))
      seq.close()

   menu2 = cMenu(50, 50, 20, 5, 'vertical', 100, screen,
               [('Back to menu', None, None)])
   menu2.set_center(True, True)
   if len(items2):
      menu2.add_buttons(items2)

   menu1 = cMenu(50, 50, 20, 5, 'vertical', 100, screen,
               [('Back to menu', None, None)])
   menu1.set_center(True, True)
   menu1.add_buttons(items)

   menu = cMenu(50, 50, 20, 5, 'vertical', 100, screen,
               [('Boot init', [unpack,["init"]], None),
                ('Boot recovery', [unpack,["recovery"]], None),
                ('Advanced boot', [loopmenu,[menu2,"Kboot > Advanced boot",bkg]], None),
                ('Boot custom', [loopmenu,[menu1,"Kboot > Boot custom",bkg]], None),
		('Halt', [halt,None], None)])

   menu.set_center(True, True)

   pygame.event.set_blocked(pygame.MOUSEMOTION)

   loopmenu(menu, "Kboot", bkg)

if __name__ == "__main__":
   initmenu()
