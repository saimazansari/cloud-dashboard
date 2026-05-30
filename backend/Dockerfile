FROM golang:1.24

WORKDIR /app

COPY . .

RUN go build -o app .

CMD ["./app"]