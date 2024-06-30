from azure.cosmos import CosmosClient, exceptions


# Azure Cosmos DB connection details
cosmos_endpoint = st.secrets["COSMOS_ENDPOINT"]
# cosmos_connection_string = st.secrets["COSMOS_CONNECTION_STRING"]
cosmos_key = st.secrets["COSMOS_KEY"]  
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database_name = st.secrets["COSMOS_DATABASE"]
database = cosmos_client.create_database_if_not_exists(id=database_name)  
customer_container_name = "Customer"
purchase_container_name = "Purchases"

def get_previous_purchases(customer_id):
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(purchase_container_name)

    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(container.query_items(query, enable_cross_partition_query=True))
        return items
    except exceptions.CosmosResourceNotFoundError:
        return []