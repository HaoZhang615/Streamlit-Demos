# Code refactored from https://docs.streamlit.io/knowledge-base/tutorials/build-conversational-apps
import streamlit as st
import requests
import json
import base64
import mimetypes
from openai import OpenAI

st.set_page_config(
    page_title="Prometheus Assistant",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    # input box for user to enter their Azure Function Endpoint
    if 'Az_Function_Endpoint' in st.secrets:
        st.success('Azure Function Endpoint already provided!', icon='✅')
        url = st.secrets['Az_Function_Endpoint']
    else:
        url = st.text_input('Enter Azure Function Endpoint:', type='password')

    # Button to clear chat history
    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.chat_history = []
    if st.button("Restart Conversation :arrows_counterclockwise:"):
        clear_chat_history()


st.title('Prometheus Assistant')  # Add your title


# check if the "messages" session state exists, if not, create it as an empty list
if "messages" not in st.session_state:
    st.session_state.messages = []
# check if the "chat_history" session state exists, if not, create it as an empty list
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# create a container with fixed height and scroll bar for conversation history
conversation_container = st.container(height = 600, border=False)

# create an input text box where the user can enter their prompt
if text_prompt := st.chat_input("type your request here..."):
    with conversation_container:
        st.session_state.messages.append({"role": "user", "content": text_prompt})
        # iterate over the messages in the session state and display them
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])  # Render markdown with images
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            data = {
                "chat_input": text_prompt,
                "chat_history": st.session_state.chat_history
            }
            # headers = {'Content-Type':'application/json', 'Authorization':('Bearer '+ api_key), 'azureml-model-deployment': model_name}
            response = requests.get(url, json=data)
            #print(response.json())
            response_json = response.json()
            message_placeholder.markdown(response_json, unsafe_allow_html=True)  # Render markdown with images
            data["chat_history"].append(
                {
                    "inputs": {
                        "chat_input": text_prompt
                    },
                    "outputs": {
                        "chat_output": response_json,
                    }
                }
            )
            st.session_state.chat_history = data["chat_history"]
            message_placeholder.markdown(response_json, unsafe_allow_html=True)  # Render markdown with images
        st.session_state.messages.append({"role": "assistant", "content": response_json})