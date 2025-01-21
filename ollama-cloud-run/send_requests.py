import aiohttp
import asyncio


async def send_request(session):
    url = "http://localhost:9090/api/generate"
    payload = {
        "model": "deepseek-r1:7b",
        "prompt": "Why is the sky blue?"
    }
    try:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.text()
            else:
                return f"Error: {response.status}"
    except Exception as e:
        return f"Request failed: {e}"


async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        for result in results:
            print(result)


if __name__ == "__main__":
    asyncio.run(main())
