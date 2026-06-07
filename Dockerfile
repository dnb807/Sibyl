FROM python:3.10.17-alpine
WORKDIR /code

RUN apk add --no-cache gcc musl-dev linux-headers postgresql postgresql-contrib libpq-dev bash

COPY pyproject.toml pyproject.toml

RUN pip install -e .

COPY app.py database.py entrypoint.sh ./
COPY controllers/*.py ./controllers/
COPY models/*.py ./models/
COPY templates ./templates
COPY data ./data

ENTRYPOINT ["./entrypoint.sh"]
