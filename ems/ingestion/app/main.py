# Flask 진입점.
# - 컨테이너에서는 `flask run` 으로 실행됨 (Dockerfile 참조).
#   FLASK_APP=app.main:app 환경변수가 이 모듈의 `app` 변수를 가리킨다.
# - 로컬에서 직접 실행 시 `python -m app.main` 또는 아래 if __name__ 블록 사용.
from .api import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, use_reloader=False)
