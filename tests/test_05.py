def execute_test(ifc_file, edited_ifc_file, model_output):
    """returns dict with key for every metric and value true/false"""
    """ifc_file state at beginning: FZK House"""

    return_object = {
        "right_answer": False,
        "right_room_found": False
    }

    num_windows = model_output["number_of_windows"]
    room_id = model_output["room_id"]

    return_object["right_answer"] = num_windows == 2
    return_object["right_room_found"] = (room_id == 21640) or (room_id == 2)

    return return_object
