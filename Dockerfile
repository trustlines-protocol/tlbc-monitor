FROM ubuntu:18.04 as builder
# python needs LANG
ENV LANG C.UTF-8

RUN apt-get update \
    && apt-get install -y apt-utils python3 python3-distutils python3-dev python3-venv git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/watchdog
RUN /opt/watchdog/bin/pip install pip==18.0.0 setuptools==40.0.0

COPY ./constraints.txt /watchdog/constraints.txt
COPY ./requirements.txt /watchdog/requirements.txt

WORKDIR /watchdog

# remove development dependencies from the end of the file
RUN sed -i -e '/development dependencies/q' requirements.txt

RUN /opt/watchdog/bin/pip install -c constraints.txt -r requirements.txt

COPY . /watchdog

RUN /opt/watchdog/bin/pip install -c constraints.txt .



FROM ubuntu:18.04 as runner
ENV LANG C.UTF-8
RUN apt-get update \
    && apt-get install -y apt-utils python3 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /opt/watchdog/bin/tlbc-watchdog /usr/local/bin/

FROM runner
COPY --from=builder /opt/watchdog /opt/watchdog
WORKDIR /opt/watchdog

ENTRYPOINT ["tlbc-watchdog"]
