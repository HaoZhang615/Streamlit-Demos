import json
import os
import requests
from dotenv import load_dotenv
load_dotenv()

api_base = os.getenv("AOAI_API_BASE")
api_key = os.getenv("AOAI_API_KEY")
api_version = os.getenv("AOAI_API_VERSION")
tts = os.getenv("TTS_MODEL_NAME")

def text_to_speech(input:str):
    headers = {'Content-Type':'application/json', 'api-key': api_key}
    url = f"{api_base}openai/deployments/{tts}/audio/speech?api-version=2024-05-01-preview"
    body = {
        "input": input,
        "voice": "echo",
        "model": "tts",
        "response_format": "mp3"
    }
    print(url)
    response = requests.post(url, headers=headers, data=json.dumps(body))
    with open("output.mp3", "wb") as f:
            f.write(response.content)
    return response.content

text_to_speech("come to my bedroom and let's have some fun")