.DEFAULT_GOAL := install

install:
	pipenv install


format:
	pipenv run black .
	pipenv run isort -y

mypy:
	pipenv run mypy .

test-format:
	pipenv run black --check .
	pipenv run isort -c

test: test-format mypy

pre-commit: test
