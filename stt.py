import json
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()

api_base = os.getenv("AOAI_API_BASE")
api_key = os.getenv("AOAI_API_KEY")
api_version = os.environ["AOAI_API_VERSION"]
whisper = os.getenv("AOAI_WHISPER_MODEL")

client = AzureOpenAI(
    api_key=api_key,  
    api_version=api_version,
    azure_endpoint = api_base,
)


def speech_to_text(audio:bytes)->str:
    result = client.audio.transcriptions.create(
        model=whisper,
        file=open(audio, "rb"),
    )
    return print(result.text)

speech_to_text("1.wav")