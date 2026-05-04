pipeline {
    agent any

    environment {
        GITLAB_CRED  = 'gitlab-deploy-token'
        GATEWAY_IP   = credentials('GATEWAY_IP')
        INGESTION_IP = credentials('INGESTION_IP')
        STATE_IP     = credentials('STATE_IP')
        CONTROL_IP   = credentials('CONTROL_IP')
        DB_IP        = credentials('DB_IP')
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {

        // ──────────────────────────────────────
        //  1. Checkout
        //     - MR 이벤트 : GitLab webhook 이 주입하는 gitlabSourceBranch 체크아웃
        //     - Push 이벤트 : 해당 브랜치(env.BRANCH_NAME) 체크아웃
        //     - 그 외       : master fallback
        // ──────────────────────────────────────
        stage('Checkout') {
            steps {
                script {
                    def targetRef = env.gitlabSourceBranch ?: env.BRANCH_NAME ?: 'master'
                    echo "=== Checkout 대상 브랜치: ${targetRef} ==="
                    checkout([
                        $class: 'GitSCM',
                        branches: [[name: "*/${targetRef}"]],
                        userRemoteConfigs: [[
                            url: 'https://lab.ssafy.com/s14-final/S14P31S305.git',
                            credentialsId: "${GITLAB_CRED}"
                        ]]
                    ])
                }
            }
        }

        // ──────────────────────────────────────
        //  2. 변경 감지 (폴더별 CI/CD)
        //     - MR 이벤트 : origin/<target>...HEAD (3-dot) 로 MR 전체 변경사항 감지
        //                   → MR 내 모든 커밋의 변경사항을 빠짐없이 잡음
        //     - Push 이벤트 : HEAD~1..HEAD (직전 커밋) 로 변경사항 감지
        //     - 감지 결과에 따라 Build/Test/Deploy stage 는 when 조건으로 필터링됨
        // ──────────────────────────────────────
        stage('Detect Changes') {
            steps {
                script {
                    def isMR = env.gitlabActionType == 'MERGE' || env.gitlabMergeRequestIid?.trim()
                    def targetBranch = env.gitlabTargetBranch ?: 'master'
                    def currentBranch = env.gitlabSourceBranch ?: env.BRANCH_NAME ?: 'master'

                    def changes
                    if (isMR) {
                        echo "=== 변경 감지 방식: MR diff (origin/${targetBranch}...HEAD) ==="
                        changes = sh(
                            script: "git fetch origin ${targetBranch} && git diff --name-only origin/${targetBranch}...HEAD || echo '.'",
                            returnStdout: true
                        ).trim()
                    } else {
                        echo "=== 변경 감지 방식: Push diff (HEAD~1..HEAD) ==="
                        changes = sh(
                            script: "git diff --name-only HEAD~1 HEAD || echo '.'",
                            returnStdout: true
                        ).trim()
                    }
                    echo "=== 변경된 파일 ===\n${changes}"

                    env.CHANGED_GATEWAY   = changes.contains('gateway/')              ? 'true' : 'false'
                    env.CHANGED_INGESTION = changes.contains('ems/ingestion/')        ? 'true' : 'false'
                    env.CHANGED_STATE     = changes.contains('ems/state-processor/')  ? 'true' : 'false'
                    env.CHANGED_DBWRITER  = changes.contains('ems/db-writer/')        ? 'true' : 'false'
                    env.CHANGED_CONTROL   = changes.contains('ems/control/')          ? 'true' : 'false'
                    env.CHANGED_AI        = changes.contains('ems/ai/')              ? 'true' : 'false'
                    env.CHANGED_FRONTEND  = changes.contains('frontend/')             ? 'true' : 'false'
                    env.CHANGED_SIMULATOR = changes.contains('simulator/')            ? 'true' : 'false'
                    env.CHANGED_INFRA     = changes.contains('docker-compose') || changes.contains('infra/') ? 'true' : 'false'

                    // ──────────────────────────────────────
                    // 배포 정책 (prod / dev 2개 환경 분리):
                    //
                    //   prod (5대 EC2, 분산 배치, 8080 + 5xxx 포트, /home/ubuntu/app)
                    //     ✅ master push                              → prod 배포
                    //     ✅ feature/ems → master MR                  → prod 배포
                    //     ❌ 그 외                                    → CI 만
                    //
                    //   dev (5대 EC2 공유, 별도 컨테이너, 9080 + 6xxx 포트, /home/ubuntu/dev)
                    //     ✅ ems push (직접 또는 feature→ems MR 머지) → dev 배포
                    //     ❌ master push, master 타겟 MR              → prod 만 (dev X)
                    //     ❌ feature → ems MR (생성 시)               → CI 만
                    //
                    //   frontend 전용 정책:
                    //     ✅ master push (frontend/ 변경)             → prod gateway 의 정적파일 갱신
                    //     ✅ frontend push (직접 또는 fe/xxx → frontend MR 머지) → dev gateway 의 정적파일 갱신
                    //     ❌ frontend → master MR                     → CI 만 (머지 후 master push 가 prod 배포)
                    //     ❌ feature(fe/xxx) → frontend MR (생성 시)  → CI 만
                    // ──────────────────────────────────────
                    def shouldDeploy = false
                    if (isMR && targetBranch == 'master') {
                        shouldDeploy = true
                    } else if (!isMR && currentBranch == 'master') {
                        shouldDeploy = true
                    }
                    env.SHOULD_DEPLOY = shouldDeploy ? 'true' : 'false'

                    def shouldDeployDev = !isMR && currentBranch == 'ems'
                    env.SHOULD_DEPLOY_DEV = shouldDeployDev ? 'true' : 'false'

                    def shouldDeployFrontendDev = !isMR && currentBranch == 'frontend'
                    env.SHOULD_DEPLOY_FRONTEND_DEV = shouldDeployFrontendDev ? 'true' : 'false'

                    echo """
                    === 변경 감지 결과 ===
                    이벤트 타입:     ${isMR ? 'MR (target=' + targetBranch + ')' : 'Push (branch=' + currentBranch + ')'}
                    Gateway:         ${env.CHANGED_GATEWAY}
                    Ingestion:       ${env.CHANGED_INGESTION}
                    State+DBWriter:  ${env.CHANGED_STATE} / ${env.CHANGED_DBWRITER}
                    Control+AI:      ${env.CHANGED_CONTROL} / ${env.CHANGED_AI}
                    Frontend:        ${env.CHANGED_FRONTEND}
                    Infra:           ${env.CHANGED_INFRA}
                    Deploy (prod):   ${env.SHOULD_DEPLOY}
                    Deploy (dev):    ${env.SHOULD_DEPLOY_DEV}
                    Deploy (FE-dev): ${env.SHOULD_DEPLOY_FRONTEND_DEV}
                    """
                }
            }
        }

        // ──────────────────────────────────────
        //  3. Verify Env (.env 필수 값 + 길이/형식 검증)
        //     - configFileProvider 로 Managed File "ems-env" 주입
        //     - infra/check_env.sh 가 공란/약한 값 검출 시 exit 1 → 파이프라인 중단
        //     - Build/Test/Deploy 전에 선제 차단
        // ──────────────────────────────────────
        stage('Verify Env') {
            steps {
                configFileProvider([configFile(fileId: 'ems-env', targetLocation: '.env')]) {
                    sh 'bash infra/check_env.sh .env'
                }
            }
        }

        // ──────────────────────────────────────
        //  4. SonarQube 정적 분석
        // ──────────────────────────────────────
        // stage('SonarQube Analysis') {
        //     steps {
        //         withSonarQubeEnv('SonarQube') {
        //             sh '''
        //                 sonar-scanner \
        //                     -Dsonar.projectKey=s14p31s305 \
        //                     -Dsonar.sources=ems/ingestion/app,ems/state-processor/app,ems/control/app,ems/ai/app,ems/db-writer/app
        //             '''
        //         }
        //     }
        // }

        // ──────────────────────────────────────
        //  5. Build (변경된 서비스만)
        // ──────────────────────────────────────
        stage('Build') {
            parallel {
                stage('Build - Gateway') {
                    when { expression { env.CHANGED_GATEWAY == 'true' } }
                    steps { sh 'docker compose -f docker-compose.gateway.yml build' }
                }
                stage('Build - Ingestion') {
                    when { expression { env.CHANGED_INGESTION == 'true' } }
                    steps { sh 'docker compose -f docker-compose.ingestion.yml build ingestion' }
                }
                stage('Build - State+DBWriter') {
                    when { expression { env.CHANGED_STATE == 'true' || env.CHANGED_DBWRITER == 'true' } }
                    steps { sh 'docker compose -f docker-compose.state.yml build' }
                }
                stage('Build - Control+AI') {
                    when { expression { env.CHANGED_CONTROL == 'true' || env.CHANGED_AI == 'true' } }
                    steps { sh 'docker compose -f docker-compose.control.yml build' }
                }
                // Vue 프론트엔드 빌드 — prod 배포 또는 frontend 브랜치 push 시
                // node:20-alpine 컨테이너로 빌드해서 결과물 frontend/dist/ 를 산출
                stage('Build - Frontend') {
                    when {
                        expression {
                            (env.SHOULD_DEPLOY == 'true' && env.CHANGED_FRONTEND == 'true') ||
                            env.SHOULD_DEPLOY_FRONTEND_DEV == 'true'
                        }
                    }
                    steps {
                        sh '''
                            docker run --rm \
                              -v "${WORKSPACE}/frontend:/app" \
                              -w /app \
                              node:20-alpine \
                              sh -c "npm ci && npm run build"
                            ls -la frontend/dist | head -20
                        '''
                    }
                }
            }
        }

        // ──────────────────────────────────────
        //  6. Test (변경된 서비스만)
        // ──────────────────────────────────────
        stage('Test') {
            parallel {
                stage('Test - Ingestion') {
                    when { expression { env.CHANGED_INGESTION == 'true' } }
                    steps {
                        sh '''
                            docker compose -f docker-compose.ingestion.yml run --rm --no-deps ingestion \
                                sh -c "pip install pytest && pytest tests/ -v --tb=short || true"
                        '''
                    }
                }
                stage('Test - State') {
                    when { expression { env.CHANGED_STATE == 'true' } }
                    steps {
                        sh '''
                            docker compose -f docker-compose.state.yml run --rm --no-deps state-processor \
                                sh -c "pip install pytest && pytest tests/ -v --tb=short || true"
                        '''
                    }
                }
                stage('Test - Control') {
                    when { expression { env.CHANGED_CONTROL == 'true' } }
                    steps {
                        sh '''
                            docker compose -f docker-compose.control.yml run --rm --no-deps control \
                                sh -c "pip install pytest && pytest tests/ -v --tb=short || true"
                        '''
                    }
                }
                stage('Test - AI') {
                    when { expression { env.CHANGED_AI == 'true' } }
                    steps {
                        sh '''
                            docker compose -f docker-compose.control.yml run --rm --no-deps ai \
                                sh -c "pip install pytest && pytest tests/ -v --tb=short || true"
                        '''
                    }
                }
            }
        }

        // ──────────────────────────────────────
        //  7. Deploy (EC2 5대 병렬 배포)
        //     - .env 는 Jenkins Config File Provider 로 주입 (파일은 저장소에 없음)
        //     - scp 경로는 monorepo 구조(ems/*) 기준
        //     - 각 stage 는 해당 EC2 의 /home/ubuntu/app 에 파일을 올리고 docker compose up -d --build
        // ──────────────────────────────────────
        stage('Deploy') {
            parallel {
                stage('Deploy - Gateway') {
                    when { expression { env.SHOULD_DEPLOY == 'true' && (env.CHANGED_GATEWAY == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        sshagent(credentials: ['ec2-ssh-key']) {
                            sh '''
                                ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'mkdir -p /home/ubuntu/app'
                                scp -o StrictHostKeyChecking=accept-new docker-compose.gateway.yml ubuntu@${GATEWAY_IP}:/home/ubuntu/app/
                                scp -o StrictHostKeyChecking=accept-new -rp gateway/ ubuntu@${GATEWAY_IP}:/home/ubuntu/app/
                                ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.gateway.yml up -d --build'
                            '''
                        }
                    }
                }
                stage('Deploy - Ingestion') {
                    when { expression { env.SHOULD_DEPLOY == 'true' && (env.CHANGED_INGESTION == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${INGESTION_IP} 'mkdir -p /home/ubuntu/app/ems /home/ubuntu/app/infra'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.ingestion.yml .env ubuntu@${INGESTION_IP}:/home/ubuntu/app/
                                    scp -o StrictHostKeyChecking=accept-new -rp ems/ingestion ubuntu@${INGESTION_IP}:/home/ubuntu/app/ems/
                                    scp -o StrictHostKeyChecking=accept-new -rp infra/mosquitto infra/init_streams.py infra/Dockerfile.stream-init ubuntu@${INGESTION_IP}:/home/ubuntu/app/infra/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${INGESTION_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.ingestion.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
                stage('Deploy - State+DBWriter') {
                    when { expression { env.SHOULD_DEPLOY == 'true' && (env.CHANGED_STATE == 'true' || env.CHANGED_DBWRITER == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${STATE_IP} 'mkdir -p /home/ubuntu/app/ems'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.state.yml .env ubuntu@${STATE_IP}:/home/ubuntu/app/
                                    scp -o StrictHostKeyChecking=accept-new -rp ems/state-processor ems/db-writer ubuntu@${STATE_IP}:/home/ubuntu/app/ems/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${STATE_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.state.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
                stage('Deploy - Control+AI') {
                    when { expression { env.SHOULD_DEPLOY == 'true' && (env.CHANGED_CONTROL == 'true' || env.CHANGED_AI == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${CONTROL_IP} 'mkdir -p /home/ubuntu/app/ems'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.control.yml .env ubuntu@${CONTROL_IP}:/home/ubuntu/app/
                                    scp -o StrictHostKeyChecking=accept-new -rp ems/control ems/ai ubuntu@${CONTROL_IP}:/home/ubuntu/app/ems/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${CONTROL_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.control.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
                stage('Deploy - DB') {
                    when { expression { env.SHOULD_DEPLOY == 'true' && env.CHANGED_INFRA == 'true' } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${DB_IP} 'mkdir -p /home/ubuntu/app/infra'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.db.yml .env ubuntu@${DB_IP}:/home/ubuntu/app/
                                    scp -o StrictHostKeyChecking=accept-new infra/init_postgres.sh infra/init_timescale.sh ubuntu@${DB_IP}:/home/ubuntu/app/infra/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${DB_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.db.yml up -d'
                                '''
                            }
                        }
                    }
                }

                // ──────────────────────────────────────
                //  Dev 환경 (ems push 시 배포, /home/ubuntu/dev, --project-name dev)
                //   - ems-env-dev Managed File 의 시크릿/포트 사용 (9080, 6xxx, 7379, 2883, 6432/6433)
                //   - bind mount: /data/postgres-dev, /data/timescale-dev (DB EC2 에 사전 생성 필요)
                //   - prod 컨테이너와 격리됨 (project name 으로 컨테이너/네트워크/볼륨 자동 분리)
                // ──────────────────────────────────────
                stage('Deploy - Gateway (dev)') {
                    when { expression { env.SHOULD_DEPLOY_DEV == 'true' && (env.CHANGED_GATEWAY == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env-dev', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'mkdir -p /home/ubuntu/dev'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.gateway.yml .env ubuntu@${GATEWAY_IP}:/home/ubuntu/dev/
                                    scp -o StrictHostKeyChecking=accept-new -rp gateway/ ubuntu@${GATEWAY_IP}:/home/ubuntu/dev/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'cd /home/ubuntu/dev && docker compose --project-name dev -f docker-compose.gateway.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
                stage('Deploy - Ingestion (dev)') {
                    when { expression { env.SHOULD_DEPLOY_DEV == 'true' && (env.CHANGED_INGESTION == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env-dev', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${INGESTION_IP} 'mkdir -p /home/ubuntu/dev/ems /home/ubuntu/dev/infra'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.ingestion.yml .env ubuntu@${INGESTION_IP}:/home/ubuntu/dev/
                                    scp -o StrictHostKeyChecking=accept-new -rp ems/ingestion ubuntu@${INGESTION_IP}:/home/ubuntu/dev/ems/
                                    scp -o StrictHostKeyChecking=accept-new -rp infra/mosquitto infra/init_streams.py infra/Dockerfile.stream-init ubuntu@${INGESTION_IP}:/home/ubuntu/dev/infra/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${INGESTION_IP} 'cd /home/ubuntu/dev && docker compose --project-name dev -f docker-compose.ingestion.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
                stage('Deploy - State+DBWriter (dev)') {
                    when { expression { env.SHOULD_DEPLOY_DEV == 'true' && (env.CHANGED_STATE == 'true' || env.CHANGED_DBWRITER == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env-dev', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${STATE_IP} 'mkdir -p /home/ubuntu/dev/ems'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.state.yml .env ubuntu@${STATE_IP}:/home/ubuntu/dev/
                                    scp -o StrictHostKeyChecking=accept-new -rp ems/state-processor ems/db-writer ubuntu@${STATE_IP}:/home/ubuntu/dev/ems/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${STATE_IP} 'cd /home/ubuntu/dev && docker compose --project-name dev -f docker-compose.state.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
                stage('Deploy - Control+AI (dev)') {
                    when { expression { env.SHOULD_DEPLOY_DEV == 'true' && (env.CHANGED_CONTROL == 'true' || env.CHANGED_AI == 'true' || env.CHANGED_INFRA == 'true') } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env-dev', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${CONTROL_IP} 'mkdir -p /home/ubuntu/dev/ems'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.control.yml .env ubuntu@${CONTROL_IP}:/home/ubuntu/dev/
                                    scp -o StrictHostKeyChecking=accept-new -rp ems/control ems/ai ubuntu@${CONTROL_IP}:/home/ubuntu/dev/ems/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${CONTROL_IP} 'cd /home/ubuntu/dev && docker compose --project-name dev -f docker-compose.control.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
                stage('Deploy - DB (dev)') {
                    when { expression { env.SHOULD_DEPLOY_DEV == 'true' && env.CHANGED_INFRA == 'true' } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env-dev', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${DB_IP} 'mkdir -p /home/ubuntu/dev/infra'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.db.yml .env ubuntu@${DB_IP}:/home/ubuntu/dev/
                                    scp -o StrictHostKeyChecking=accept-new infra/init_postgres.sh infra/init_timescale.sh ubuntu@${DB_IP}:/home/ubuntu/dev/infra/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${DB_IP} 'cd /home/ubuntu/dev && docker compose --project-name dev -f docker-compose.db.yml up -d'
                                '''
                            }
                        }
                    }
                }

                // ──────────────────────────────────────
                //  Frontend (정적파일) — Volume Mount 방식
                //   - prod: master push + frontend/ 변경 → /home/ubuntu/app/frontend-dist 갱신 → gateway nginx 가 서빙
                //   - dev : frontend 브랜치 push → /home/ubuntu/dev/frontend-dist 갱신 → dev gateway nginx 가 서빙
                //   - 빌드 산출물 (frontend/dist/) 은 Build - Frontend stage 에서 생성됨
                // ──────────────────────────────────────
                stage('Deploy - Frontend') {
                    when { expression { env.SHOULD_DEPLOY == 'true' && env.CHANGED_FRONTEND == 'true' } }
                    steps {
                        sshagent(credentials: ['ec2-ssh-key']) {
                            sh '''
                                ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'mkdir -p /home/ubuntu/app/frontend-dist'
                                ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'rm -rf /home/ubuntu/app/frontend-dist/*'
                                scp -o StrictHostKeyChecking=accept-new -rp frontend/dist/* ubuntu@${GATEWAY_IP}:/home/ubuntu/app/frontend-dist/
                                ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.gateway.yml restart gateway'
                            '''
                        }
                    }
                }
                stage('Deploy - Frontend (dev)') {
                    when { expression { env.SHOULD_DEPLOY_FRONTEND_DEV == 'true' } }
                    steps {
                        configFileProvider([configFile(fileId: 'ems-env-dev', targetLocation: '.env')]) {
                            sshagent(credentials: ['ec2-ssh-key']) {
                                sh '''
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'mkdir -p /home/ubuntu/dev/frontend-dist'
                                    scp -o StrictHostKeyChecking=accept-new docker-compose.gateway.yml .env ubuntu@${GATEWAY_IP}:/home/ubuntu/dev/
                                    scp -o StrictHostKeyChecking=accept-new -rp gateway/ ubuntu@${GATEWAY_IP}:/home/ubuntu/dev/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'rm -rf /home/ubuntu/dev/frontend-dist/*'
                                    scp -o StrictHostKeyChecking=accept-new -rp frontend/dist/* ubuntu@${GATEWAY_IP}:/home/ubuntu/dev/frontend-dist/
                                    ssh -o StrictHostKeyChecking=accept-new ubuntu@${GATEWAY_IP} 'cd /home/ubuntu/dev && docker compose --project-name dev -f docker-compose.gateway.yml up -d --build'
                                '''
                            }
                        }
                    }
                }
            }
        }
    }

    post {
        success { echo '=== 파이프라인 성공 ===' }
        failure { echo '=== 파이프라인 실패 ===' }
        always  { sh 'docker system prune -f 2>/dev/null || true' }
    }
}
