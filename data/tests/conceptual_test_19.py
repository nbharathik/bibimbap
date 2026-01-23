
def execute_test(ifc_file, edited_ifc_file, model_output):
    return {
        "right_answer": model_output["global_id"] == "0yUr6Ya6H9KQRXLG$IA5Yb"
    }