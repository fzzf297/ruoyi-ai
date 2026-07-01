#!/usr/bin/env sh
set -eu

# One-time setup: classic RuoYi (springboot2) + MySQL on /opt/ruoyi-classic
# Coexists with ruoyi-ai — no shared DB or ports.
# Requires: root, internet (clone + mvn + dnf), ~1.5GB RAM + swap recommended.
#
# Usage (on server):
#   sh /opt/ruoyi-ai/deploy/coexist/setup-ruoyi-classic.sh

RUOYI_AI_ROOT="${RUOYI_AI_ROOT:-/opt/ruoyi-ai}"
RUOYI_ROOT="${RUOYI_ROOT:-/opt/ruoyi-classic}"
COEXIST_DIR="$RUOYI_AI_ROOT/deploy/coexist"
BRANCH="${RUOYI_BRANCH:-springboot2}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: run as root." >&2
    exit 1
fi

echo "==> [1/8] Install JDK, Maven, Git"
if ! command -v java >/dev/null 2>&1; then
    dnf install -y git java-11-openjdk-devel maven
fi
java -version
mvn -version

echo "==> [2/8] ruoyi-ai debug mode (stop agent, free memory)"
if [ -f "$RUOYI_AI_ROOT/deploy/debug-stack.sh" ]; then
    sh "$RUOYI_AI_ROOT/deploy/debug-stack.sh" || true
fi

echo "==> [3/8] MySQL for RuoYi only"
mkdir -p "$RUOYI_ROOT"
cd "$RUOYI_ROOT"
if [ ! -f .env ]; then
    cp "$COEXIST_DIR/mysql.env.example" .env
    # random passwords
    ROOT_PW="$(openssl rand -hex 8)"
    APP_PW="$(openssl rand -hex 8)"
    sed -i "s/change-me-root/$ROOT_PW/" .env
    sed -i "s/change-me-ruoyi/$APP_PW/" .env
    echo "MySQL passwords saved in $RUOYI_ROOT/.env"
fi
# shellcheck disable=SC1091
. ./.env
cp "$COEXIST_DIR/docker-compose.mysql.yml" ./docker-compose.mysql.yml
docker compose -f docker-compose.mysql.yml up -d
echo "Waiting for MySQL..."
for i in $(seq 1 60); do
    if docker exec ruoyi-classic-mysql mysqladmin ping -h127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" --silent 2>/dev/null; then
        break
    fi
    sleep 3
done
if ! docker exec ruoyi-classic-mysql mysqladmin ping -h127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" --silent 2>/dev/null; then
    echo "Error: MySQL not ready. Check: docker logs ruoyi-classic-mysql" >&2
    exit 1
fi

echo "==> [4/8] Clone classic RuoYi ($BRANCH)"
if [ ! -d "$RUOYI_ROOT/app/.git" ]; then
    git clone -b "$BRANCH" --depth 1 https://gitee.com/y_project/RuoYi.git "$RUOYI_ROOT/app"
fi

echo "==> [5/8] Import SQL"
SQL_FILE="$(ls "$RUOYI_ROOT/app/sql/ry_"*.sql 2>/dev/null | head -1)"
if [ -z "$SQL_FILE" ]; then
    echo "Error: no ry_*.sql in app/sql/" >&2
    exit 1
fi
echo "Using $SQL_FILE"
docker exec -i ruoyi-classic-mysql mysql -h127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 "$MYSQL_DATABASE" < "$SQL_FILE"
if [ -f "$RUOYI_ROOT/app/sql/quartz.sql" ]; then
    docker exec -i ruoyi-classic-mysql mysql -h127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 "$MYSQL_DATABASE" < "$RUOYI_ROOT/app/sql/quartz.sql"
fi

echo "==> [6/8] Configure datasource + port 8080"
DRUID="$RUOYI_ROOT/app/ruoyi-admin/src/main/resources/application-druid.yml"
if [ -f "$DRUID" ]; then
    git -C "$RUOYI_ROOT/app" checkout -- ruoyi-admin/src/main/resources/application-druid.yml 2>/dev/null || true
    sed -i "s|jdbc:mysql://localhost:3306/ry?|jdbc:mysql://127.0.0.1:3306/${MYSQL_DATABASE}?|" "$DRUID"
    sed -i "s|useSSL=true|useSSL=false|" "$DRUID"
    sed -i "/master:/,/slave:/ s/username: root/username: ${MYSQL_USER}/" "$DRUID"
    sed -i "/master:/,/slave:/ s/password: password/password: ${MYSQL_PASSWORD}/" "$DRUID"
    sed -i 's/initialSize: 5/initialSize: 2/' "$DRUID"
    sed -i 's/minIdle: 10/minIdle: 2/' "$DRUID"
    sed -i 's/maxActive: 20/maxActive: 10/' "$DRUID"
fi

echo "==> [7/8] Build (may take several minutes)"
cd "$RUOYI_ROOT/app"
mvn -q -DskipTests package -pl ruoyi-admin -am

echo "==> [8/8] Start RuoYi on 127.0.0.1:8080"
pkill -f 'ruoyi-admin.jar' 2>/dev/null || true
sleep 1
nohup java -Xmx256m -Xms128m -jar "$RUOYI_ROOT/app/ruoyi-admin/target/ruoyi-admin.jar" \
    --server.port=8080 > /var/log/ruoyi-classic.log 2>&1 &

echo "Waiting for RuoYi..."
for i in $(seq 1 60); do
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/ | grep -qE '200|302'; then
        break
    fi
    sleep 3
done

cd "$RUOYI_AI_ROOT"
sh "$COEXIST_DIR/enable-coexist.sh"

echo ""
echo "=========================================="
echo "Classic RuoYi is up."
echo "  RuoYi UI:  http://$(hostname -I 2>/dev/null | awk '{print $1}')/"
echo "  Login:     admin / admin123"
echo "  ruoyi-ai:  http://$(hostname -I 2>/dev/null | awk '{print $1}')/docs"
echo "  MySQL creds: $RUOYI_ROOT/.env"
echo "  Log: /var/log/ruoyi-classic.log"
echo "=========================================="
