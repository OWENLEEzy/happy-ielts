from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # H3 fix: 创建全局共享 checkpointer 单例，setup() 只调用一次
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string("./db.sqlite3") as cp:
        cp.setup()
        app.state.checkpointer = cp
        yield
    # with 块退出时自动关闭连接


app = FastAPI(title="DynamicLingo API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}
