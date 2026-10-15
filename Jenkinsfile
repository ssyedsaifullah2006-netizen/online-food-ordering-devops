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
exit /b 0
"""
    }
}
