from openai import AzureOpenAI
import streamlit as st
# from cosmosdb_utils import CosmosDBChatMessageHistory
from azure.cosmos import CosmosClient, PartitionKey, exceptions
import uuid  

st.title("Azure OpenAI Chatbot in streaming mode")

# Initialize session state attributes  
if "messages" not in st.session_state:  
    st.session_state.messages = []  
    st.session_state.session_id = str(uuid.uuid4())  # Unique session ID  
    print(st.session_state.session_id)

# Azure Open AI Configuration
api_base = st.secrets["AOAI_API_BASE"] # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
api_key = st.secrets["AOAI_API_KEY"]
api_version = "2024-02-01"
client = AzureOpenAI(
    api_key=api_key,  
    api_version=api_version,
    azure_endpoint = api_base,
)

# CosmosDB Configuration
cosmos_endpoint = st.secrets["COSMOS_ENDPOINT"]
# cosmos_connection_string = st.secrets["COSMOS_CONNECTION_STRING"]
cosmos_key = st.secrets["COSMOS_KEY"]  
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database_name = st.secrets["COSMOS_DATABASE"]
database = cosmos_client.create_database_if_not_exists(id=database_name)  
container_name = st.secrets["COSMOS_CONTAINER"]  
container = database.create_container_if_not_exists(  
    id=container_name,   
    partition_key=PartitionKey(path="/user_id"),  
    offer_throughput=400  
) 

user_id = st.secrets["COSMOS_USER_ID"]  # Ensure a user-specific identification logic if needed  

# Function to save chat to Cosmos DB  
def save_chat(session_id, user_id, messages):  
    document_id = f"chat_{session_id}"  # Create a document ID that is consistent throughout the session  
    try:  
        # Attempt to read the existing document  
        item = container.read_item(item=document_id, partition_key=user_id)
        item['messages'] = messages  # Update the messages  
        container.replace_item(item=item, body=item)  
    except exceptions.CosmosResourceNotFoundError:  
        # If the document does not exist, create a new one  
        container.create_item({  
            'id': document_id,  
            'session_id': session_id,  
            'user_id': user_id,  
            'messages': messages  
        })

# Sidebar Configuration
with st.sidebar:
    # Temperature and token slider
    temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.1
    )
    Max_Token = st.sidebar.slider(
        "Max. Tokens",
        min_value=10,
        max_value=4096,
        value=256,
        step=64
    )
    # dropdown for selecting the model with options for gpt-3.5 and gpt-4, default is gpt-3.5. 
    # If gpt-3.5 is selected, the model is set to use value of secret AOAI_GPT35_MODEL, else it uses AOAI_GPT4_MODEL
    model = st.selectbox("Select Model", ["gpt-3.5", "gpt-4"], index=0)
    if model == "gpt-3.5":
        model = st.secrets["AOAI_GPT35_MODEL"]
    else:    
        model = st.secrets["AOAI_GPT4_MODEL"]

    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.chat_history = []
    if st.button("Restart Conversation :arrows_counterclockwise:"):
        clear_chat_history()
  
# Display chat history  
for message in st.session_state.messages:  
    with st.chat_message(message["role"]):  
        st.markdown(message["content"])  
  
# Handle new message  
if prompt := st.chat_input("What is up?"):  
    st.session_state.messages.append({"role": "user", "content": prompt})  
    with st.chat_message("user"):  
        st.markdown(prompt)  
    with st.chat_message("assistant"):  
        stream = client.chat.completions.create(  
            model=model,  
            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],  
            stream=True,  
            temperature=temperature,  
            max_tokens=Max_Token  
        )  
        response = st.write_stream(stream)  
        st.session_state.messages.append({"role": "assistant", "content": response})  
        # st.markdown(st.session_state.session_id)
        save_chat(st.session_state.session_id, user_id, st.session_state.messages)  # Save the session 
