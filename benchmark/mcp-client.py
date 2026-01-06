import asyncio
import json
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from typing import List
import pandas as pd
import importlib
import importlib.util
from typing import TypedDict
from datetime import datetime
import shutil

load_dotenv()

# read csv file that contains all the prompts
questions = pd.read_csv("questions.csv")

# set the number of samples per prompt
num_samples = 1
# set the llm to use
model_name = "openai:gpt-4.1"

model = init_chat_model(model_name)

class State(TypedDict):
    prompt: str
    structured_output: object
    ifc_file_path: str
    model_output: str
    input_tokens: int
    output_tokens: int
    tool_call_iterations: List[dict]

# TODO: catch errors while calling tools so that the benchmark does not end
async def main():
    # connect to MCP server and load tools
    client = MultiServerMCPClient(
        {
            "blender": {
                "url": "http://127.0.0.1:8000/mcp",
                "transport": "streamable_http",
            }
        }
    )
    mcp_tools = await client.get_tools()

    async def call_model(state: State):
        """function that calls the model and writes the output to the state"""

        # read prompt, structured output, ifc file path from state and initialize llm-agent
        prompt = state["prompt"]
        ifc_file_path = state["ifc_file_path"]
        structured_output = state["structured_output"]

        if structured_output:
            agent = create_agent(model, mcp_tools, response_format=ToolStrategy(structured_output))
        else:
            agent = create_agent(model, mcp_tools)

        # invoke agents
        chain = [event async for event in agent.astream_events({"messages": [{"role": "system", "content": "You are a BIM assistent. Whenever you have questions about values, infer them or use default values. Always execute the commands and do not ask for confirmation. You must always load the ifc file first."},
                                                                             {"role": "user", "content": f"{prompt}\nThe ifc file path is {ifc_file_path}."}]})]

        # retrieve outputs containing model output, tool calls and token uses
        chain_end = chain[-1]

        model_output = ""
        input_tokens = output_tokens = 0
        tool_call_iterations = []
        for message in chain_end["data"]["output"]["messages"]:
            if not message.response_metadata:
                continue

            tokens = message.usage_metadata
            input_tokens = tokens["input_tokens"]
            output_tokens = tokens["output_tokens"]
            if message.response_metadata["finish_reason"] == "tool_calls":

                tool_calls = []
                for tool_call in message.tool_calls:
                    if tool_call["name"] != "ModelOutput":
                        tool_calls.append({"name": tool_call["name"], "args": tool_call["args"]}) #
                tool_call_iterations.append(
                    {"tool_calls": tool_calls, "input_tokens": input_tokens, "output_tokens": output_tokens})

            if message.response_metadata["finish_reason"] == "stop":
                model_output = message.content


        if "structured_response" in chain_end["data"]["output"].keys():
            model_output = chain_end["data"]["output"]["structured_response"]

        return {
            "model_output": model_output,
            "tool_call_iterations": tool_call_iterations,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }


    # load cache file
    try:
        cache = json.load(open(f"results/cache_{model_name.split(":")[-1]}.json"))
    except FileNotFoundError:
        cache = {}

    # create directory for storing edited ifc files
    edited_ifc_directory = f"results/edited_ifc_{model_name.split(':')[-1]}"
    if not os.path.exists(edited_ifc_directory):
        os.mkdir(edited_ifc_directory)

    # build langchain graph
    builder = StateGraph(State)
    builder.add_node("call_model", call_model)

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    graph = builder.compile()


    # iterate over every prompt from the csv file
    for index, row in questions.iterrows():
        print(f"Processing question {int(str(index))+1} of {len(questions)}...")
        question_id = int(str(index))

        # if prompt already processed, use the cached result
        if str(question_id) in cache:
            print("Question already in cache. Using cached result.")
            print(cache[str(question_id)])
            continue

        # read the prompt, test, ifc file path, and structured output from the csv file
        prompt = row["question"]
        test_path = "tests." + row["test"]
        ifc_path = "ifc/" + row["ifc-file"]

        structured_output = "structured_outputs." + str(row["structured-output"])

        # load the structured output python object
        if not pd.isna(row["structured-output"]):
            output_object = importlib.import_module(structured_output).ModelOutput
        else:
            output_object = None

        # creating subdirectory for storing edited ifc files per question
        edited_question_directory = f"{edited_ifc_directory}/{question_id}"
        if not os.path.exists(edited_question_directory):
            os.mkdir(edited_question_directory)

        # iterate over sample size and store results for every sample
        sample_results = []
        for sample in range(num_samples):

            # create the ifc file that will be edited. Create a new one per sample.
            edited_ifc_path = f"{edited_question_directory}/{row["ifc-file"].split(".ifc")[0]}_{sample}.ifc"
            shutil.copyfile(ifc_path, edited_ifc_path)

            # set the arguments for the LLM
            model_args = {
                "prompt": prompt,
                "structured_output": output_object,
                "ifc_file_path": os.path.abspath(edited_ifc_path),
            }

            # invoke LLM
            result_state = await graph.ainvoke(
                model_args
            )

            # process structured output
            if output_object:
                model_output = result_state["model_output"].__dict__
            else:
                model_output = result_state["model_output"]

            # load and execute test
            test = importlib.import_module(test_path)
            # now you can call test.execute_test() and retrieve the evaluation metrics
            metrics = test.execute_test(ifc_path, edited_ifc_path, model_output)

            # store results for a sample
            sample_cache_object = {
                "sample": sample + 1,
                "model_output": model_output,
                "tool_call_iterations": result_state["tool_call_iterations"],
                "metrics": metrics, # dictionary of metrics
                "score": sum(metrics.values())/len(metrics), # score = fulfilled metrics / all metrics
                "input_tokens": result_state["input_tokens"],
                "output_tokens": result_state["output_tokens"]
            }
            sample_results.append(sample_cache_object)

        # store results for a question
        cache_object = {
            "question_id": question_id,
            "prompt": prompt,
            "model": model_name,
            "ifc_file": row["ifc-file"],
            "results": sample_results,
            "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        }

        # store results in the cache
        cache[question_id] = cache_object

        json.dump(cache, open(f"results/cache_{model_name.split(":")[-1]}.json", "w"))

        # input("Please prepare open Blender file so that the next question can be processed. Press enter to continue.")
        # for manually opening the right ifc file in blender


if __name__ == "__main__":
    asyncio.run(main())
