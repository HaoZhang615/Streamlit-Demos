import streamlit as st

# Define the text_area widget
text_box = st.text_area('Text Area', value='Hey, how are you today?')

# Display the value of text_box
st.chat_input(st.text(text_box))