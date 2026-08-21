import uvicorn

from config.env import AppConfig

if __name__ != '__main__':
    from scheduler_server import create_scheduler_app

    app = create_scheduler_app()

if __name__ == '__main__':
    uvicorn.run(
        app='scheduler_server:create_scheduler_app',
        host=AppConfig.app_host,
        port=AppConfig.app_port,
        root_path='',
        reload=False,
        workers=1,
        factory=True,
    )
