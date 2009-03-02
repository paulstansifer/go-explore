#!/usr/bin/env python
import pygame
from pygame import Surface, Color, draw
from pygame.locals import *

import subprocess
import sys

#They skip the letter I in coordinates
def noi_to_idx(letter):
  if letter <= 'H':
    return ord(letter) - 65
  else:
    return ord(letter) - 66

def idx_to_noi(num):
  rv = chr(num+65)
  if rv > 'H':
    return chr(num+66)
  return rv

#zero-based, and flipped

def gnm_to_idx(gnm):
  return int(gnm)-1
def idx_to_gnm(idx):
  return str(idx+1)


def to_gnu((x,y)):
  return idx_to_noi(x) + idx_to_gnm(y)

def from_gnu(coord):
  return (noi_to_idx(coord[0]), gnm_to_idx(coord[1:]))




class gtp:
  def __init__(self):
    self.process = subprocess.Popen("gnugo --mode gtp",
                                    bufsize=1, shell=True,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)

  def w(self, line):
    self.process.stdin.write(line + "\n")
    out = self.process.stdout.readline()
    self.process.stdout.readline()

    #self.process.stdin.write("showboard\n")
    #for i in xrange(0,24):
    #  print self.process.stdout.readline(),
      
    if out[0] == '=':
      return out[1:].strip()
    else:
      raise Exception, "[" + line + "] -> [" + out + "]"

gnugo = gtp()

    
empty, white, black = 0, 1, 2
color_str = ["empty", "white", "black"]


def png(name):
  return pygame.image.load(name+'.png').convert_alpha()

class move:
  def __init__(self, parent, coord, color):
    self.parent = parent
    self.kids = []
    self.coord = coord
    self.color = color
    self.source = None
      
  def adopt(self, move):
    self.kids.append(move)
    
class game:
  def __init__(self, size):
    gnugo.w("boardsize " + str(size))
    gnugo.w("clear_board")
    self.cur = move(None, None, None)

    self.grid = [ [ 0 for i in xrange(0,size) ]
                  for i in xrange(0,size) ]


    
  def to_play(self):
    if self.cur.color == None or self.cur.color == white:
      return black
    else:
      return white

  def up(self):
    gnugo.w("undo")

    self.cur = self.cur.parent
    self.update_stones()

  def update_stones(self):
    #read new stones status, for captures
    #super stupid, but what's wrong with that?

    #clear off everything
    for i in xrange(0, len(self.grid)):
      for j in xrange(0, len(self.grid)):
        self.grid[i][j] = empty
    
    w_stones = [
      from_gnu(w) for w in gnugo.w("list_stones white").split() ]
    b_stones = [
      from_gnu(b) for b in gnugo.w("list_stones black").split() ]

    for x, y in w_stones:
      self.grid[x][y] = black
    for x, y in b_stones:
      self.grid[x][y] = white

  def move(self, coord, source):
    self.update_stones()
    for k in self.cur.kids:
      if k.coord == coord:
        self.cur = k #go to preexisting move
        return #rest is graph-fiddling we've already done

    m = move(self.cur, coord, self.to_play())

    self.cur.adopt(m)
    self.cur = m
    self.cur.source = source
    
  def gnugo_move(self):
    for k in self.cur.kids:
      if k.source == "gnugo":
        gnugo.w("play " + color_str[self.to_play()] + " " + to_gnu(k.coord))
        self.move(k.coord, None)
        return
    
    #TODO cope with passes
    #TODO handoff event-pumping to another thread, which'll animate the cursor, too
    coord = from_gnu(gnugo.w("genmove " + color_str[self.to_play()]))
    self.move(coord, "gnugo")

  def human_move(self, coord):
    x, y = coord
    coord_str = to_gnu((x,y))

    move_str = color_str[self.to_play()] + " " + coord_str
    legal = int(gnugo.w("is_legal " + move_str))

    if legal:
      gnugo.w("play " + move_str)

      self.move(coord, "human")


class goban:
  def __init__(self, size):
    assert size <= 19
    assert size >= 5
    self.size = size

    self.g = game(size)

    pygame.init()
    self.screen = pygame.display.set_mode((size*21, size*21))

    self.b_stone = png('b_stone')
    self.w_stone = png('w_stone')
    self.empty = Surface((size*21,size*21))
    self.empty.fill(Color(170,170,100,0))

    for i in xrange(0, size):
      draw.line(self.empty, Color(0,0,0,0),
                (10,10+21*i), (size*21-11,10+21*i))
      draw.line(self.empty, Color(0,0,0,0),
                (10+21*i,10), (10+21*i,size*21-11))

    self.icon = Surface((5*21, 5*21))

    self.cursors = [None, 
                    pygame.cursors.load_xbm("curs_w.xbm", "curs_w_mask.xbm"),
                    pygame.cursors.load_xbm("curs_b.xbm", "curs_b_mask.xbm")]
    self.yy_cursor = pygame.cursors.load_xbm("yy1.xbm", "yy1_mask.xbm")

  
  def main(self):
    pygame.display.set_caption('go explore')
    pygame.mouse.set_visible(1)


    while 1:
      event = pygame.event.wait()

      if event.type == QUIT: return
      elif event.type == MOUSEMOTION:
        pass
      elif event.type == MOUSEBUTTONDOWN:
        x, y = event.pos
        x /= 21; y /= 21
        self.g.human_move((x,y))
        pygame.mouse.set_cursor(*self.cursors[self.g.to_play()])
      elif event.type == MOUSEBUTTONUP:
        pass
      elif event.type == KEYDOWN:
        if event.key == K_DOWN:
          self.g.gnugo_move()
          pygame.mouse.set_cursor(*self.cursors[self.g.to_play()])
        if event.key == K_UP:
          self.g.up()
          pygame.mouse.set_cursor(*self.cursors[self.g.to_play()])
        if event.key == K_RETURN:
          pass

      self.paint()

  def paint(self):
    self.screen.blit(self.empty, (0,0))

    for x in xrange(0,self.size):
      for y in xrange(0,self.size):
        color = self.g.grid[x][y]
        if color == 1:
          self.screen.blit(self.b_stone, (x*21, y*21))
        elif color == 2:
          self.screen.blit(self.w_stone, (x*21, y*21))

    if self.g.cur.coord == None:
      fx, fy = self.size/2, self.size/2
    else:
      fx, fy = self.g.cur.coord
    cx = min(self.size-3, max(2, fx))-2
    cy = min(self.size-3, max(2, fy))-2

    self.icon.blit(self.screen, (0,0), Rect(cx*21, cy*21, 5*21, 5*21))


    ghost_piece = Surface((11,11)).convert_alpha(self.screen)
    ghost_piece.fill(Color(0,0,0,0))
    pygame.draw.ellipse(ghost_piece,
                        (Color(0,0,0,96)
                         if self.g.to_play() == black else
                         Color(255,255,255,96)),
                        (0, 0, 12, 12), 0)
    
    for k in self.g.cur.kids:
      x, y = k.coord
      self.screen.blit(ghost_piece, (x*21+5, y*21+5))
      

    pygame.display.set_icon(self.icon)
    pygame.display.flip()


if __name__ == '__main__':
    goban(9).main()
