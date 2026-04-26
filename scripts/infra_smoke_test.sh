#!/usr/bin/env bash
set -euo pipefail

# Verifies OSS infra profile connectivity plus basic write/read checks for:
# 1) Kafka
# 2) Postgres
# 3) MinIO

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.oss.yml}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_BIN="${SCRIPT_DIR}/compose.sh"
KAFKA_BIN="${KAFKA_BIN:-/opt/kafka/bin}"
SMOKE_ID="${SMOKE_ID:-$(date +%s)}"
KAFKA_TOPIC="smoke.cdp.${SMOKE_ID}"
KAFKA_MSG="{\"smoke_id\":\"${SMOKE_ID}\",\"kind\":\"kafka\"}"
PG_TABLE="cdp_smoke_test"
MINIO_OBJECT="smoke/${SMOKE_ID}/probe.txt"
MINIO_PAYLOAD="smoke-${SMOKE_ID}-ok"

echo "Running OSS infra smoke test with compose file: ${COMPOSE_FILE}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker command not found. Install Docker first."
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "ERROR: compose file not found: ${COMPOSE_FILE}"
  exit 1
fi

if [[ ! -x "${COMPOSE_BIN}" ]]; then
  echo "ERROR: compose wrapper not executable: ${COMPOSE_BIN}"
  exit 1
fi

RUNNING_SERVICES="$("${COMPOSE_BIN}" -f "${COMPOSE_FILE}" ps --services --status running || true)"
for svc in kafka postgres minio mc; do
  if ! grep -q "^${svc}$" <<<"${RUNNING_SERVICES}"; then
    echo "ERROR: service '${svc}' is not running."
    echo "Hint: run 'make infra-up' first."
    exit 1
  fi
done

echo "[1/3] Kafka write/read check..."
"${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T kafka bash -lc \
  "${KAFKA_BIN}/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic ${KAFKA_TOPIC}" >/dev/null
echo "${KAFKA_MSG}" | "${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T kafka bash -lc \
  "${KAFKA_BIN}/kafka-console-producer.sh --bootstrap-server kafka:9092 --topic ${KAFKA_TOPIC}" >/dev/null
KAFKA_READ="$("${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T kafka bash -lc \
  "${KAFKA_BIN}/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic ${KAFKA_TOPIC} --from-beginning --max-messages 1 --timeout-ms 10000" || true)"
if [[ "${KAFKA_READ}" != *"${SMOKE_ID}"* ]]; then
  echo "ERROR: Kafka read check failed."
  exit 1
fi

echo "[2/3] Postgres write/read check..."
"${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T postgres psql -U cdp -d cdp -v ON_ERROR_STOP=1 -c \
  "CREATE TABLE IF NOT EXISTS ${PG_TABLE} (id text primary key, created_at timestamptz default now());" >/dev/null
"${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T postgres psql -U cdp -d cdp -v ON_ERROR_STOP=1 -c \
  "INSERT INTO ${PG_TABLE}(id) VALUES ('${SMOKE_ID}') ON CONFLICT (id) DO NOTHING;" >/dev/null
PG_COUNT="$("${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T postgres psql -U cdp -d cdp -t -A -c \
  "SELECT count(*) FROM ${PG_TABLE} WHERE id='${SMOKE_ID}';" | tr -d '[:space:]')"
if [[ "${PG_COUNT}" != "1" ]]; then
  echo "ERROR: Postgres read check failed."
  exit 1
fi

echo "[3/3] MinIO write/read check..."
"${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T mc sh -lc \
  "mc alias set local http://minio:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc mb -p local/cdp-artifacts >/dev/null 2>&1 || true"
echo "${MINIO_PAYLOAD}" | "${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T mc sh -lc \
  "mc alias set local http://minio:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc pipe local/cdp-artifacts/${MINIO_OBJECT}" >/dev/null
MINIO_READ="$("${COMPOSE_BIN}" -f "${COMPOSE_FILE}" exec -T mc sh -lc \
  "mc alias set local http://minio:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc cat local/cdp-artifacts/${MINIO_OBJECT}")"
if [[ "${MINIO_READ}" != "${MINIO_PAYLOAD}" ]]; then
  echo "ERROR: MinIO read check failed."
  exit 1
fi

echo "OSS infra smoke test passed."
echo "Kafka topic: ${KAFKA_TOPIC}"
echo "Postgres row id: ${SMOKE_ID}"
echo "MinIO object: cdp-artifacts/${MINIO_OBJECT}"
