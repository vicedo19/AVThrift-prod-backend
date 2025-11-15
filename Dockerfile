FROM python:3.13-slim

# Install uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && curl -Ls https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtualenv managed by uv
RUN uv sync --no-dev --frozen

# Copy project files
COPY . .

# Default to production settings; override in platform as needed
ENV DJANGO_SETTINGS_MODULE=config.settings.prod

# Expose web port
EXPOSE 8000

# Run the app with gunicorn in production
CMD ["uv", "run", "gunicorn", "-b", "0.0.0.0:8000", "config.wsgi:application"]
