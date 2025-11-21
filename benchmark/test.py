import ifcopenshell
import math

ifc = ifcopenshell.open("ifc/empty.ifc")

wall = ifc.by_type("IfcWall")[0]

placement = wall.ObjectPlacement
rel = placement.RelativePlacement
dir_x = rel.RefDirection.DirectionRatios if rel.RefDirection else [1, 0, 0]
angle = math.degrees(math.atan2(dir_x[1], dir_x[0]))
print(angle)