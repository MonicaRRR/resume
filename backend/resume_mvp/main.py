from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="中文 AI 简历工作台", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "resume-mvp"}

    return app


app = create_app()
