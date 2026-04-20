pipeline {
    agent any

    environment {
        GITLAB_CRED = 'gitlab-deploy-token'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {

        // ──────────────────────────────────────
        //  1. Checkout
        // ──────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/master']],
                    userRemoteConfigs: [[
                        url: 'https://lab.ssafy.com/s14-final/S14P31S305.git',
                        credentialsId: "${GITLAB_CRED}"
                    ]]
                ])
            }
        }

        // ──────────────────────────────────────
        //  2. 변경 감지
        // ──────────────────────────────────────
        stage('Detect Changes') {
            steps {
                script {
                    def changes = sh(script: "git diff --name-only HEAD~1 HEAD || echo '.'", returnStdout: true).trim()
                    echo "=== 변경된 파일 ===\n${changes}"

                    env.CHANGED_GATEWAY   = changes.contains('gateway/')              ? 'true' : 'false'
                    env.CHANGED_INGESTION = changes.contains('ems/ingestion/')        ? 'true' : 'false'
                    env.CHANGED_STATE     = changes.contains('ems/state-processor/')  ? 'true' : 'false'
                    env.CHANGED_DBWRITER  = changes.contains('ems/db-writer/')        ? 'true' : 'false'
                    env.CHANGED_CONTROL   = changes.contains('ems/control/')          ? 'true' : 'false'
                    env.CHANGED_AI        = changes.contains('ems/ai-service/')       ? 'true' : 'false'
                    env.CHANGED_SIMULATOR = changes.contains('simulator/')            ? 'true' : 'false'
                    env.CHANGED_INFRA     = changes.contains('docker-compose') || changes.contains('infra/') ? 'true' : 'false'

                    echo """
                    === 변경 감지 결과 ===
                    Gateway:         ${env.CHANGED_GATEWAY}
                    Ingestion:       ${env.CHANGED_INGESTION}
                    State+DBWriter:  ${env.CHANGED_STATE} / ${env.CHANGED_DBWRITER}
                    Control+AI:      ${env.CHANGED_CONTROL} / ${env.CHANGED_AI}
                    Infra:           ${env.CHANGED_INFRA}
                    """
                }
            }
        }

        // ──────────────────────────────────────
        //  3. SonarQube 정적 분석
        // ──────────────────────────────────────
        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh '''
                        sonar-scanner \
                            -Dsonar.projectKey=s14p31s305 \
                            -Dsonar.sources=ems/ingestion/app,ems/state-processor/app,ems/control/app,ems/ai-service/app,ems/db-writer/app
                    '''
                }
            }
        }

        // ──────────────────────────────────────
        //  4. Build (변경된 서비스만)
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
            }
        }

        // ──────────────────────────────────────
        //  5. Test (변경된 서비스만)
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
                            docker compose -f docker-compose.control.yml run --rm --no-deps ai-service \
                                sh -c "pip install pytest && pytest tests/ -v --tb=short || true"
                        '''
                    }
                }
            }
        }

        // ──────────────────────────────────────
        //  6. Deploy (EC2 할당 후 주석 해제)
        // ──────────────────────────────────────
        /*
        stage('Deploy') {
            parallel {
                stage('Deploy - Gateway') {
                    when { expression { env.CHANGED_GATEWAY == 'true' || env.CHANGED_INFRA == 'true' } }
                    steps {
                        sshagent(credentials: ['ec2-ssh-key']) {
                            sh """
                                scp -o StrictHostKeyChecking=no docker-compose.gateway.yml ubuntu@\${GATEWAY_IP}:/home/ubuntu/app/
                                scp -rp gateway/ ubuntu@\${GATEWAY_IP}:/home/ubuntu/app/
                                ssh -o StrictHostKeyChecking=no ubuntu@\${GATEWAY_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.gateway.yml up -d --build'
                            """
                        }
                    }
                }
                stage('Deploy - Ingestion') {
                    when { expression { env.CHANGED_INGESTION == 'true' || env.CHANGED_INFRA == 'true' } }
                    steps {
                        sshagent(credentials: ['ec2-ssh-key']) {
                            sh """
                                scp -o StrictHostKeyChecking=no docker-compose.ingestion.yml .env ubuntu@\${INGESTION_IP}:/home/ubuntu/app/
                                scp -rp ingestion/ infra/mosquitto/ ubuntu@\${INGESTION_IP}:/home/ubuntu/app/
                                ssh -o StrictHostKeyChecking=no ubuntu@\${INGESTION_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.ingestion.yml up -d --build'
                            """
                        }
                    }
                }
                stage('Deploy - State+DBWriter') {
                    when { expression { env.CHANGED_STATE == 'true' || env.CHANGED_DBWRITER == 'true' || env.CHANGED_INFRA == 'true' } }
                    steps {
                        sshagent(credentials: ['ec2-ssh-key']) {
                            sh """
                                scp -o StrictHostKeyChecking=no docker-compose.state.yml .env ubuntu@\${STATE_IP}:/home/ubuntu/app/
                                scp -rp state-processor/ db-writer/ ubuntu@\${STATE_IP}:/home/ubuntu/app/
                                ssh -o StrictHostKeyChecking=no ubuntu@\${STATE_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.state.yml up -d --build'
                            """
                        }
                    }
                }
                stage('Deploy - Control+AI') {
                    when { expression { env.CHANGED_CONTROL == 'true' || env.CHANGED_AI == 'true' || env.CHANGED_INFRA == 'true' } }
                    steps {
                        sshagent(credentials: ['ec2-ssh-key']) {
                            sh """
                                scp -o StrictHostKeyChecking=no docker-compose.control.yml .env ubuntu@\${CONTROL_IP}:/home/ubuntu/app/
                                scp -rp control/ ai-service/ ubuntu@\${CONTROL_IP}:/home/ubuntu/app/
                                ssh -o StrictHostKeyChecking=no ubuntu@\${CONTROL_IP} 'cd /home/ubuntu/app && docker compose -f docker-compose.control.yml up -d --build'
                            """
                        }
                    }
                }
            }
        }
        */
    }

    post {
        success { echo '=== 파이프라인 성공 ===' }
        failure { echo '=== 파이프라인 실패 ===' }
        always  { sh 'docker system prune -f 2>/dev/null || true' }
    }
}
