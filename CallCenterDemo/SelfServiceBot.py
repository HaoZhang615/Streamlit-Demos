from openai import AzureOpenAI
from audio_recorder_streamlit import audio_recorder
import streamlit as st
# from cosmosdb_utils import CosmosDBChatMessageHistory
from azure.cosmos import CosmosClient, PartitionKey, exceptions
import uuid
import json
import requests
import io
import re

# Azure Open AI Configuration
api_base = st.secrets["AOAI_API_BASE"] # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
api_key = st.secrets["AOAI_API_KEY"]
api_version = "2024-02-01"
gpt4_o = st.secrets["AOAI_GPT4_MODEL"]
whisper = st.secrets["AOAI_WHISPER_MODEL"]
tts = st.secrets["AOAI_TTS_MODEL"]

session_customer_id = st.session_state.customer_id
client = AzureOpenAI(
    api_key=api_key,  
    api_version=api_version,
    azure_endpoint = api_base,
)
# st.set_page_config(
#     page_title="Azure OpenAI powered Self Service Chatbot",
#     page_icon="🧊",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# Function STT
def speech_to_text(audio:bytes)->str:
    # create a BytesIO object from the audio bytes
    buffer = io.BytesIO(audio)
    buffer.name = "audio.wav"
    result = client.audio.transcriptions.create(
        model=whisper,
        file= buffer,
    )
    # empty the buffer
    buffer.close()
    return result.text

# Function TTS
def text_to_speech(input:str):
    headers = {'Content-Type':'application/json', 'api-key': api_key}
    url = f"{api_base}openai/deployments/{tts}/audio/speech?api-version=2024-05-01-preview"
    body = {
        "input": input,
        "voice": "echo",
        "model": "tts",
        "response_format": "mp3"
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    return response.content

st.title("Azure OpenAI powered Self Service Chatbot")


# Sidebar Configuration -- BEGIN
with st.sidebar:
    # # Temperature and token slider
    # temperature = st.sidebar.slider(
    #     "Temperature",
    #     min_value=0.0,
    #     max_value=1.0,
    #     value=0.5,
    #     step=0.1
    # )
    # Max_Token = st.sidebar.slider(
    #     "Max. Tokens",
    #     min_value=10,
    #     max_value=4096,
    #     value=800,
    #     step=64
    # )
    # add toggle to turn on and off the audio player
    if "voice_on" not in st.session_state:
        st.session_state.voice_on = False
    st.session_state.voice_on = st.toggle(label="Enable Voice Output", value=st.session_state.voice_on)
    # dropdown for selecting the model with options for gpt-3.5 and gpt-4o, default is gpt-3.5. 
    # If gpt-3.5 is selected, the model is set to use value of secret AOAI_GPT35_MODEL, else it uses AOAI_GPT4_MODEL
    # model = st.selectbox("Select Model", ["gpt-3.5", "gpt-4o"], index=0)
    # if model == "gpt-3.5":
    #     model = st.secrets["AOAI_GPT35_MODEL"]
    # else:    
    #     model = st.secrets["AOAI_GPT4_MODEL"]
    # st.subheader("Custom recorder") # https://github.com/Joooohan/audio-recorder-streamlit/blob/main/audio_recorder_streamlit/__init__.py

    custom_audio_bytes = audio_recorder(
        text="Click the microphone to start recording\n",
        recording_color="#e8b62c",
        neutral_color="#6aa36f",
        icon_size="3x",
        sample_rate=41_000,
        auto_start=False,
    )
    
    if custom_audio_bytes:
        # st.audio(custom_audio_bytes, format="audio/wav")
        # call speech to text function and display the result
        st.session_state.voice_prompt = speech_to_text(custom_audio_bytes)
    # Function to clear chat history
    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.session_state.session_id = str(uuid.uuid4())

    if st.button("Restart Conversation :arrows_counterclockwise:"):
        clear_chat_history()
        st.session_state.voice_prompt = None
# Sidebar Configuration -- END

# Initialize session state attributes  
if "messages" not in st.session_state:  
    st.session_state.messages = []  
    st.session_state.session_id = str(uuid.uuid4())  # Unique session ID  
    print(st.session_state.session_id)
# Bing Custome Search Configuration
bing_api_key = st.secrets["BING_CUSTOM_SEARCH_API_KEY"]
bing_api_endpoint = st.secrets["BING_CUSTOM_SEARCH_API_ENDPOINT"]
custom_config_id = st.secrets["BING_CUSTOM_CONFIG_ID"] 


# Function to format the tools
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

# Function to search the web
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
        return results
    except Exception as ex:
        raise ex

# Function with function calling
def nestle_chat(user_request, conversation_history: list = []):
    system_message = """You are a helpful assistant that help people find information about Nestle and the major brands owned by it.
            IMPORTANT: It is crucial to contextualize first what is the user request really about based on user intent and chat history as your context, and then choose the function to use. Slow down and think step by step.
            Only call functions with arguments coming verbatim from the user or the output of other functions.
            Remind the user briefly at the end of your answer which web url you used to get the information.
            If the question is not related to Nestle, its products, or the brands Nestle owns, you can answer the question directly using your own knowledge without calling any function.
            If the question is about any of Nestle or its brands competitors, politely decline to answer.
            """
    customer_info = get_customer_info(session_customer_id)
    customer_info_str = json.dumps(customer_info, indent=4)
    system_message += f"Customer Information:\n{customer_info_str}"
    previous_purchases = get_previous_purchases(session_customer_id)
    previous_purchases_str = json.dumps(previous_purchases, indent=4)
    system_message += f"Previous Purchases the customer made:\n{previous_purchases_str}"
    messages=[
        {
            "role": "system",
            "content": system_message,
        }
        ]
    messages.extend(conversation_history)
    print(messages)
    # Step 1: send the conversation and available functions to the model
    messages.append({"role": "user", "content": user_request})
    response = client.chat.completions.create(
        model= gpt4_o,
        messages=messages,
        tools=tools_format(),
        tool_choice="auto",
        temperature=0.3,
        max_tokens=4000,
    )
    response_message = response.choices[0].message
    messages.append(response_message)  # Extend conversation with assistant's reply
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
            temperature=0.3,
            max_tokens=800,
        )
        return second_response.choices[0].message.content
    else:
        return response_message.content


# CosmosDB Configuration
cosmos_endpoint = st.secrets["COSMOS_ENDPOINT"]
# cosmos_connection_string = st.secrets["COSMOS_CONNECTION_STRING"]
cosmos_key = st.secrets["COSMOS_KEY"]  
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database_name = st.secrets["COSMOS_DATABASE"]
database = cosmos_client.create_database_if_not_exists(id=database_name)  
container_name = "AI_Conversations"  
customer_container_name = "Customer"
purchase_container_name = "Purchases"
container = database.create_container_if_not_exists(  
    id=container_name,   
    partition_key=PartitionKey(path="/customer_id"),  
    offer_throughput=400  
) 

def get_customer_info(customer_id):
    # Get the database and container
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(customer_container_name)

    try:
        # Query the container for the customer information
        query = f"SELECT * FROM c WHERE c.customer_id = {customer_id}"
        items = list(container.query_items(query, enable_cross_partition_query=True))
        
        if items:
            return items[0]
        else:
            return None
    except exceptions.CosmosResourceNotFoundError:
        return None
    
def get_previous_purchases(customer_id):
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(purchase_container_name)

    try:
        query = f"SELECT * FROM c WHERE c.customer_id = {customer_id}"
        items = list(container.query_items(query, enable_cross_partition_query=True))
        return items
    except exceptions.CosmosResourceNotFoundError:
        return []

# Function to save chat to Cosmos DB  
def save_chat(session_id, customer_id, messages):  
    document_id = f"chat_{session_id}"  # Create a document ID that is consistent throughout the session  
    try:  
        # Attempt to read the existing document  
        item = container.read_item(item=document_id, partition_key=customer_id)
        item['messages'] = messages  # Update the messages  
        container.replace_item(item=item, body=item)  
    except exceptions.CosmosResourceNotFoundError:  
        # If the document does not exist, create a new one  
        container.create_item({  
            'id': document_id,  
            'session_id': session_id,  
            'customer_id': customer_id,
            'messages': messages  
        })
  
# create a container with fixed height and scroll bar for conversation history
conversation_container = st.container(height = 600, border=False)
# Handle new message  
if text_prompt := st.chat_input("type your request here..."):
    prompt = text_prompt
elif custom_audio_bytes:
    prompt = st.session_state.voice_prompt
else:
    prompt = None

with conversation_container:
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display the conversation history
        for message in st.session_state.messages:
            if message["role"] != "system":  
                with st.chat_message(message["role"]):  
                    st.markdown(message["content"]) 
        with st.chat_message("assistant"):  
            result= nestle_chat(prompt, st.session_state.messages)
            audio_text = re.sub(r'\([^)]*\)', '', result)
            # trim the result to remove all occurances of text wrapped within brackets, e.g. (source_page: "Nestle") and (source_url: "https://www.nestle.com/")
            st.markdown(result)
            if st.session_state.voice_on:
                st.audio(text_to_speech(audio_text), format="audio/mp3", autoplay=True)
        st.session_state.messages.append({"role": "assistant", "content": result}) 
        save_chat(st.session_state.session_id, session_customer_id, st.session_state.messages)  # Save the session 