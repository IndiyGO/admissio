FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home admissio
USER admissio
ENTRYPOINT ["admissio"]
CMD ["--help"]
