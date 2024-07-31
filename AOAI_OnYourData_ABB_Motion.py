from openai import AzureOpenAI
import streamlit as st
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType,VectorizedQuery
from azure.core.credentials import AzureKeyCredential
import os
from dotenv import load_dotenv
import json

st.title("基于自有数据的 Azure OpenAI 知识库问答 - ABB Motion")

# Initialize session state attributes  
if "messages" not in st.session_state:  
    st.session_state.messages = [] 

# AOAI Configuration
endpoint = st.secrets["AOAI_API_BASE"]
key = st.secrets["AOAI_API_KEY"]
deployment = st.secrets["AOAI_GPT4_MODEL"]
embedding_deployment = st.secrets["AOAI_EMBEDDING_MODEL"]
search_endpoint = st.secrets["AZURE_AI_SEARCH_SERVICE_ENDPOINT"]
search_key = st.secrets["AZURE_AI_SEARCH_ADMIN_KEY"]
search_index = st.secrets["AZURE_AI_SEARCH_INDEX_NAME_ABB"]
search_semantic_config = st.secrets["AZURE_AI_SEARCH_SEMANTIC_CONFIG_NAME"]
# instantiate the AzureOpenAI client
client = AzureOpenAI(
    api_key=key,  
    api_version="2024-02-01",
    azure_endpoint = endpoint,
)

# tools as list of functions to use Azure AI Search to built RAG pattern for QA on the files
def tools_format() -> list:
    tools = [
        {
            "type": "function",
            "function":{            
                "name": "search_internal_knowledge_bases",
                "description": "use this function when the user request can be fulfilled by searching internal knowledge bases which contain 550 PDF pages of technical specifications and 50 Q&A list of ACS880 machine.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {
                            "type": "string",
                            "description": "the user question. If it is a follow-up question, rephrase it to include the context of the previous conversation.",
                        },
                    },
                    "required": ["user_request"],
                },
            },
        }
      ]
    return tools

# function to embedd the question
def embedd_question(question: str):
  model = embedding_deployment
  response = client.embeddings.create(input=question, model=model).data[0].embedding
  return response

# function to use Azure AI Search to built RAG pattern for QA on the files
def search_internal_knowledge_bases(user_request:str):
        ikb_api_base = os.getenv("AZURE_AI_SEARCH_SERVICE_ENDPOINT")
        ikb_api_key = os.getenv("AZURE_AI_SEARCH_ADMIN_KEY")
        ikb_search_index = os.getenv("AZURE_AI_SEARCH_INDEX_NAME_ABB")
        semantic_config_name = os.getenv("AZURE_AI_SEARCH_SEMANTIC_CONFIG_NAME")

        search_client = SearchClient(endpoint=ikb_api_base,
                                        index_name=ikb_search_index,
                                        credential=AzureKeyCredential(ikb_api_key))
        question = user_request
        vector_query = VectorizedQuery(vector=embedd_question(question), k_nearest_neighbors=10, fields="embedding")
        results = search_client.search(
            search_text=question,
            semantic_configuration_name=search_semantic_config,
            query_type=QueryType.SEMANTIC,
            top=10,
            select=["content","source","category"],
            vector_queries=[vector_query],
        ) 
        results_list = [
            {
            "content": doc["content"],
            "source": doc["source"],
            "category": doc["category"],
            "search_score": doc["@search.score"]
            }
        for doc in results]

        # Sort the results by search_score in descending order
        sorted_results = sorted(results_list, key=lambda x: x['search_score'], reverse=True)

        # loop through the sorted results and check if there is any source value that starts with "FAQ", if so return the top 1 result, else return the top 5 results
        for result in sorted_results:
            if result["source"].startswith("FAQ"):
                return result
        return sorted_results[:5]

# final function to call Azure OpenAI using function calling to search_internal_knowledge_bases
def aoai_on_your_data(query):
    messages = [
            {
                "role": "system",
                "content": f"""
    You are a helpful assistant that helps the user with their request regarding ABB's machine: ACS880.
    You have access to a set of tools/functions that helps the user searches internal knowledge base.
    Only call functions with arguments coming verbatim from the user or the output of other functions.
    When providing the answer based on internal knowledge base search result, always reply in Chinese language as the user request and you answer with citations on the use sources.
    """}]
    # append the user request to the messages
    messages.append({"role": "user", "content": query})
    #messages = [{"role": "user", "content": "What's the current time in San Francisco, Tokyo, and Paris?"}] # Parallel function call with a single tool/function defined

    # Define the function for the model
    tools = tools_format()

    # First API call: Ask the model to use the function
    response = client.chat.completions.create(
        model=deployment,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    # Process the model's response
    response_message = response.choices[0].message
    messages.append(response_message)

    # Handle function calls
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "search_internal_knowledge_bases":
                function_args = json.loads(tool_call.function.arguments)
                user_request = function_args.get("user_request")
                kb_search_response = search_internal_knowledge_bases(user_request)
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": "search_internal_knowledge_bases",
                    "content": json.dumps(kb_search_response),
                })
    else:
        print("No tool calls were made by the model.")  

    # Second API call: Get the final response from the model
    final_response = client.chat.completions.create(
        model=deployment,
        messages=messages,
    )

    return final_response.choices[0].message.content

# Sidebar Configuration
with st.sidebar:
    # Temperature and token slider
    temperature = st.sidebar.slider(
        "模型温度",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.1
    )
    Max_Token = st.sidebar.slider(
        "最大token限制",
        min_value=10,
        max_value=120000,
        value=256,
        step=64
    )

    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.chat_history = []
    if st.button("重新开始对话 :arrows_counterclockwise:"):
        clear_chat_history()
  

for message in st.session_state.messages:  
    with st.chat_message(message["role"]):  
        st.markdown(message["content"])  
  
# Handle new message  
if prompt := st.chat_input(f"请提问关于ABB的ACS880机器的问题"):
    # Display chat history  
    st.session_state.messages.append({"role": "user", "content": prompt})  
    with st.chat_message("user"):  
        st.markdown(prompt)  
    with st.chat_message("assistant"): 
        result = aoai_on_your_data(prompt)
        st.markdown(result)
    st.session_state.messages.append({"role": "assistant", "content": result})  