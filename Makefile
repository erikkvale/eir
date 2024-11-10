serve-docs:
	docker run --rm -it -p 8000:8000 -v ${PWD}:/docs squidfunk/mkdocs-material

run-app:
	docker-compose --profile docs up --build

run-tests:
	docker-compose --profile default up --build -d && \
	docker-compose run fastapi-app /app/.venv/bin/pytest app/test_main.py; \
	EXIT_CODE=$$?; \
	docker-compose down; \
	exit $$EXIT_CODE