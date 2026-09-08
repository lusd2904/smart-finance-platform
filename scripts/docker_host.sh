# Source from deploy/verify scripts for host Docker access.
#
#   source scripts/docker_host.sh
#
# cursor-1 / VM: sudo docker via /var/run/docker.sock (data-root often /workspace/docker).
# Agent sandbox: no socket — falls back to DOCKER_HOST=tcp://127.0.0.1:2375.
#
# Do not mount docker.sock into application containers.

if [ -n "${DOCKER_HOST:-}" ]; then
  :
elif [ -S /var/run/docker.sock ]; then
  if ! docker info >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
      docker() {
        sudo docker "$@"
      }
    fi
  fi
else
  export DOCKER_HOST="${DOCKER_HOST:-tcp://127.0.0.1:2375}"
fi

# Slim production data bind root (cursor-1: /workspace/sfp-data, Influx ~18G on disk).
export SFP_DATA_ROOT="${SFP_DATA_ROOT:-/workspace/sfp-data}"
