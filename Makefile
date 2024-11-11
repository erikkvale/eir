serve-docs:
	docker run --rm -it -p 8000:8000 -v ${PWD}:/docs squidfunk/mkdocs-material

run-app:
	trap "docker-compose --profile docs down" EXIT;
	docker-compose --profile docs up --build

down-app:
	docker-compose --profile docs down 

run-tests:
	trap "docker-compose --profile default down" EXIT;
	docker-compose --profile default up --build -d && \
	docker-compose run fastapi-app /app/.venv/bin/pytest app/test_main.py;