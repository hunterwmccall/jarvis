import requests

messages = [{"role": "system", "content":
    "You are Jarvis, a concise voice assistant running locally on Hunter's PC. "
    "Be friendly. Answer accurately. Decipher tone of wording and respond accordingly. if tone is friendly and conversational, respond in kind. If tone is hostile or rude, respond politely and professionally. Based upon the context of a conversation, you may ask questions to clarify the users intent. Also, use the context of the conversation to attempt to negate potential misunderstadings in the spelling, grammar, or phrasing of the users input. Do not make up answers."}]

while True:
    user = input("You: ")
    messages.append({"role": "user", "content": user})
    r = requests.post("http://localhost:11434/api/chat", json={
        "model": "gemma4", "messages": messages, "stream": False})
    reply = r.json()["message"]["content"]
    messages.append({"role": "assistant", "content": reply})
    print("Jarvis:", reply)
    