import ifcopenshell
import os
import ifcopenshell.geom
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a slab that closes the elements with the ids [GlobalId = "3_DHXxtdb3wRKlXgyMiHR$", 
    GlobalId = "3_DHXxtdb3wRKlXgyMiHOP", GlobalId = "3_DHXxtdb3wRKlXgyMiH5o", GlobalId = "1IMYx2Ej12vu3iYKHoTn08"] ."""
    metrics = {
        "object_exists": False, 
        "right_location": False,
        "right_dimensions": False 
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # check if there is a new slab
    original_slab_guids = set(slab.GlobalId for slab in ifc_original.by_type("IfcSlab"))
    edited_slab_guids = set(slab.GlobalId for slab in ifc_edited.by_type("IfcSlab"))

    new_slab_ids = list(edited_slab_guids - original_slab_guids)
    if len(new_slab_ids) == 0:
        return metrics
    metrics["object_exists"] = True
    slab = ifc_edited.by_guid(new_slab_ids[0])

    # get slab geometry information
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, slab)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    x_min_slab = min(vertices[:, 0])
    x_max_slab = max(vertices[:, 0])
    y_min_slab = min(vertices[:, 1])
    y_max_slab = max(vertices[:, 1])
    z_min_slab = min(vertices[:, 2])
    z_max_slab = max(vertices[:, 2])

    slab_width = ifcopenshell.util.shape.get_x(geom)
    slab_depth = ifcopenshell.util.shape.get_y(geom)
    slab_thickness = ifcopenshell.util.shape.get_z(geom)

    # get wall geometry information to determine the enclosed area
    wall_ids = ["3_DHXxtdb3wRKlXgyMiHR$", "3_DHXxtdb3wRKlXgyMiHOP", 
                "3_DHXxtdb3wRKlXgyMiH5o", "1IMYx2Ej12vu3iYKHoTn08"]
    
    try:
        wall_bounds = []
        wall_heights = []
        for wall_id in wall_ids:
            try:
                wall = ifc_edited.by_guid(wall_id)
                wall_shape = ifcopenshell.geom.create_shape(settings, wall)
                wall_geom = wall_shape.geometry
                wall_vertices = ifcopenshell.util.shape.get_shape_vertices(wall_shape, wall_geom)
                wall_bounds.append({
                    'x_min': min(wall_vertices[:, 0]),
                    'x_max': max(wall_vertices[:, 0]),
                    'y_min': min(wall_vertices[:, 1]),
                    'y_max': max(wall_vertices[:, 1]),
                    'z_min': min(wall_vertices[:, 2]),
                    'z_max': max(wall_vertices[:, 2])
                })
                wall_heights.append(max(wall_vertices[:, 2]))
            except:
                continue
        
        if len(wall_bounds) >= 4:
            # calculate the bounding box of the enclosed area
            x_min_space = min(wb['x_min'] for wb in wall_bounds)
            x_max_space = max(wb['x_max'] for wb in wall_bounds)
            y_min_space = min(wb['y_min'] for wb in wall_bounds)
            y_max_space = max(wb['y_max'] for wb in wall_bounds)
            z_max_walls = max(wall_heights)
            z_min_walls = min(wb['z_min'] for wb in wall_bounds)
            
            space_width = x_max_space - x_min_space
            space_depth = y_max_space - y_min_space
            
            # check if slab dimensions match the enclosed area (right_dimensions)
            tolerance = 1.0
            slab_area = slab_width * slab_depth
            space_area = space_width * space_depth
            
            # slab should roughly cover the enclosed area
            if abs(slab_width - space_width) < tolerance and abs(slab_depth - space_depth) < tolerance:
                metrics["right_dimensions"] = True
            elif abs(slab_area - space_area) < (space_area * 0.3):  # within 30% of area
                metrics["right_dimensions"] = True
            
            # check if slab is positioned at the top or bottom of walls (right_location)
            # slab should be at the base (floor) or top (ceiling) of the walls
            slab_z_center = (z_min_slab + z_max_slab) / 2
            
            # check if slab is at the bottom (floor) or top (ceiling) of the walls
            at_floor = abs(slab_z_center - z_min_walls) < tolerance
            at_ceiling = abs(slab_z_center - z_max_walls) < tolerance
            
            # also check if slab overlaps with the enclosed area in x,y plane
            x_overlap = not (x_max_slab < x_min_space - tolerance or x_min_slab > x_max_space + tolerance)
            y_overlap = not (y_max_slab < y_min_space - tolerance or y_min_slab > y_max_space + tolerance)
            
            if (at_floor or at_ceiling) and x_overlap and y_overlap:
                metrics["right_location"] = True
            
    except Exception:
        pass

    return metrics

if __name__ == "__main__":
    path = os.getcwd()
    print(path)
    result = execute_test("data/02/01_02_004.ifc", "tests/02/04/results/02/01_02_004.ifc", {})
    print("\nTest Results:")
    print(f"  object_exists: {result['object_exists']}")
    print(f"  right_location: {result['right_location']}")
    print(f"  right_dimensions: {result['right_dimensions']}")
