# This will build the currently checked out version
#
# we use an intermediate image to build this image. it will make the resulting
# image a bit smaller.
#
# you can build the image with:
#
#    docker build -t tlbc-monitor .


FROM ubuntu:18.04 as builder
# python needs LANG
ENV LANG C.UTF-8
ENV PIP_DISABLE_PIP_VERSION_CHECK 1

RUN apt-get update \
    && apt-get install -y apt-utils python3 python3-distutils python3-dev python3-venv git \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/tlbc-monitor
RUN /opt/tlbc-monitor/bin/pip install pip==19.0.3 setuptools==41.0.0 wheel==0.33.1

COPY ./constraints.txt /tlbc-monitor/constraints.txt
COPY ./requirements.txt /tlbc-monitor/requirements.txt

WORKDIR /tlbc-monitor

# remove development dependencies from the end of the file
RUN sed -i -e '/development dependencies/q' requirements.txt

RUN /opt/tlbc-monitor/bin/pip install -c constraints.txt -r requirements.txt

COPY . /tlbc-monitor

RUN /opt/tlbc-monitor/bin/pip install -c constraints.txt .

RUN mkdir -p /opt/tlbc-monitor/config
RUN curl https://raw.githubusercontent.com/trustlines-protocol/blockchain/8acf3fb62d9e32e4c371aaf6753e603a6a30c3ac/config/trustlines-spec.json > /opt/tlbc-monitor/config/chain-spec.json



FROM ubuntu:18.04 as runner
ENV LANG C.UTF-8
RUN apt-get update \
    && apt-get install -y apt-utils python3 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /opt/tlbc-monitor/bin/tlbc-monitor /usr/local/bin/ \
    && ln -s /opt/tlbc-monitor/bin/report-validator /usr/local/bin/ \
    && mkdir -p /opt/tlbc-monitor/reports

FROM runner
COPY --from=builder /opt/tlbc-monitor /opt/tlbc-monitor
WORKDIR /opt/tlbc-monitor

ENTRYPOINT ["tlbc-monitor"]
