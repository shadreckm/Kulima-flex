from tavily import TavilyClient

client = TavilyClient(
    api_key="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"
)

try:
    response = client.search(
        query="Shadreck Mawindo entrepreneurship",
        search_depth="basic"
    )

    print("SUCCESS!")
    print(response)

except Exception as e:
    print("ERROR:")
    print(e)