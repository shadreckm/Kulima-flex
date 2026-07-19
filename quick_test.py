"""Quick OpenAI connectivity check for Kulima FLEX."""

from dotenv import load_dotenv

from kulima.llm import LLMClient

load_dotenv()

if __name__ == "__main__":
    client = LLMClient()
    text = client.complete(
        system="You are Kulima FLEX, an African VC intelligence OS.",
        user="Say hello to Kulima FLEX VC Brain in one sharp sentence.",
    )
    print(text)
