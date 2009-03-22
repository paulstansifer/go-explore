-- general --

it would be nice if the design were extremely simple.

-- game tree --

answering "what-if" questions is an important part of learning.
taking, playing out, and abandoning a tangent should be simple, as
should be sorting through all the current leaves of the tree.

value judging is another important part of learning.  there are two
prongs: hueristics (asking gnugo to estimate a score) (this should be
off by default, since it isn't very trustworthy, and its inherently
died towards specific means of counting (assured territory?  predicted
territory?)), and evaluation by playing-out.  when the player leaves a
branch because the situation is uninterestingly slanted towards one
side, the branch can be tinted to reflect that.  also, life-death
transitions are sometimes formalizable.

-- ui --

have a keyboard interface.  this can be done simply.

make playing both sides natural.  perhaps this can counteract a
tendency to construct a perfect game to beat the computer, but that is
tailored to its specific mistakes?

-- ideas --

to distinguish leaves more easily, gray/blur/dim pieces that haven't
been changing between.

for navigation purposes, color the board with gnugo's
initial_influence function.  also, size the tokens based on a
minimaxing of gnugo's score for leaf nodes.  have 'down' make the
largest move.