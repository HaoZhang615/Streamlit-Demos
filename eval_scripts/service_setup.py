import logging
import os
import streamlit as st
import openai
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from promptflow.core import AzureOpenAIModelConfiguration, ModelConfiguration, OpenAIModelConfiguration

logger = logging.getLogger("scripts")

azure_endpoint = st.secrets["AOAI_API_BASE"]
api_key = st.secrets["AOAI_API_KEY"]
azure_deployment = st.secrets["AOAI_GPT4O_MINI_MODEL"]
api_version = "2024-02-01"

def get_openai_config() -> ModelConfiguration:
    openai_config = AzureOpenAIModelConfiguration(
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
        api_version=api_version,
        api_key=api_key,
    )
    openai_config.model = st.secrets["AOAI_GPT4O_MINI_MODEL"]
    return openai_config


def get_openai_config_dict() -> dict:
    """Return a dictionary with OpenAI configuration based on environment variables.
    This is only used by azure-ai-generative SDK right now, and should be deprecated once
    the generate functionality is available in promptflow SDK.
    """
    azure_endpoint = azure_endpoint
    api_key = api_key
    openai_config = {
        "api_type": "azure",
        "api_base": azure_endpoint,
        "api_key": api_key,
        "api_version": "2024-02-15-preview",
        "deployment": azure_deployment,
        "model": azure_deployment,
    }
    return openai_config


def get_search_client():
    if api_key := api_key:
        logger.info("Using Azure Search Service with API Key from AZURE_SEARCH_KEY")
        azure_credential = AzureKeyCredential(api_key)
    else:
        logger.info("Using Azure Search Service with Azure Developer CLI Credential")
        azure_credential = AzureDeveloperCliCredential()

    return SearchClient(
        endpoint=f"https://{st.secrets('AZURE_SEARCH_SERVICE')}.search.windows.net",
        index_name=st.secrets("AZURE_AI_SEARCH_INDEX_NAME"),
        credential=azure_credential,
    )


def get_openai_client(oai_config: ModelConfiguration):
    if isinstance(oai_config, AzureOpenAIModelConfiguration):
        azure_token_provider = None
        if not api_key:
            azure_token_provider = get_bearer_token_provider(
                AzureDeveloperCliCredential(), "https://cognitiveservices.azure.com/.default"
            )
        return openai.AzureOpenAI(
            api_version=oai_config.api_version,
            azure_endpoint=oai_config.azure_endpoint,
            api_key=oai_config.api_key if api_key else None,
            azure_ad_token_provider=azure_token_provider,
            azure_deployment=oai_config.azure_deployment,
        )
    elif isinstance(oai_config, OpenAIModelConfiguration):
        oai_config: OpenAIModelConfiguration = oai_config
        return openai.OpenAI(api_key=oai_config.api_key, organization=oai_config.organization)
    else:
        raise ValueError(f"Unsupported OpenAI configuration type: {type(oai_config)}")
