def execute_test(ifc_file, edited_ifc_file, model_output):
    """returns dict with key for every metric and value true/false"""
    """ifc_file state at beginning: simple wall with one door"""

    return_object = {
        "right_answer": False
    }

    area = model_output["area"]

    net_area = 4 * 4 - 1.067 * 2.210
    return_object["right_answer"] = area == net_area


    # TODO: test different units here/ provide unit in structured output? I would say test for multiple units here makes more sense
    # TODO: what if they are 0.1 apart?
    # also, there are two different answers bc door size != opening size and I would count both ways to calculate that as right
    # or use an ifc file where both sizes are the same

    return return_object
