import streamlit as st
from openai import AzureOpenAI
import json
import os
import sys
import time
from pathlib import Path
import requests

st.set_page_config(
    layout="wide"
)
def clear_chat_history():
    st.session_state.messages = []
    st.session_state.chat_history = []

col1, col2, col3= st.columns([5, 1, 1])
with col1:
    st.title("GraphRAG on Annual Reports of Baloise and Helvetia")
with col2:
    query_mode = st.selectbox("choose query mode", ["local", "global"], index=0)
with col3:
    if st.button("Restart Conversation :arrows_counterclockwise:"):
        clear_chat_history()



# Initialize session state attributes  
if "messages" not in st.session_state:  
    st.session_state.messages = []  

# Azure APIM Configuration
ocp_apim_subscription_key = st.secrets["APIM_KEY"] # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/

# Azure Open AI Configuration
api_base = st.secrets["AOAI_API_BASE"] # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
api_key = st.secrets["AOAI_API_KEY"]
api_version = "2024-02-01"
gpt4_o = st.secrets["AOAI_GPT4_MODEL"]

client = AzureOpenAI(
    api_key=api_key,  
    api_version=api_version,
    azure_endpoint = api_base,
)
# Other configurations
headers = {"Ocp-Apim-Subscription-Key": ocp_apim_subscription_key}
index_name = st.secrets["GRAPHRAG_INDEX_NAME"]
endpoint = st.secrets["APIM_ENDPOINT"]

# Helper Functions  
def global_search(index_name: str | list[str], query: str) -> requests.Response:
    """Run a global query over the knowledge graph(s) associated with one or more indexes"""
    url = endpoint + "/query/global"
    request = {"index_name": index_name, "query": query}
    return requests.post(url, json=request, headers=headers)

def local_search(index_name: str | list[str], query: str) -> requests.Response:
    """Run a local query over the knowledge graph(s) associated with one or more indexes"""
    url = endpoint + "/query/local"
    request = {"index_name": index_name, "query": query}
    return requests.post(url, json=request, headers=headers)


def get_graph_stats(index_name: str) -> requests.Response:
    """Get basic statistics about the knowledge graph constructed by GraphRAG."""
    url = endpoint + f"/graph/stats/{index_name}"
    return requests.get(url, headers=headers)


def save_graphml_file(index_name: str, graphml_file_name: str) -> None:
    """Retrieve and save a graphml file that represents the knowledge graph.
    The file is downloaded in chunks and saved to the local file system.
    """
    url = endpoint + f"/graph/graphml/{index_name}"
    if Path(graphml_file_name).suffix != ".graphml":
        raise UserWarning(f"{graphml_file_name} must have a .graphml file extension")
    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(graphml_file_name, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024):
                f.write(chunk)

def parse_query_response(
    response: requests.Response, return_context_data: bool = False
) -> requests.Response | dict[list[dict]]:
    """
    Prints response['result'] value and optionally
    returns associated context data.
    """
    if response.ok:
        # print(json.loads(response.text)["result"])
        if return_context_data:
            return json.loads(response.text)["context_data"]
        return response
    else:
        # print(response.reason)
        # print(response.content)
        return response

def global_query(index_name: str | list[str], query: str) -> requests.Response:
    global_response = global_search(
        index_name=index_name, query="Summarize the main topics of this data"
    )
    # print the result and save context data in a variable
    global_response_data = parse_query_response(global_response, return_context_data=True)
    return global_response_data

def query_rewrite(existing_messages):
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant. You do not repeat the user's request in your reply and you answer in a very laconic way",
        },
        {
            "role": "user",
            "content": f"rewrite the user's last question into a contextualized query based on an given conversation history below (if there is only one user question, do not rewrite it and return the exact same question): \n\n. {json.dumps(existing_messages)}",
        },
        ]
    completion = client.chat.completions.create(
    model=gpt4_o,
    temperature=0.2,
    max_tokens=100,
    messages=messages,
)
    print(completion.choices[0].message.content)
    return completion.choices[0].message.content

# define a container to hold the conversation history
conversation_container = st.container(height = 750, border=False)
if text_prompt := st.chat_input("type your request here..."):
    prompt = text_prompt
else:
    prompt = None

# Display chat history  
with conversation_container:
    # Handle new message  
    if prompt:  
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display the conversation history
        for message in st.session_state.messages:
            if message["role"] != "system":  
                with st.chat_message(message["role"]):  
                    st.markdown(message["content"]) 
        with st.chat_message("assistant"):  
            contextualized_query = query_rewrite(st.session_state.messages)
            if query_mode == "global":
                result = global_search(index_name, contextualized_query)
            else:
                result = local_search(index_name, contextualized_query)
            response = json.loads(result.text)["result"]
            st.session_state.messages.append({"role": "assistant", "content": response})  
            st.markdown(response)