from openai import AzureOpenAI
import streamlit as st
import hashlib
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from eval_scripts.evaluate import *
import datetime
import pandas as pd
import logging

# # Configure logging
# logging.basicConfig(level=logging.DEBUG)

st.set_page_config(
    page_title="Azure OpenAI RAG Chat Evaluator",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("Azure OpenAI RAG Chat Evaluator")

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
container_name = st.secrets["COSMOS_CONTAINER_RAG_EVALUATOR"]  
container = database.create_container_if_not_exists(  
    id=container_name,   
    partition_key=PartitionKey(path="/rag_app_id"),  
    # offer_throughput=400  
) 

config = {}

# MD5 hash function to hash the URL
def md5_hash_string(input_string):
    # Create an MD5 hash object
    md5_hash = hashlib.md5()
    
    # Update the hash object with the bytes of the string
    md5_hash.update(input_string.encode('utf-8'))
    
    # Return the hexadecimal representation of the hash
    return md5_hash.hexdigest()

# Function to count number of documents in Cosmos DB container where the "target_url" is the same as the URL input parameter
def count_documents(URL):
    # hash the URL to get the rag_app_id
    rag_app_id = md5_hash_string(URL)
    query = f"SELECT VALUE COUNT(1) FROM c WHERE c.rag_app_id = '{rag_app_id}'"
    result = list(container.query_items(query=query, enable_cross_partition_query=True))
    return result[0]

# Function to save chat to Cosmos DB  
def save_result(URL, eval_results):  
    rag_app_id = md5_hash_string(URL)  # Create a hash of the URL to use as the partition key
    run_id = count_documents(URL) + 1  # Get the number of documents with the same URL and increment by 1
    payload = {
        "id": f"{rag_app_id}_{run_id}",
        'run_id': run_id,  
        'rag_app_id': rag_app_id,
        'eval_results': eval_results
    }
    logging.debug("Payload to be sent to Cosmos DB: %s", json.dumps(payload, indent=2))

    try:
        container.create_item(payload)
    except Exception as e:
        logging.error("Failed to save result to Cosmos DB: %s", str(e))
        raise

# Sidebar Configuration
with st.sidebar:
    URL = st.sidebar.text_input("URL of your RAG Chat App", "https://app-backend-url.azurewebsites.net/chat")
    Truth_JSONL = st.sidebar.file_uploader("Upload the JSONL file with the ground truth data", type=["jsonl"])
    # dropdown for multiple selecting the evaluation metrics from options: "gpt_groundedness", "gpt_relevance", "gpt_coherence", "gpt_similarity", default is select all. 
    metric_list = st.sidebar.multiselect("Select the evaluation metrics", ["gpt_similarity", "gpt_groundedness", "gpt_relevance", "gpt_coherence", "gpt_fluency"], 
                                         ["gpt_similarity", "gpt_groundedness", "gpt_relevance", "gpt_coherence", "gpt_fluency"])
    # a dotted line to seperate a new section
    st.markdown("---")
    # a header for the configuration section
    st.header("RAG Chat Configuration")
    # Temperature slider
    temperature = st.sidebar.slider(
        "New Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.3,
        step=0.1
    )
    # true/false radio button to define if the chatbot should use semantic ranker
    use_semantic_ranker = st.sidebar.radio("Use Semantic Ranker", ("Yes", "No"))
    # retrieval documents number slider
    top_n_documents = st.sidebar.slider(
        "Top N Documents to retrieve",
        min_value=1,
        max_value=50,
        value=10,
        step=1
    )
    # dropdown for selecting the retrieval mode: "text", "vectors" or "hybrid"
    retrieval_mode = st.sidebar.selectbox("Query Type", ["text", "vectors", "hybrid"])

    # add submit button to update the config variable with the new values from the sidebar
    if st.sidebar.button("Submit"):
        target_parameters = {
                "top": top_n_documents,
                "temperature": temperature,
                "retrieval_mode": retrieval_mode,
                "semantic_ranker": True if use_semantic_ranker == "Yes" else False
                }
        eval_results = run_evaluation(
             openai_config=service_setup.get_openai_config(),
             target_url = URL,
             test_data_BytesIO = Truth_JSONL, 
             requested_metrics = metric_list,
             target_parameters = target_parameters
             )
        # st.write(eval_results) for debugging
        save_result(URL, eval_results)

# Query the evaluation results of all documents in the Cosmos DB container where the "target_url" is the same as the URL input parameter
query = f"SELECT * FROM c WHERE c.rag_app_id = '{md5_hash_string(URL)}'"
results = list(container.query_items(query=query, enable_cross_partition_query=True))
if len(results) > 0:
    # Extract relevant fields and convert them to a new list
    sub_results_list = []
    for result in results:
        eval_results = result.get("eval_results", {})
        target_parameters = eval_results.get("target_parameters", {})
        metrics_summary = eval_results.get("metrics_summary", {})

        sub_result = {
            "run_id": result.get("run_id", "N/A"),
            "target_url": eval_results.get("target_url", "N/A"),
            "evaluation_timestamp": datetime.datetime.fromtimestamp(
                eval_results.get("evaluation_timestamp", 0)
            ).strftime('%Y-%m-%d %H:%M:%S') if eval_results.get("evaluation_timestamp") else "N/A",
            "top": target_parameters.get("top", "N/A"),
            "temperature": target_parameters.get("temperature", "N/A"),
            "retrieval_mode": target_parameters.get("retrieval_mode", "N/A"),
            "semantic_ranker": target_parameters.get("semantic_ranker", "N/A"),
            "num_questions": eval_results.get("num_questions", "N/A"),
            # Flattened metrics_summary
            "groundedness_pass_count": metrics_summary.get("gpt_groundedness", {}).get("pass_count", "N/A"),
            "groundedness_pass_rate": metrics_summary.get("gpt_groundedness", {}).get("pass_rate", "N/A"),
            "groundedness_mean_rating": metrics_summary.get("gpt_groundedness", {}).get("mean_rating", "N/A"),
            "coherence_pass_count": metrics_summary.get("gpt_coherence", {}).get("pass_count", "N/A"),
            "coherence_pass_rate": metrics_summary.get("gpt_coherence", {}).get("pass_rate", "N/A"),
            "coherence_mean_rating": metrics_summary.get("gpt_coherence", {}).get("mean_rating", "N/A"),
            "relevance_pass_count": metrics_summary.get("gpt_relevance", {}).get("pass_count", "N/A"),
            "relevance_pass_rate": metrics_summary.get("gpt_relevance", {}).get("pass_rate", "N/A"),
            "relevance_mean_rating": metrics_summary.get("gpt_relevance", {}).get("mean_rating", "N/A"),
            "fluency_pass_count": metrics_summary.get("gpt_fluency", {}).get("pass_count", "N/A"),
            "fluency_pass_rate": metrics_summary.get("gpt_fluency", {}).get("pass_rate", "N/A"),
            "fluency_mean_rating": metrics_summary.get("gpt_fluency", {}).get("mean_rating", "N/A")
        }
        sub_results_list.append(sub_result)
    df = pd.DataFrame(sub_results_list)
    # Display the table in Streamlit
    # Inject custom CSS for smaller title font size
    st.markdown(
        """
        <style>
        .title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Display the title with smaller font size
    st.markdown('<div class="title">Evaluation Results Summary</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
