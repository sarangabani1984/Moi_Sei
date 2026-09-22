import os
import toml
from litellm import completion

# Load your keys from secrets.toml (same file your Streamlit app uses)
secrets = toml.load(".streamlit/secrets.toml")
os.environ["OPENAI_API_KEY"] = secrets["OPENAI_API_KEY"]
os.environ["GROQ_API_KEY"] = secrets["GROQ_API_KEY"]

question = "Who contributed more than 5000 rupees?"

models_to_test = ["gpt-4o-mini", "groq/openai/gpt-oss-20b"]

for model_name in models_to_test:
    print(f"\n--- Answer from {model_name} ---")
    response = completion(
        model=model_name,
        messages=[{"role": "user", "content": question}],
    )
    print(response["choices"][0]["message"]["content"])