pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
    }

    environment {
        // Change this if your Docker Hub username/repository differs.
        DOCKERHUB_REPO = 'syedsaifu/online-food-ordering'
        DOCKERHUB_CREDENTIALS = 'dockerhub-creds'
        KUBECONFIG_CREDENTIALS = 'docker-desktop-kubeconfig'
        FOOD_SERVICE = 'food-portal-service'
        PREVIEW_SERVICE = 'food-portal-preview'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Automated Source Tests') {
            steps {
                bat 'python tests\\test_app.py'
            }
        }

        stage('Build Image and Local Smoke Test') {
            steps {
                bat """
@echo off
docker build -t ${env.DOCKERHUB_REPO}:${env.BUILD_NUMBER} .
if errorlevel 1 exit /b 1
docker rm -f food-portal-ci-test >NUL 2>&1
docker run -d --name food-portal-ci-test -p 18080:80 ${env.DOCKERHUB_REPO}:${env.BUILD_NUMBER}
if errorlevel 1 exit /b 1
timeout /t 5 /nobreak >NUL
curl.exe --fail --silent --show-error http://127.0.0.1:18080/ -o local-smoke.html
if errorlevel 1 (
  docker logs food-portal-ci-test
  docker rm -f food-portal-ci-test >NUL 2>&1
  exit /b 1
)
findstr /I /C:"Online Food Ordering Portal" local-smoke.html >NUL
if errorlevel 1 (
  docker logs food-portal-ci-test
  docker rm -f food-portal-ci-test >NUL 2>&1
  exit /b 1
)
docker rm -f food-portal-ci-test >NUL 2>&1
"""
            }
        }

        stage('Push Image to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: env.DOCKERHUB_CREDENTIALS,
                                                   usernameVariable: 'DH_USER',
                                                   passwordVariable: 'DH_PASS')]) {
                    bat """
@echo off
echo %DH_PASS% | docker login -u %DH_USER% --password-stdin
if errorlevel 1 exit /b 1
docker push ${env.DOCKERHUB_REPO}:${env.BUILD_NUMBER}
if errorlevel 1 exit /b 1
docker logout
"""
                }
            }
        }

        stage('Blue-Green Deploy and Validate') {
            steps {
                script {
                    withCredentials([file(credentialsId: env.KUBECONFIG_CREDENTIALS,
                                          variable: 'KUBECONFIG_FILE')]) {
                        withEnv(["KUBECONFIG=${env.KUBECONFIG_FILE}"]) {
                            bat 'kubectl config current-context'

                            int serviceStatus = bat(returnStatus: true,
                                script: 'kubectl get service food-portal-service >NUL 2>&1')
                            String activeTrack = ''

                            if (serviceStatus != 0) {
                                // First deployment: create the public Service, initially selecting blue.
                                bat 'kubectl apply -f k8s\\service.yaml'
                                activeTrack = ''
                            } else {
                                int trackStatus = bat(returnStatus: true,
                                    script: '@echo off\r\nkubectl get service food-portal-service -o jsonpath={.spec.selector.track} > active-track.txt 2>NUL')
                                if (trackStatus == 0) {
                                    activeTrack = readFile('active-track.txt').trim()
                                }
                            }

                            String previousTrack = (activeTrack in ['blue', 'green']) ? activeTrack : ''
                            String targetTrack
                            if (previousTrack == '') {
                                targetTrack = 'blue'
                            } else {
                                targetTrack = (previousTrack == 'blue') ? 'green' : 'blue'
                            }

                            int targetStatus = bat(returnStatus: true,
                                script: "kubectl get deployment food-portal-${targetTrack} >NUL 2>&1")
                            boolean targetExisted = (targetStatus == 0)
                            env.PREVIOUS_TRACK = previousTrack
                            env.TARGET_TRACK = targetTrack
                            env.TARGET_DEPLOYMENT_EXISTED = targetExisted ? 'true' : 'false'

                            echo "Stable track: ${previousTrack == '' ? 'none (first deployment)' : previousTrack}"
                            echo "Candidate track: ${targetTrack}"
                            echo "Candidate image: ${env.DOCKERHUB_REPO}:${env.BUILD_NUMBER}"

                            writeFile file: "k8s-generated-${targetTrack}.yaml", text: """apiVersion: apps/v1
kind: Deployment
metadata:
  name: food-portal-${targetTrack}
  labels:
    app: online-food
    track: ${targetTrack}
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: online-food
      track: ${targetTrack}
  template:
    metadata:
      labels:
        app: online-food
        track: ${targetTrack}
    spec:
      containers:
        - name: food-portal
          image: ${env.DOCKERHUB_REPO}:${env.BUILD_NUMBER}
          imagePullPolicy: Always
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 2
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
          resources:
            requests:
              cpu: 50m
              memory: 32Mi
            limits:
              cpu: 250m
              memory: 128Mi
"""

                            writeFile file: 'k8s-generated-preview-service.yaml', text: """apiVersion: v1
kind: Service
metadata:
  name: food-portal-preview
spec:
  type: ClusterIP
  selector:
    app: online-food
    track: ${targetTrack}
  ports:
    - name: http
      port: 80
      targetPort: 80
"""

                            try {
                                bat "kubectl apply -f k8s-generated-${targetTrack}.yaml"
                                bat "kubectl rollout status deployment/food-portal-${targetTrack} --timeout=180s"

                                // The preview Service is internal-only; users are not switched to it.
                                bat 'kubectl apply -f k8s-generated-preview-service.yaml'
                                bat "kubectl set selector service/food-portal-preview app=online-food,track=${targetTrack}"

                                // Runtime candidate acceptance test. It checks a marker that is intentionally
                                // separate from the source tests so the rollback demo can fail at this stage.
                                bat "kubectl run food-portal-check-${env.BUILD_NUMBER} --image=curlimages/curl:8.12.1 --restart=Never --rm -i --pod-running-timeout=90s --command -- sh -c \"curl -fsS http://food-portal-preview/ | grep -q MENU_READY_FOR_TRAFFIC\""

                                // Only switch the public NodePort after the private candidate test passes.
                                bat "kubectl set selector service/food-portal-service app=online-food,track=${targetTrack}"
                                bat 'timeout /t 4 /nobreak >NUL'
                                bat """
@echo off
curl.exe --fail --silent --show-error http://127.0.0.1:30080/ -o nodeport-smoke.html
if errorlevel 1 exit /b 1
findstr /C:"MENU_READY_FOR_TRAFFIC" nodeport-smoke.html >NUL
if errorlevel 1 exit /b 1
"""
                                echo "Candidate ${targetTrack} passed its checks and now receives traffic."
                            } catch (failure) {
                                echo "RELEASE VALIDATION FAILED: ${failure.getMessage()}"
                                echo 'Restoring the public Service to the previous stable track.'

                                if (env.PREVIOUS_TRACK in ['blue', 'green']) {
                                    bat(returnStatus: true,
                                        script: "kubectl set selector service/food-portal-service app=online-food,track=${env.PREVIOUS_TRACK}")
                                    bat(returnStatus: true,
                                        script: "kubectl rollout status deployment/food-portal-${env.PREVIOUS_TRACK} --timeout=180s")
                                }

                                if (env.TARGET_DEPLOYMENT_EXISTED == 'true') {
                                    echo "Rolling back the candidate Deployment food-portal-${env.TARGET_TRACK}."
                                    bat(returnStatus: true,
                                        script: "kubectl rollout undo deployment/food-portal-${env.TARGET_TRACK}")
                                    bat(returnStatus: true,
                                        script: "kubectl rollout status deployment/food-portal-${env.TARGET_TRACK} --timeout=180s")
                                } else {
                                    echo "Removing the first failed candidate Deployment food-portal-${env.TARGET_TRACK}."
                                    bat(returnStatus: true,
                                        script: "kubectl delete deployment food-portal-${env.TARGET_TRACK} --ignore-not-found=true")
                                }

                                if (env.PREVIOUS_TRACK in ['blue', 'green']) {
                                    bat 'timeout /t 4 /nobreak >NUL'
                                    int rollbackSmokeStatus = bat(returnStatus: true, script: """
@echo off
curl.exe --fail --silent --show-error http://127.0.0.1:30080/ -o rollback-smoke.html
if errorlevel 1 exit /b 1
findstr /C:"MENU_READY_FOR_TRAFFIC" rollback-smoke.html >NUL
if errorlevel 1 exit /b 1
""")
                                    if (rollbackSmokeStatus == 0) {
                                        echo 'ROLLBACK VERIFIED: previous stable release responds through NodePort 30080.'
                                    } else {
                                        echo 'WARNING: previous selector was restored, but the NodePort smoke check did not pass. Check Docker Desktop Service connectivity.'
                                    }
                                }
                                throw failure
                            }
                        }
                    }
                }
            }
        }

        stage('Final Verification') {
            steps {
                withCredentials([file(credentialsId: env.KUBECONFIG_CREDENTIALS,
                                      variable: 'KUBECONFIG_FILE')]) {
                    withEnv(["KUBECONFIG=${env.KUBECONFIG_FILE}"]) {
                        bat 'kubectl get deployments -l app=online-food -o wide'
                        bat 'kubectl get pods -l app=online-food -o wide'
                        bat 'kubectl get service food-portal-service -o wide'
                        bat 'curl.exe --fail --silent --show-error http://127.0.0.1:30080/'
                    }
                }
            }
        }
    }

    post {
        always {
            bat 'docker rm -f food-portal-ci-test >NUL 2>&1 & exit /b 0'
            archiveArtifacts artifacts: '*smoke.html', allowEmptyArchive: true
        }
        success {
            echo 'CI/CD completed: candidate tests passed and NodePort is serving the selected release.'
        }
        failure {
            echo 'CI/CD failed. If a stable release existed, the public Service selector was restored to it.'
        }
    }
}
