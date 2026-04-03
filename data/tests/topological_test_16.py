import ifcopenshell
from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Remove the wall that touches both the walls with ids 3cmsjRvPb4wf9t15K203w_ and 3cmsjRvPb4wf9t15K203XR.

    Check that a target wall was removed, and that no integrity constraints are violated
    (i.e., no relationships in the edited model still reference the removed wall GUID).

    Metrics:
      - object_not_exists: target wall exists in original as IfcWall/IfcWallStandardCase and
                       is absent in edited as IfcWall/IfcWallStandardCase.
      - integrity_constraint: in the edited file, no IfcRelationship still references
                              the removed wall GUID (no dangling references).
    """

    target_wall_guid = "3cmsjRvPb4wf9t15K203Cj"

    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False,
    }

    if non_target_elements_unchanged(ifc_file, edited_ifc_file): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def ids_of_types(model, types):
        out = set()
        for t in types:
            for obj in model.by_type(t):
                gid = getattr(obj, "GlobalId", None)
                if gid:
                    out.add(gid)
        return out

    # ---- object_not_exists ----
    wall_types = ["IfcWall", "IfcWallStandardCase"]
    orig_wall_ids = ids_of_types(ifc_original, wall_types)
    edited_wall_ids = ids_of_types(ifc_edited, wall_types)

    metrics["object_not_exists"] = (target_wall_guid in orig_wall_ids) and (target_wall_guid not in edited_wall_ids)

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, [target_wall_guid])

    return metrics
