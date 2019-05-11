.DEFAULT_GOAL := install

install:
	pipenv install


format:
	pipenv run black .
	pipenv run isort -y

mypy:
	pipenv run mypy .

flake8:
	pipenv run flake8

static: flake8 mypy

test-format:
	pipenv run black --check .
	pipenv run isort -c

test: test-format static

pre-commit: test
