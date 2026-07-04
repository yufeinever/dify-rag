#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_URL="${HERMES_REPO_URL:-https://github.com/NousResearch/hermes-agent.git}"
REPO_REF="${HERMES_REPO_REF:-main}"
TARGET_DIR="${ROOT_DIR}/vendor/hermes-agent"

mkdir -p "${ROOT_DIR}/vendor"

if [ -d "${TARGET_DIR}/.git" ]; then
  git -C "${TARGET_DIR}" fetch --depth 1 origin "${REPO_REF}"
  git -C "${TARGET_DIR}" checkout FETCH_HEAD
else
  git clone --depth 1 --filter=blob:none --branch "${REPO_REF}" "${REPO_URL}" "${TARGET_DIR}"
fi

if [ ! -f "${TARGET_DIR}/Dockerfile" ]; then
  echo "Hermes source was fetched, but Dockerfile was not found in ${TARGET_DIR}." >&2
  echo "Check the upstream repository layout before running docker compose build." >&2
  exit 1
fi

echo "Hermes source ready at ${TARGET_DIR}"
