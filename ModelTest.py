from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# Initialize the LLM
chat_llm = ChatOllama(model="llama3.2:3b", temperature=0.5)

# Define messages
system_message = SystemMessage(content="You are a helpful chatbot.")
human_message = HumanMessage(content="How are you?")

# Provide messages as a list
messages = [system_message, human_message]

# Invoke the model
response = chat_llm.invoke(messages)

# Print the output
print(response.content)

