# from transformers import AutoTokenizer, AutoModelForCausalLM
# from peft import PeftModel
# import torch

# # Load base model
# # base_model_id = "microsoft/phi-2"
# base_model_id = "microsoft/phi-1_5"

# adapter_path = r"C:\Users\JAI BHASIN\Desktop\ai call\adapter"  # fixed
# # adapter_path = "C:\Users\JAI BHASIN\Desktop\ai call\adapter"  # or absolute path

# tokenizer = AutoTokenizer.from_pretrained(base_model_id)
# base_model = AutoModelForCausalLM.from_pretrained(base_model_id)

# # Apply LoRA adapter
# model = PeftModel.from_pretrained(base_model, adapter_path)
# model.eval()

# def generate_response(prompt: str) -> str:
#     inputs = tokenizer(prompt, return_tensors="pt")
#     outputs = model.generate(**inputs, max_new_tokens=50)
#     return tokenizer.decode(outputs[0], skip_special_tokens=True)

# print(generate_response("what is the capital of france?"))
# llm_service.py

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key from .env
load_dotenv()
api_key = os.getenv("SECRET_KEY_GOOGLE_AI")

# Configure Gemini client once
client = genai.Client(api_key=api_key)

# Function to call LLM
# BASE_PROMPT = """You are an AI phone agent collecting customer feedback.
# Speak clearly, be polite, and keep the conversation short and friendly.User can speak in indian langauges as well.
# If the user sounds unsure, gently ask a follow-up.
# Your goal is to collect a short review about their experience.
# Only respond with what the agent would say on the call — no explanations or comments."""

BASE_PROMPT = """
You are an AI phone agent collecting customer feedback.

Guidelines
• Keep replies ≤ 25 words, clear and polite.
• Prefix each reply with a brief tone cue in **parentheses**, e.g.  
  “(warm, upbeat)” or “(calm, apologetic)”.
• Do **not** explain anything, just speak the line.
• If the caller sounds unsure, follow up once, otherwise thank them and end.
• Match the caller’s language if it’s obviously not English, but prefer English when possible.
"""


def generate_response(user_input: str) -> str:
    full_prompt = f"{BASE_PROMPT}\nUser: {user_input}\nAgent:"
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        ),
    )
    return response.text

# print(generate_response("kya aap mein thodi der baad call kar sakte ho, abhi main busy hoon"))  # Example usage