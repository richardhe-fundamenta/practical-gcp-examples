import aiohttp
import asyncio
import de_prompt_gen

TOTAL_CONCURRENT_REQUESTS = 15
ALL_PROMPTS = [_ for _ in de_prompt_gen.generate(TOTAL_CONCURRENT_REQUESTS)]


async def send_request(session, index):
    url = "http://localhost:9090/api/generate"
    payload = {
        "model": "deepseek-r1:7b",
        "prompt": ALL_PROMPTS[index]
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
        tasks = [send_request(session, index) for index in range(TOTAL_CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)
        for result in results:
            print(result)


if __name__ == "__main__":
    asyncio.run(main())
