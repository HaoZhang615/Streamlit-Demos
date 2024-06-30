import streamlit as st
from azure.cosmos import CosmosClient, exceptions
from openai import AzureOpenAI
import json

st.set_page_config(
    page_title="Azure AI assisted Customer Contact Center",
    page_icon="🧊",
    layout="wide",
    # initial_sidebar_state="expanded"
)
# Set the title of the app
st.title("AI Assisted Live Chat with Forwarded Customer Conversation")

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

# Azure Cosmos DB connection details
cosmos_endpoint = st.secrets["COSMOS_ENDPOINT"]
# cosmos_connection_string = st.secrets["COSMOS_CONNECTION_STRING"]
cosmos_key = st.secrets["COSMOS_KEY"]  
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database_name = st.secrets["COSMOS_DATABASE"]
database = cosmos_client.create_database_if_not_exists(id=database_name)  
customer_container_name = "Customer"
purchase_container_name = "Purchases"
ai_conversations_container_name = "AI_Conversations"

def get_customer_info(customer_id):
    # Get the database and container
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(customer_container_name)

    try:
        # Query the container for the customer information
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
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
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(container.query_items(query, enable_cross_partition_query=True))
        return items
    except exceptions.CosmosResourceNotFoundError:
        return []
    
def display_customer_info(customer_info):
    if customer_info:
        left, right = st.columns(2)
        with left:
            st.write(f"**Customer ID:** {customer_info['customer_id']}")
            st.write(f"**Name:** {customer_info['first_name']} {customer_info['last_name']}")
            st.write(f"**Email:** {customer_info['email']}")
        with right:
            st.write(f"**Phone Number:** {customer_info['phone_number']}")
            st.write("**Address:**")
            st.write(f"{customer_info['address']['street']}, "
                     f"{customer_info['address']['city']}, "
                     f"{customer_info['address']['postal_code']}, "
                     f"{customer_info['address']['country']}")
    else:
        st.write("Customer information not found.")

def display_product_details(product_details):
    for key, value in product_details.items():
        st.write(f"**{key.replace('_', ' ').capitalize()}:** {value}")

def display_previous_purchases(purchases):
    if purchases:
        cols = st.columns(len(purchases))
        for idx, purchase in enumerate(purchases):
            with cols[idx]:
                st.write(f"**Order Number:** {purchase['order_number']}")
                st.write("**Product Details:**")
                display_product_details(purchase['product_details'])
                st.write(f"**Quantity:** {purchase['quantity']}")
                st.write(f"**Total Price:** ${purchase['total_price']:.2f}")
                st.write(f"**Purchase Date:** {purchase['purchasing_date']}")
                st.write(f"**Delivered Date:** {purchase['delivered_date']}")
                st.write("---")
    else:
        st.write("No previous purchases found.")

def get_prior_conversation(customer_id):
    client = CosmosClient(cosmos_endpoint, cosmos_key)
    database = client.get_database_client(database_name)
    container = database.get_container_client(ai_conversations_container_name)

    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}' ORDER BY c._ts DESC"
        items = list(container.query_items(query, enable_cross_partition_query=True, max_item_count=1))
        if items:
            return items[0]
        else:
            return None
    except exceptions.CosmosResourceNotFoundError:
        return None

def summarize_conversation(messages):
    system_message = """
"You are a helpful customer service representative who is good at looking at a prior customer-agent conversation and 
provide a key-points based summary with the key-points being: 'Issue Reported', 'Already provided help', 'user expectation as next' and 'converstaion language'."""
    prompt = "Summarize the following conversation:\n\n"
    for message in messages:
        prompt += f"{message['role'].capitalize()}: {message['content']}\n"
    completion = client.chat.completions.create(
    model=gpt4_o,
    temperature=0.0,
    max_tokens=300,
    messages=[
        {
            "role": "system",
            "content": system_message,
        },
        {
            "role": "user",
            "content": prompt,
        }
    ],
)
    return completion.choices[0].message.content

def display_prior_conversation_summary(summary):
    st.write(f"{summary}")

def generate_recommended_reply(customer_id):
    system_message = """
You are a senior customer service representative who is good at giving next-turn reply to keep an engaging conversation. You got forwarded an existing customer service conversation done by another junior representative with extended context of customer information and previous purchases.
In your response, you always begins with a warm greeting addressing the customer's first name directly like 'Hi <first_name>'. This is a live chat so do expect a quick response from the customer, do not reply like the customer is offline.
The existing conversation:\n\n"""
    prior_conversation = get_prior_conversation(customer_id)
    for message in prior_conversation['messages']:
        system_message += f"{message['role'].capitalize()}: {message['content']}\n"
    customer_info = get_customer_info(customer_id)
    customer_info_str = json.dumps(customer_info, indent=4)
    system_message += f"Customer Information:\n{customer_info_str}"
    previous_purchases = get_previous_purchases(customer_id)
    previous_purchases_str = json.dumps(previous_purchases, indent=4)
    system_message += f"Previous Purchases:\n{previous_purchases_str}"
    prompt = "Based on the conversation and extended content, provide a recommended reply to the customer.\n\n"
    completion = client.chat.completions.create(
    model=gpt4_o,
    temperature=0.5,
    max_tokens=800,
    messages=[
        {
            "role": "system",
            "content": system_message,
        },
        {
            "role": "user",
            "content": prompt,
        }
    ],
)
    return completion.choices[0].message.content

# Define the layout with columns
left_col, right_col = st.columns([1, 2])

# Add components to the left column
with left_col:
    st.subheader("Customer Information")
    customer_id = st.text_input("Enter Customer ID")

    if customer_id:
        customer_info = get_customer_info(customer_id)
        display_customer_info(customer_info)

        st.subheader("Previous Purchases")
        purchases = get_previous_purchases(customer_id)
        display_previous_purchases(purchases)

        st.subheader("Summary of Prior Conversation")
        conversation = get_prior_conversation(customer_id)
        if conversation:
            summary = summarize_conversation(conversation['messages'])
            display_prior_conversation_summary(summary)
        else:
            st.write("No prior conversation found.")
    else:
        st.write("Please enter a customer ID to fetch the information.")

# Add components to the right column
with right_col:
    st.subheader("Recommended Reply")
    if customer_id:
        recommended_reply = generate_recommended_reply(customer_id)
        st.text_area("Recommended Reply", recommended_reply, height=200)
    else:
        st.write("Please enter a customer ID to generate a recommended reply.")

    st.subheader("Live Chat")
    st.image("Picture1.png", caption="Live Chat Interface", use_column_width=True)