all: build

build:
	docker build -t ramms .
	docker tag ramms localhost:5000/ramms; docker push localhost:5000/ramms
