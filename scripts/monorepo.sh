#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WEB_DIR="$ROOT_DIR/apps/web"
CLOUD_POM="$ROOT_DIR/services/cloud/pom.xml"
CLOUD_DIR="$ROOT_DIR/services/cloud"
DOCKER_COMPOSE="$CLOUD_DIR/script/docker/docker-compose.yml"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}

surefire_count() {
  python - "$CLOUD_DIR/ruoyi-example/ruoyi-demo/target/surefire-reports" <<'PY'
import pathlib
import sys
import xml.etree.ElementTree as ET

reports = pathlib.Path(sys.argv[1])
count = 0
if reports.exists():
    for path in reports.glob("*.xml"):
        root = ET.parse(path).getroot()
        if root.tag == "testsuite":
            count += int(root.attrib.get("tests", "0"))
        elif root.tag == "testsuites":
            for suite in root.findall("testsuite"):
                count += int(suite.attrib.get("tests", "0"))
print(count)
PY
}

case "${1:-}" in
  web:install)
    require_cmd npm
    cd "$WEB_DIR"
    npm install --registry=https://registry.npmmirror.com
    ;;
  web:dev)
    require_cmd npm
    cd "$WEB_DIR"
    npm run dev
    ;;
  web:build)
    require_cmd npm
    cd "$WEB_DIR"
    npm run build:prod
    ;;
  web:lint)
    require_cmd npm
    cd "$WEB_DIR"
    npm run lint:eslint
    ;;
  web:typecheck)
    require_cmd npx
    cd "$WEB_DIR"
    npx --no-install vue-tsc --noEmit
    ;;
  cloud:compile)
    require_cmd mvn
    mvn -f "$CLOUD_POM" clean package -DskipTests=true -Pdev
    ;;
  cloud:test)
    require_cmd mvn
    rm -rf "$CLOUD_DIR/ruoyi-example/ruoyi-demo/target/surefire-reports"
    mvn -f "$CLOUD_POM" -pl ruoyi-example/ruoyi-demo -am test -DskipTests=false -Pdev
    TEST_COUNT="$(surefire_count)"
    if [ "$TEST_COUNT" -le 0 ]; then
      echo "Maven completed, but no Surefire tests were executed." >&2
      exit 1
    fi
    echo "Surefire executed tests: $TEST_COUNT"
    ;;
  cloud:infra:up)
    require_cmd docker
    docker compose -f "$DOCKER_COMPOSE" up -d mysql nacos redis minio ruoyi-snailjob-server
    ;;
  cloud:infra:down)
    require_cmd docker
    docker compose -f "$DOCKER_COMPOSE" down
    ;;
  verify)
    "$0" web:install
    "$0" web:lint
    "$0" web:typecheck
    "$0" web:build
    "$0" cloud:compile
    "$0" cloud:test
    ;;
  *)
    echo "Usage: $0 {web:install|web:dev|web:build|web:lint|web:typecheck|cloud:compile|cloud:test|cloud:infra:up|cloud:infra:down|verify}" >&2
    exit 1
    ;;
esac
