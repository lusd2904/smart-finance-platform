# Source from deploy/verify scripts when talking to the host Docker Engine from the
# agent sandbox (sibling containers). Do not mount docker.sock into app containers.
#
#   source scripts/docker_host.sh
#
export DOCKER_HOST="${DOCKER_HOST:-tcp://127.0.0.1:2375}"
