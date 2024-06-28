import json
import os
import requests
from collections.abc import Callable
from openai import AzureOpenAI
from openai import BadRequestError
import logging
from dotenv import load_dotenv
from pprint import pprint
load_dotenv()


bing_api_key = os.getenv("BING_CUSTOM_SEARCH_API_KEY")
bing_api_endpoint = os.getenv("BING_CUSTOM_SEARCH_API_ENDPOINT")
custom_config_id = os.getenv("BING_CUSTOM_CONFIG_ID") 

def tools_format() -> list:
        tools = [
            {
                "type": "function",
                "function":{            
                    "name": "search_web",
                    "description": "use this function to search information on the web. Mandatory when the user asks for any questions related to Nestle, its products, or the brands Nestle owns.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "the rephrased user request considering the conversation history, in concise search terms that works efficiently in Bing Search.",
                            },
                            "up_to_date": {
                                "type": "boolean",
                                "default": False,
                                "description": "indicator of whether or not the up-to-date information is needed.",
                            },
                        },
                        "required": ["user_request"],
                    },
                }
            },
        ]
        return tools
def search_web(query, up_to_date:bool=False):

    headers = {"Ocp-Apim-Subscription-Key": bing_api_key}
    params = {"q": query, 'customconfig': custom_config_id, "count": 5}  # Limit the results to 5
    url = bing_api_endpoint
    if up_to_date:
            params.update({"sortby":"Date"})
    try:
        response = requests.get(url, headers=headers,params = params, timeout=10)
        print(params)
        response.raise_for_status()
        search_results = response.json()
        results = []
        if search_results is not None:
            for v in search_results["webPages"]["value"]:
                result = {
                    "source_page": v["name"],
                    "content": v["snippet"],
                    "source_url": v["url"]
                }
                results.append(result)
            return [
                        {"content": doc["content"],
                        "source_page": doc["source_page"],
                        "source_url":doc["source_url"]}
                        for doc in results]
        return results
    except Exception as ex:
        raise ex

def nestle_chat(user_request, conversation_history: list = []):
    # For local test
    load_dotenv()
    api_base = os.getenv("AOAI_API_BASE")
    api_key = os.getenv("AOAI_API_KEY")
    api_version = os.environ["AOAI_API_VERSION"]
    gpt4_o = os.getenv("GPT4_MODEL_NAME")

    # instantiate the AzureOpenAI client
    client = AzureOpenAI(
        api_key=api_key,  
        api_version=api_version,
        azure_endpoint = api_base,
    )
    messages = [
        {
            "role": "system",
            "content": """You are a helpful assistant that help people find information about Nestle and the major brands owned by it.
            IMPORTANT: It is crucial to contextualize first what is the user request really about based on user intent and chat history as your context, and then choose the function to use. Slow down and think step by step.
            You can answer multistep questions by sequentially calling functions. Follow a pattern of 
                THOUGHT (reason step-by-step about which function to call next), 
                ACTION (call a function to as a next step towards the final answer), 
                OBSERVATION (output of the function). Reason step by step which actions to take to get to the answer. 
            Only call functions with arguments coming verbatim from the user or the output of other functions.
            """,
        }]
    messages.extend(conversation_history)
    pprint(messages)
    # Step 1: send the conversation and available functions to the model
    messages.append({"role": "user", "content": user_request})
    pprint(messages)
    response = client.chat.completions.create(
        model= gpt4_o,
        messages=messages,
        tools=tools_format(),
        tool_choice="auto",
        temperature=0.6,
        max_tokens=4000,
    )
    response_message = response.choices[0].message
    messages.append(response_message)  # Extend conversation with assistant's reply
    pprint(messages)
    # Check if GPT wanted to call a function
    tool_calls = response_message.tool_calls
    if tool_calls:
        # Step 3: call the function
        available_functions = {
        "search_web": search_web,
    }
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            # Validate function name
            if function_name not in available_functions:
                print(f"Invalid function name: {function_name}")
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": f"Invalid function name: {function_name!r}",
                    }
                )
                continue
            # Get the function to call
            function_to_call = available_functions[function_name]
            # Try getting the function arguments
            try:
                function_args_dict = json.loads(tool_call.function.arguments)
                pprint(function_args_dict)
            except json.JSONDecodeError as exc:
                # JSON decoding failed
                print(f"Error decoding function arguments: {exc}")
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": f"Error decoding function call `{function_name}` arguments {tool_call.function.arguments!r}! Error: {exc!s}",
                    }
                )
                continue
            # Call the selected function with generated arguments
            try:
                function_response = function_to_call(**function_args_dict)
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(function_response, ensure_ascii=False),
                    }
                )
                pprint(messages)
            except Exception as exc:
                # Function call failed
                print(f"Function call failed: {exc}")
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": f"Function call `{function_name}` failed with arguments {function_args_dict!r}! Error: {exc!s}",
                    }
                )
                continue
        second_response = client.chat.completions.create(
            model= gpt4_o,
            messages=messages,
            temperature=0.6,
            max_tokens=4000,
        )
        return second_response.choices[0].message.content

nestle_chat("What is the latest news about Nestle?")

        
