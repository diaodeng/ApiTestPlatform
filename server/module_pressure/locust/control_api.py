from fastapi import FastAPI




def create_control_api(env, runner):
    app = FastAPI()

    @app.post("/start")
    def start(users: int, rate: int):
        runner.start(user_count=users, spawn_rate=rate)

    @app.post("/stop")
    def stop():
        runner.stop()

    @app.get("/stats")
    def stats():
        return export_stats(env.stats)

    return app
