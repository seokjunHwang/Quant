"""Builder 산출물 격리 실행기."""


class DockerSandbox:
    def __init__(self, image: str = "python:3.11-slim", timeout: int = 30):
        self.image = image
        self.timeout = timeout

    def run(self, artifact_path: str) -> dict:
        # TODO: docker run --rm --network none -v {artifact}:/app/main.py {image} python /app/main.py
        # TODO: stdout, stderr, exit_code, elapsed 반환
        raise NotImplementedError
