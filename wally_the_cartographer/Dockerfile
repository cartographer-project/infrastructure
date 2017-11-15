FROM golang:1.9

WORKDIR /go/src/wally
COPY main.go .
COPY cmd ./cmd/

RUN apt-get update && apt-get install -y --no-install-recommends \
		clang-format \
      ssh \
	&& rm -rf /var/lib/apt/lists/*

RUN go-wrapper download   # "go get -d -v ./..."
RUN go-wrapper install    # "go install -v ./..."

COPY config.json /go/src/wally
COPY id_rsa id_rsa.pub /root/.ssh/
COPY run_wally.sh .

RUN git config --global user.email "wally-the-cartographer@googlegroups.com"
RUN git config --global user.name "Wally B. Feed"
RUN ssh-keyscan github.com >> ~/.ssh/known_hosts

CMD ["./run_wally.sh"]
