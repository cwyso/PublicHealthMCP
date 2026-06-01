FROM python:3.11-slim

COPY ./devcontainer/docker/dev-requirements.txt /tmp/pip-tmp/
RUN pip3 install --progress-bar off -r /tmp/pip-tmp/dev-requirements.txt \
    && rm -rf /tmp/pip-tmp/
