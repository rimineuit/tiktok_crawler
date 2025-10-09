# start.py
import sys, asyncio
import uvicorn

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run(
        "main:app",  # đổi thành module:path tới FastAPI app của bạn
        host="0.0.0.0",
        port=8000,
        reload=False,   # tránh reload trên Windows
    )
