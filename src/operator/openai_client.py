import os
import openai

def get_ai_advice(logger, message):
    # Load your API key from an environment variable or secret management service
    logger.info(f'openAI gpt4, sending message')
    openai.api_key = os.getenv("OPENAI_API_KEY")
    chat_completion = openai.ChatCompletion.create(
        model="gpt-4", 
        messages=[
            {"role": "user", "content": message}
    ])
    logger.info(chat_completion.choices[0].message.content)
    return chat_completion.choices[0].message.content

