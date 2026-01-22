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


def _find_north_wall(walls, target_guid, unit_scale):
	target = next((w for w in walls if w.GlobalId == target_guid), None)
	if target is None:
		return None, None, None

	target_bbox = _bbox_in_meters(target, unit_scale)
	target_y_c = target_bbox["y_c"]

	north_candidates = []
	for wall in walls:
		if wall.GlobalId == target_guid:
			continue
		bbox = _bbox_in_meters(wall, unit_scale)
		delta_y = bbox["y_c"] - target_y_c
		if delta_y > 0:
			north_candidates.append((delta_y, wall, bbox))

	if not north_candidates:
		return None, target_bbox, None

	north_candidates.sort(key=lambda item: item[0])
	_, north_wall, north_bbox = north_candidates[0]
	return north_wall, north_bbox, target_bbox


def execute_test(ifc_file, edited_ifc_file, model_output):
	"""Prompt: add a door to the wall that is north (+Y direction) to the wall with id GlobalId = "3YQ$1CPXD2Mh2vQ18vV$hw".

	Perfect criteria (all must be true):
	- a NEW element exists
	- it is an IfcDoor
	- the door is placed on the wall directly north of the referenced wall
	- the door base touches ground level
	- an opening element exists and is associated with the door

	Partial credit:
	- if another class is created (IfcOpeningElement/IfcBuildingElementProxy/etc.), geometry metrics can still pass,
	  but `is_ifc_door` stays False so `perfect` stays False.
	- door located on the wrong wall fails `on_north_wall`.
	"""

	metrics = {
		"object_exists": False,
		"integrity_constraint": False, # integrity_constraint
		"right_location": False, # right_location
		"right_dimensions": False, # right_dimensions	
	}

	try:
		ifc_edited = ifcopenshell.open(edited_ifc_file)
	except Exception:
		return metrics

	unit_scale = 1.0

	existing_objects = ["3YQ$1CPXD2Mh2vQ18vV$hw", "3YQ$1CPXD2Mh2vQ18vV$ig", "3YQ$1CPXD2Mh2vQ18vV$iC"]

	doors = ifc_edited.by_type("IfcDoor")

	for obj in existing_objects:
		doors = [d for d in doors if d.GlobalId != obj]

	if len(doors) != 1:
		return metrics

	door = doors[0]
	try:
		door_bbox = _bbox_in_meters(door, unit_scale)
	except Exception:
		return metrics

	metrics["object_exists"] = True
	is_ifc_door = bool(door.is_a("IfcDoor"))

	opening_rels = getattr(door, "FillsVoids", None) or []
	opening_created = False
	for rel in opening_rels:
		if getattr(rel, "RelatingOpeningElement", None) is not None:
			opening_created = True
			break

	if is_ifc_door and opening_created:
		metrics["integrity_constraint"] = True

	walls = ifc_edited.by_type("IfcWallStandardCase") or ifc_edited.by_type("IfcWall")
	if len(walls) < 2:
		return metrics

	north_wall, north_bbox, target_bbox = _find_north_wall(walls, "3YQ$1CPXD2Mh2vQ18vV$hw", unit_scale)
	if north_wall is None or north_bbox is None or target_bbox is None:
		return metrics

	tol_y = 0.1
	tol_x = 0.25

	in_wall_plane = (
		north_bbox["y_min"] - tol_y <= door_bbox["y_min"] <= north_bbox["y_max"] + tol_y
		and north_bbox["y_min"] - tol_y <= door_bbox["y_max"] <= north_bbox["y_max"] + tol_y
	)
	within_span_x = (
		door_bbox["x_min"] <= north_bbox["x_max"] + tol_x
		and door_bbox["x_max"] >= north_bbox["x_min"] - tol_x
	)

	dist_to_north = abs(door_bbox["y_c"] - north_bbox["y_c"])
	dist_to_target = abs(door_bbox["y_c"] - target_bbox["y_c"])

	on_north_wall = False
	if in_wall_plane and within_span_x and dist_to_north < dist_to_target:
		on_north_wall = True

	ground_z = 0.0
	base_at_ground = _within_abs(door_bbox["z_min"], ground_z, tol=0.05)

	if on_north_wall and base_at_ground:
		metrics["right_location"] = True
  
	if metrics["object_exists"]:
		metrics["right_dimensions"] = True

	return metrics
