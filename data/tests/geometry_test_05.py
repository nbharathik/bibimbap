import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import math

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
		"z_max": z_max
	}

def _within_abs(value, expected, tol):
	return abs(value - expected) <= tol

def execute_test(ifc_file, edited_ifc_file, model_output):
	metrics = {
		"object_exists": False,
		"is_ifc_wall": False,
		"correct_start": False,
		"correct_orientation": False
	}

	try:
		ifc_edited = ifcopenshell.open(edited_ifc_file)
	except Exception:
		return metrics
	
	walls = ifc_edited.by_type("IfcWall")
	if not walls:
		return metrics
	
	unit_scale = 1.0
	tol = 0.5
	
	for wall in walls:
		try:
			bbox = _bbox_in_meters(wall, unit_scale)
			
			metrics["object_exists"] = True
			metrics["is_ifc_wall"] = True

			match_start_x = _within_abs(bbox["x_min"], 10.0, tol)
			match_start_y = _within_abs(bbox["y_min"], 5.0, tol) or _within_abs(bbox["y_max"], 5.0, tol)
			
			if match_start_x and match_start_y:
				metrics["correct_start"] = True
				
				x_len = bbox["x_max"] - bbox["x_min"]
				y_len = bbox["y_max"] - bbox["y_min"]
				
				if x_len > y_len:
					metrics["correct_orientation"] = True
				
				break
		except:
			continue

	return metrics
