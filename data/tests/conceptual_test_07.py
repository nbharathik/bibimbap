
def execute_test(ifc_file, edited_ifc_file, model_output):
    return {
        "right_answer": set(model_output["global_ids"]) == {"0bp_Ieqgb3dOf60Ug1H0pA", "0bp_Ieqgb3dOf60Ug1H0xy", "3E$cYc__TFSxk95ilJEo3O"}
    }