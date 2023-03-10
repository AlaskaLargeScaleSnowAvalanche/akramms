all: build

# docker login git.akdggs.com


DOCKER_HOST=git.akdggs.com
DOCKER_TAG=$DOCKER_HOST/efischer/ramms

build:
	docker build -t ramms .
	docker tag ramms $DOCKER_TAG; docker push $DOCKER_TAG
