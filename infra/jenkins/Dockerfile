# Jenkins LTS + Docker CE CLI (DooD 패턴용)
#
# Jenkins 컨테이너에서 호스트 Docker 소켓(/var/run/docker.sock)을 통해
# 호스트의 docker 데몬을 호출하려면 컨테이너 안에 `docker` 클라이언트가 있어야 함.
# 기본 jenkins/jenkins:lts-jdk17 이미지에는 docker CLI 가 없어서 별도 설치.
#
# 설치 대상:
# - docker-ce-cli       : `docker` 명령어 (빌드/푸시/실행)
# - docker-compose-plugin : `docker compose` v2 (Jenkinsfile 에서 compose up/down 사용 시)
#
# 버전: Jenkins 이미지에 맞춰 Debian bookworm 의 Docker CE 저장소 사용.

FROM jenkins/jenkins:lts-jdk17

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        docker-ce-cli \
        docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Jenkins 가 docker.sock 을 직접 호출하도록 root 로 유지 (compose 의 user: root 와 일치)
# 보안 강화가 필요하면 jenkins 유저 + 호스트 docker 그룹 GID 매칭 방식으로 전환.
USER root
