import google.generativeai as genai
import os

# Load API key from environment variables
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_text(prompt, model="gemini-1.5-pro", temperature=0.7):
    """
    Calls Gemini LLM to generate a response based on the given prompt.
    
    :param prompt: The input prompt to process.
    :param model: The model variant (e.g., 'gemini-pro').
    :param temperature: Controls randomness of output.
    :return: AI-generated text.
    """
    try:
        response = genai.GenerativeModel(model).generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None
