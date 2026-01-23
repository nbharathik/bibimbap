
def execute_test(ifc_file, edited_ifc_file, model_output):
    return {
        "right_answer": model_output["global_id"] == "2YBG8$weL8dfjf3ERiESW$"
    }