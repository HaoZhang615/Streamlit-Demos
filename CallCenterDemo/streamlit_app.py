import streamlit as st

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    if st.button("Log in"):
        st.session_state.logged_in = True
        st.rerun()

def logout():
    if st.button("Log out"):
        st.session_state.logged_in = False
        st.rerun()

login_page = st.Page(login, title="Customer Contact Center Demo", icon=":material/login:")
logout_page = st.Page(logout, title="Log out", icon=":material/logout:")

self_service_page = st.Page("SelfServiceBot.py", title="Self Service Chatbot", icon="🧊")
ai_assisted_page = st.Page("AiAssistedBot.py", title="AI Assisted Chatbot", icon="🧊")

st.set_page_config(page_title="Customer Contact Center Demo", page_icon="🧊",layout="wide")

if st.session_state.logged_in:
    pg = st.navigation([self_service_page, ai_assisted_page])
else:
    pg = st.navigation([login_page])
    Customer_Name = st.selectbox("Sign in as:", 
                           ["Alex Richardson", 
                            "David Newman",
                            "Paula Smith",
                            "Wendy Miller",
                            "Yvonne Davis"], index=0)
    # switch logic to match the selected customer name to the customer_id 1 to 5 respectively
    if Customer_Name == "Alex Richardson":
        customer_id = 1
    elif Customer_Name == "David Newman":
        customer_id = 2
    elif Customer_Name == "Paula Smith":
        customer_id = 3
    elif Customer_Name == "Wendy Miller":
        customer_id = 4
    else:
        customer_id = 5
    st.session_state.customer_id = customer_id

pg.run() 