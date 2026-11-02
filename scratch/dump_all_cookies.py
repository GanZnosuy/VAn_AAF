import asyncio
from playwright.async_api import async_playwright

async def get_all_cookies():
    p = await async_playwright().start()
    b = await p.chromium.connect_over_cdp('http://localhost:9222')
    for ctx in b.contexts:
        for page in ctx.pages:
            if 'gemini.google.com' in page.url:
                cookies = await ctx.cookies()
                print(f"Total cookies in context: {len(cookies)}")
                for c in sorted(cookies, key=lambda x: x['name']):
                    print(f"  {c['domain']} : {c['name']} = {c['value'][:25]}...")
                await b.close()
                await p.stop()
                return

if __name__ == '__main__':
    asyncio.run(get_all_cookies())
