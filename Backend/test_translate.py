import logging
logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv()

from translate import _call_gemini_json

print(_call_gemini_json('Translate every value to Urdu. Return JSON like {"a": "Hello world"}'))