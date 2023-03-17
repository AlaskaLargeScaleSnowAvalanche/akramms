all: build

# docker login git.akdggs.com


VERSION=230210.2
DOCKER_HOST=git.akdggs.com
DOCKER_TAG=${DOCKER_HOST}/efischer/ramms

build:
	docker build -t ramms:${VERSION} .
	docker tag ramms:${VERSION} ${DOCKER_TAG}:${VERSION}; docker push ${DOCKER_TAG}:${VERSION}

