#!/usr/bin/env python
import pygame
from pygame import Surface, Color, draw
from pygame.locals import *

import subprocess, sys, threading

empty, white, black = 0, 1, 2

def moves_after(color):
  if color == black:
    return white
  else:
    return black #black moves first, so it's after None
  
color_str = ["empty", "white", "black"]


#There is no "I" in Go!
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
  if coord == "PASS" or coord == "resign":
    return None
  return (noi_to_idx(coord[0]), gnm_to_idx(coord[1:]))




class GTP:
  def __init__(self, size, strength):
    self.process = subprocess.Popen("gnugo --mode gtp --level " + str(strength),
                                    bufsize=1, shell=True,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)

    self.w("boardsize " + str(size))
    self.w("clear_board")
    

  def w(self, line, expected_lines=1):
    self.process.stdin.write(line + "\n")
    out = self.process.stdout.readline()
    if out[0:2] == '= ':
      out = out[2:].strip()
    else:
      print "<<" + out + ">>"
      self.process.stdin.write("showboard\n")
      for i in xrange(0,9 + 5):
        print self.process.stdout.readline(),
      print "[" + line + "] -> [" + out + "]"
      raise Exception, "[" + line + "] -> [" + out + "]"


    for i in xrange(expected_lines-1):
      out += "\n" + self.process.stdout.readline().strip()

    self.process.stdout.readline() #chew an extra blank line
    
    return out
    
  def score(self): #relative to white
    score_verbose = self.w("estimate_score")
    score = float(score_verbose[1:score_verbose.find(' ')])
    if score_verbose[0:1] == "B":
      return -score
    return score

class GTP_speculator(threading.Thread):
  def __init__(self, size, last_move):
    threading.Thread.__init__(self)
    self.last_move = last_move
    self.size = size
    
  def run(self):
    move = self.last_move
    with move.ai_move_in_progress:
      gnugo_bkg = GTP(self.size, 10)

      #we need a forwards list of moves to get to the current position
      moves = []
      while move.color != None:
        moves.append(move)
        move = move.parent
      moves.reverse()

      for m in moves:
        gnugo_bkg.w("play " + color_str[m.color] +
                    " " + to_gnu(m.coord))
      next_color = color_str[moves_after(self.last_move.color)]



      #up-to-date.  Now estimate score (m/m redundant with below
      #self.last_move.set_absolute_score(gnugo_bkg.score())

      influence_str = gnugo_bkg.w("initial_influence "
          + next_color + " territory_value",
          self.size)
      print influence_str
      #convert to a matrix of numbers
      self.last_move.influence = [[float(val) for val in line.split()]
                                  for line in influence_str.split('\n')]
      

      result = Move(
        self.last_move,
        from_gnu(gnugo_bkg.w("genmove " + next_color)),
        "gnugo bkg")

      #gnugo_bkg.process.stdin.write("showboard\n")
      #for i in xrange(0,14):
      #  print gnugo_bkg.process.stdout.readline(),
                           
      result.source = "gnugo"
      self.last_move.adopt(result)
      result.set_absolute_score(gnugo_bkg.score())
      
      gnugo_bkg.w("quit")


def png(name):
  return pygame.image.load(name+'.png').convert_alpha()

def png_pair(name):
  return [None, png('w_'+name), png('b_'+name)]

score_protector = threading.RLock()

class Move:
  #coord should either be a coordinate pair, or None, for passing/resignation
  def __init__(self, parent, coord, source):
    self.parent = parent
    self.kids = []
    self.coord = coord

    if parent == None:
      self.color = None
    else:
      self.color = moves_after(parent.color)
    
    self.minmaxed = None

    self.source = source
    self.kid_protector = threading.RLock()
    self.ai_move_in_progress = threading.Lock()
    self.visited = False
    self.influence = None
      
  def adopt(self, move):
    with self.kid_protector:
      self.kids.append(move)

  def as_sgf(self):
    with self.kid_protector:
      children = ''.join([k.as_sgf() for k in self.kids])
    if self.coord == None:
      return children
    else:    
      x, y = self.coord
      return ('(;' + [None,'W','B'][self.color] + 
              '[' + chr(ord('a')+x) + chr(ord('a')+y) + ']'+
              children +')')

  def set_absolute_score(self, abs_score):
    with score_protector:
      if self.color == white:
        self.advantage = abs_score
      else:
        self.advantage = -abs_score
      self.minmaxed = self.advantage

      cur_move = self.parent
      while cur_move != None:
        with cur_move.kid_protector:
          cur_move.minmaxed = -max(k.minmaxed for k in cur_move.kids
                                   if k.minmaxed != None)
        cur_move = cur_move.parent
          
    
class Game:
  def __init__(self, size):
    self.cur = Move(None, None, "start")
    self.root = self.cur

    self.grid = [ [ 0 for i in xrange(0,size) ]
                  for i in xrange(0,size) ]

    self.gnugo = GTP(size, 10)

    self.size = size

    #get a first move
    GTP_speculator(size, self.cur).start()

  def as_sgf(self):
    return '(;FF[4]SZ['+str(self.size)+']'+self.root.as_sgf()+')'
    
  def to_play(self):
    return moves_after(self.cur.color)

  def up(self):
    if self.cur.parent == None: return
    self.gnugo.w("undo")

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
      from_gnu(w) for w in self.gnugo.w("list_stones white").split() ]
    b_stones = [
      from_gnu(b) for b in self.gnugo.w("list_stones black").split() ]

    for x, y in w_stones:
      self.grid[x][y] = white
    for x, y in b_stones:
      self.grid[x][y] = black

  def move(self, coord, source):
    if coord == None:
      #except that passes don't register at all, yet
      #if self.cur.parent != None and self.cur.parent.coord == None:
      print self.gnugo.w("estimate_score") #hack!  present the score for real with final_score.
      return
    self.gnugo.w("play " + color_str[self.to_play()] + " " + to_gnu(coord))
    self.update_stones()
    with self.cur.kid_protector:
      for k in self.cur.kids:
        if k.coord == coord:
          self.cur = k #go to preexisting move
          if not k.visited: #TODO: is there a cleaner check?
            if not any(k.source.startswith('gnugo') for k in self.cur.kids):
              GTP_speculator(self.size, self.cur).start()
          k.visited = True
          return #rest is stuff we've already done    

    m = Move(self.cur, coord, source)
    self.cur.adopt(m)
    
    self.cur = m
    m.visited = True

    GTP_speculator(self.size, self.cur).start()
    
  def gnugo_move(self):
    #return false if we need to wait longer
    if not self.cur.ai_move_in_progress.acquire(False):
      return False
    self.cur.ai_move_in_progress.release()

    with self.cur.kid_protector:
      for k in self.cur.kids:
        if k.source == "gnugo":
          self.move(k.coord, None)
          return True
    
    #TODO cope with passes
    #TODO handoff event-pumping to another thread, which'll animate the cursor, too
    coord = self.gnugo.w("reg_genmove " + color_str[self.to_play()])
    self.move(from_gnu(coord), "gnugo")
    return True

  def human_move(self, coord):
    x, y = coord
    coord_str = to_gnu((x,y))

    move_str = color_str[self.to_play()] + " " + coord_str
    legal = int(self.gnugo.w("is_legal " + move_str))

    if legal:
      self.move(coord, "human")


class Goban:
  def __init__(self, size):
    assert size <= 19
    assert size >= 5
    self.size = size

    self.g = Game(size)

    pygame.init()
    self.screen = pygame.display.set_mode((size*21, size*21))
    self.font = pygame.font.Font(pygame.font.get_default_font(), 8)


    self.stone = png_pair('stone')
    self.hand = png_pair('hand')
    self.chip = png_pair('chip')
    self.chip_uncertain = png_pair('chip_uncertain')

    self.empty = Surface((size*21,size*21))
    self.empty.fill(Color(170,170,100,0))  #pretty color
    #self.empty.fill(Color(128,128,128,0))  #more neutral-toned

    for i in xrange(0, size):
      draw.line(self.empty, Color(0,0,0,0),
                (10,10+21*i), (size*21-11,10+21*i))
      draw.line(self.empty, Color(0,0,0,0),
                (10+21*i,10), (10+21*i,size*21-11))

    self.icon = Surface((5*21, 5*21))

    self.cursors = [None, 
                    pygame.cursors.load_xbm("curs_w.xbm", "curs_w_mask.xbm"),
                    pygame.cursors.load_xbm("curs_b.xbm", "curs_b_mask.xbm")]
    self.spining_yy = [pygame.cursors.load_xbm("yy%d.xbm" % i, "circle_mask.xbm")
                       for i in xrange(1,13)]

    self.spining_y = [ None,
                       [pygame.cursors.load_xbm("yy%d.xbm" % i, "hyy%d.xbm" % i)
                        for i in xrange(1,13)],
                       [pygame.cursors.load_xbm("yy%d.xbm" % i, "hyy%d.xbm" % (13-i))
                        for i in xrange(1,13)]]
                       
    
    #self.yy_cursor = pygame.cursors.load_xbm("yy1.xbm", "yy1_mask.xbm")

  
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
        if event.key == K_ESCAPE:
          print self.g.as_sgf()
          return
        if event.key == K_DOWN:
          i = 0
          while self.g.gnugo_move() == False:
            pygame.mouse.set_cursor(*self.spining_yy[i])
            pygame.time.wait(50)
            pygame.event.pump()
            i = (i+1)%12
                                    

            
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
        if color > 0:
          self.screen.blit(self.stone[color], (x*21, y*21))


    if self.g.cur.coord == None:
      fx, fy = self.size/2, self.size/2
    else:
      fx, fy = self.g.cur.coord
    cx = min(self.size-3, max(2, fx))-2
    cy = min(self.size-3, max(2, fy))-2

    self.icon.blit(self.screen, (0,0), Rect(cx*21, cy*21, 5*21, 5*21))
    pygame.display.set_icon(self.icon)

    with self.g.cur.kid_protector:
      if any(k.visited for k in self.g.cur.kids):
        for k in self.g.cur.kids:
          if k.coord == None:
            continue
          x, y = k.coord

          if k.minmaxed != None:
            score = self.font.render(
              str(int(k.minmaxed)),
              True, [None, Color(255,255,255), Color(0,0,0)][k.color])
          
            sc_l_x = (21-score.get_width())/2
            sc_l_y = (21-score.get_height())+3
          
            self.screen.blit(score, (21*x+sc_l_x, 21*y+sc_l_y))
          
          if k.source.startswith('human'):
            self.screen.blit(self.hand[k.color], (21*x+4, 21*y+0))
          elif k.source.startswith('gnugo'):
            if k.parent.source.startswith('gnugo'):
              #computer responses to computer moves are more questionable
              self.screen.blit(self.chip_uncertain[k.color], (21*x+3, 21*y+2))
            else:
              self.screen.blit(self.chip[k.color], (21*x+3, 21*y+2))


          if self.g.cur.influence != None:
            for x in xrange(self.size):
              for y in xrange(self.size):
                icc = lambda n: int(n+50 * self.g.cur.influence[x][y])

                pygame.draw.aaline(self.screen, Color(icc(170),icc(170),icc(100),255),
                                   (21*y+16, 21*(self.size-x-1)+16),
                                   (21*y+5, 21*(self.size-x-1)+5), True)
          

    pygame.display.flip()


if __name__ == '__main__':
    Goban(9).main()
