flexG rev G - under-rotor sector-drive flex  (TFINER / Decay Sail)
=================================================================
Files (RS-274X Gerber, mm, 4.6 format; Excellon metric 3:3):

  flexG-F_Cu.gbr       top copper
  flexG-B_Cu.gbr       bottom copper
  flexG-F_Mask.gbr     TOP COVERLAY OPENINGS  (see note 1)
  flexG-B_Mask.gbr     BOTTOM COVERLAY OPENINGS
  flexG-Edge_Cuts.gbr  board outline, circle dia 25.40 mm
  flexG-PTH.drl        ALL holes, PLATED: 41 x 0.15 mm vias
                       + 4 x 3.00 mm mounting holes

Build:
  2-layer flexible PCB, polyimide, total thickness 0.10 mm
  finished copper 0.5 oz (18 um) both sides
  surface finish ENIG (immersion gold 1U")
  coverlay both sides WITH OPENINGS as per mask files
  no stiffener, no silkscreen, 100% e-test
  min track/space in design: 0.08 mm ; min drill 0.15 mm

NOTES - please read, this is not a normal circuit board:
1) The large opening in the middle of the TOP coverlay (dia 12.4 mm) is
   INTENTIONAL and REQUIRED. The exposed gold in that area is the working
   electrode surface of an electrostatic motor. Do NOT cover it with
   coverlay. Likewise the ring opening on the BOTTOM (dia 5.9-6.8 mm) is a
   pressure contact surface and must be bare ENIG.
2) The 4 x 3.00 mm holes are plated and pass through copper pads on both
   sides (screw clearance for 4-40 screws with ring terminals). This is
   intentional.
3) There are no components and nothing is soldered to this board.
4) Fine features: 0.08 mm tracks/gaps in the central area, 0.15 mm drills.
