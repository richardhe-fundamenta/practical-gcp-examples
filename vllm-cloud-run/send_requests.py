import aiohttp
import asyncio
import time
import numpy as np
import de_prompt_gen

TOTAL_CONCURRENT_REQUESTS = 60
ALL_PROMPTS = [_ for _ in de_prompt_gen.generate(TOTAL_CONCURRENT_REQUESTS)]


async def send_request(session, index, latencies):
    url = "http://localhost:8080/v1/completions"
    payload = {
        "model": "tgi",
        "prompt": ALL_PROMPTS[index],
        "max_tokens": 2048,
        "temperature": 0.90
    }
    try:
        start_time = time.monotonic()
        async with session.post(url, json=payload) as response:
            end_time = time.monotonic()
            latency = end_time - start_time
            latencies.append(latency)
            if response.status == 200:
                return await response.text()
            else:
                return f"Error: {response.status}"
    except Exception as e:
        return f"Request failed: {e}"


async def main():
    latencies = []
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, index, latencies) for index in range(TOTAL_CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)
        # Process results if needed, but not printing them as per your request
        for r in results:
            print(r)
    if latencies:
        p99_latency = np.percentile(latencies, 99)
        print(f"P99 Latency: {p99_latency:.4f} seconds")
    else:
        print("No latencies recorded.")


if __name__ == "__main__":
    asyncio.run(main())
