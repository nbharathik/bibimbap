import asyncio
import json
import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langchain.agents import create_agent

from langchain.agents.structured_output import ToolStrategy
from langchain.agents.structured_output import ProviderStrategy


from typing import List

import pandas as pd
import importlib
import importlib.util
from typing import TypedDict

from datetime import datetime

import shutil
import uuid
import tempfile
from pprint import pprint

load_dotenv()

questions = pd.read_csv("questions.csv")
session_id = str(uuid.uuid4())

num_samples = 1
model_name = "openai:gpt-4.1"
# TODO: use command line arguments for this

model = init_chat_model(model_name)


class State(TypedDict):
    prompt: str
    structured_output: object
    model_output: str
    input_tokens: int
    output_tokens: int
    tool_calls: List[dict]


async def main():
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
        prompt = state["prompt"]
        structured_output = state["structured_output"]
        if structured_output:
            agent = create_agent(model, mcp_tools, response_format=ToolStrategy(structured_output))
        else:
            agent = create_agent(model, mcp_tools)

        chain_end = [event async for event in agent.astream_events({"messages": [{"role": "user", "content": prompt}]})][-1]

        model_output = ""
        input_tokens = output_tokens = 0
        tool_calls = []
        for message in chain_end["data"]["output"]["messages"]:
            if not message.response_metadata:
                continue

            tokens = message.usage_metadata
            input_tokens = tokens["input_tokens"]
            output_tokens = tokens["output_tokens"]
            if message.response_metadata["finish_reason"] == "tool_calls":
                for tool_call in message.tool_calls:
                    tool_calls.append({"name": tool_call["name"], "args": tool_call["args"], "input_tokens": input_tokens, "output_tokens": output_tokens})

            if message.response_metadata["finish_reason"] == "stop":
                model_output = message.content

        structured_response = chain_end["data"]["output"]["structured_response"]
        if structured_response:
            model_output = structured_response

        return {
            "model_output": model_output,
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }


    cache = json.load(open("cache.json"))

    builder = StateGraph(State)
    builder.add_node("call_model", call_model)

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    graph = builder.compile()

    for index, row in questions.iterrows():
        print(f"Processing question {int(str(index))+1} of {len(questions)}...")
        question_id = int(str(index))

        if str(question_id) in cache:
            print("Question already in cache. Using cached result.")
            print(cache[str(question_id)])
            continue

        prompt = row["question"]
        test_path = "tests." + row["test"]
        ifc_path = "ifc/" + row["ifc-file"]

        structured_output = "structured_outputs." + str(row["structured-output"])

        if not pd.isna(row["structured-output"]):
            output_object = importlib.import_module(structured_output).ModelOutput
        else:
            output_object = None

        tmp = tempfile.NamedTemporaryFile(suffix=".ifc", delete=False, mode="w+b")
        edited_ifc_path = tmp.name # TODO: use tempfile as input to the model and for the evaluation
        with open(ifc_path, "rb") as src:
            shutil.copyfileobj(src, tmp)
        tmp.close()
        # tempfile can be accessed by other processes now



        # TODO: loop over number of samples


        model_args = {
                "prompt": prompt,
                "structured_output": output_object
        }
        print(model_args)
        result_state = await graph.ainvoke(
            model_args
        )
        # result state contains prompt, model_output, tool_calls

        if output_object:
            model_output = result_state["model_output"].__dict__
        else:
            model_output = result_state["model_output"]

        test = importlib.import_module(test_path)
        # now you can call test.execute_test()
        metrics = test.execute_test(ifc_path, ifc_path, model_output) # TODO: change that to edited_ifc as soon as it works (without blender)


        cache_object = {
            "question_id": question_id,
            "session_id": session_id,
            "prompt": result_state["prompt"],
            "model": model_name,
            "ifc_file": row["ifc-file"],
            "model_output": model_output,
            "tool_calls": result_state["tool_calls"],
            "metrics": metrics,
            "input_tokens": result_state["input_tokens"],
            "output_tokens": result_state["output_tokens"],
            "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        }

        cache[question_id] = cache_object

        json.dump(cache, open("cache.json", "w"))

        print(f"Question {question_id + 1} processed with result state {result_state} at {datetime.now()}. Metrics: {metrics}")
        # TODO: put this together as a nice object and store somewhere for analysis

        os.remove(edited_ifc_path)

        input("Please prepare open Blender file so that the next question can be processed. Press enter to continue.")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
