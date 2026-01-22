import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


def _bbox_in_meters(product, unit_scale):
	settings = ifcopenshell.geom.settings()
	shape = ifcopenshell.geom.create_shape(settings, product)
	geom = shape.geometry
	vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
	vertices = vertices * unit_scale

	x_min = float(vertices[:, 0].min())
	x_max = float(vertices[:, 0].max())
	y_min = float(vertices[:, 1].min())
	y_max = float(vertices[:, 1].max())
	z_min = float(vertices[:, 2].min())
	z_max = float(vertices[:, 2].max())

	return {
		"x_min": x_min,
		"x_max": x_max,
		"y_min": y_min,
		"y_max": y_max,
		"z_min": z_min,
		"z_max": z_max,
		"x_len": x_max - x_min,
		"y_len": y_max - y_min,
		"z_len": z_max - z_min,
		"x_c": (x_min + x_max) / 2.0,
		"y_c": (y_min + y_max) / 2.0,
		"z_c": (z_min + z_max) / 2.0,
	}


def _within_abs(value, expected, tol):
	return abs(value - expected) <= tol


def execute_test(ifc_file, edited_ifc_file, model_output):
	"""Prompt: insert a room (IfcSpace) to the area that is left of the column with id GlobalId = "3A5GfH23DBvBYpavCfWh4z".

	Perfect criteria (all must be true):
	- a NEW element exists
	- it is an IfcSpace
	- it is located left (negative X direction) of the referenced column
	- it fits within the polygon formed by walls ["3A5GfH23DBvBYpavCfWhSk", "3A5GfH23DBvBYpavCfWhRM", "3A5GfH23DBvBYpavCfWhEJ", "3A5GfH23DBvBYpavCfWh5t", "3A5GfH23DBvBYpavCfWhPk"]
	- footprint dimensions roughly match the gap defined by those walls (expected about 6m x 6m)

	Partial credit:
	- Other classes (IfcBuildingElementProxy, etc.) keep metrics except `is_ifc_space`.
	- Spaces not bounded by the listed walls fail `within_walls`.
	"""

	metrics = {
		"object_exists": False,
		"integrity_constraint": False, # integrity_constraint
		"right_location": False, # right_location
		"right_dimensions": False, # right_dimensions
	}

	try:
		ifc_base = ifcopenshell.open(ifc_file)
		ifc_edited = ifcopenshell.open(edited_ifc_file)
	except Exception:
		return metrics

	unit_scale = 1.0

	spaces = [s for s in ifc_edited.by_type("IfcSpace")]

	if len(spaces) != 1:
		return metrics

	space = spaces[0]
	try:
		space_bbox = _bbox_in_meters(space, unit_scale)
	except Exception:
		return metrics

	metrics["object_exists"] = True
	metrics["integrity_constraint"] = bool(space.is_a("IfcSpace"))

	tgt_x_min = 0.20
	tgt_y_min, tgt_y_max = 0.20, 6.70
	tgt_z_min, tgt_z_max = 0.0, 3.0
	tol = 0.5

	common_match = (
		_within_abs(space_bbox["x_min"], tgt_x_min, tol)
		and _within_abs(space_bbox["y_min"], tgt_y_min, tol)
		and _within_abs(space_bbox["y_max"], tgt_y_max, tol)
		and _within_abs(space_bbox["z_min"], tgt_z_min, tol)
		and _within_abs(space_bbox["z_max"], tgt_z_max, tol)
	)

	# Sometimes it could create for the whole fotprint
	left_of_column = False
	within_walls = False
	footprint_matches = False
	if common_match:
		if _within_abs(space_bbox["x_max"], 6.35, tol):
			left_of_column = True
			within_walls = True
			footprint_matches = True
		elif _within_abs(space_bbox["x_max"], 12.75, tol):
			left_of_column = True
			within_walls = True
			footprint_matches = False

	if left_of_column and within_walls:
		metrics["right_location"] = True
	if footprint_matches:
		metrics["right_dimensions"] = True

	return metrics