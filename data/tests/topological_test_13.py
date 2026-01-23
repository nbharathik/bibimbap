import ifcopenshell
import ifcopenshell.util.placement

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Metrics (all with tolerance 0.1):
      - right_location: window global Y == 900 ± 0.1
      - right_dimensions: window OverallWidth/OverallHeight unchanged (± 0.1)
      - integrity_constraint: opening global Y == 900 ± 0.1
    """
    WINDOW_GUID = "0HbU4cYqD2SBtSJYoQ_eW1"
    TARGET_GLOBAL_Y = 900.0
    TOL = 0.1

    metrics = {
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": False,
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def approx_equal(a, b):
        return abs(float(a) - float(b)) <= TOL

    def find_window(model):
        for w in model.by_type("IfcWindow"):
            if getattr(w, "GlobalId", None) == WINDOW_GUID:
                return w
        return None

    def global_y(obj):
        lp = getattr(obj, "ObjectPlacement", None)
        if lp is None:
            return None
        M = ifcopenshell.util.placement.get_local_placement(lp)
        return float(M[1][3])

    def find_opening_for_window(model, window_obj):
        for rel in model.by_type("IfcRelFillsElement"):
            if rel.RelatedBuildingElement == window_obj:
                return rel.RelatingOpeningElement
        return None

    win_orig = find_window(ifc_original)
    win_edit = find_window(ifc_edited)
    if win_orig is None or win_edit is None:
        return metrics

    # --- right_location ---
    y_win = global_y(win_edit)
    if y_win is not None and approx_equal(y_win, TARGET_GLOBAL_Y):
        metrics["right_location"] = True

    # --- right_dimensions (unchanged) ---
    ow_orig = getattr(win_orig, "OverallWidth", None)
    oh_orig = getattr(win_orig, "OverallHeight", None)
    ow_edit = getattr(win_edit, "OverallWidth", None)
    oh_edit = getattr(win_edit, "OverallHeight", None)

    if None not in (ow_orig, oh_orig, ow_edit, oh_edit):
        if approx_equal(ow_orig, ow_edit) and approx_equal(oh_orig, oh_edit):
            metrics["right_dimensions"] = True

    # --- integrity_constraint (opening moved too) ---
    op_edit = find_opening_for_window(ifc_edited, win_edit)
    if op_edit is None:
        return metrics

    y_open = global_y(op_edit)
    if y_open is not None and approx_equal(y_open, TARGET_GLOBAL_Y):
        metrics["integrity_constraint"] = True

    return metrics

if __name__ == "__main__":
    import sys
    result = execute_test("/Users/tobi/Documents/Projekte/Show2Instruct/bim-benchmark/test_case_files/01/02/01_02_013.ifc","/Users/tobi/Documents/Projekte/Show2Instruct/bim-benchmark/test_case_files/01/02/01_02_013_out.ifc" , None)
    print(result)
