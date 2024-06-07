from openai import OpenAI
import streamlit as st

st.title("Chatbot with OpenAI GPT-3.5 in streaming mode")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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
        min_value=64,
        max_value=2048,
        value=256,
        step=64
    )
    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.chat_history = []
    if st.button("Restart Conversation :arrows_counterclockwise:"):
        clear_chat_history()

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
            temperature=temperature,
            max_tokens=Max_Token
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})