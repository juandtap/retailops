# Código oficial archivado: fijar revisiones, checksums y bases; no usar latest.
FROM golang:1.27.3-alpine@sha256:fa3d596898d9f126af7c01d14ee7597bab3f39cccf392ef36b69fe77cd681f18 AS build
ADD --checksum=sha256:71794c2df26aad0cc99e8421c58b7aa2dd55969f979b0e7d1e931042e9fabcd6 https://codeload.github.com/minio/minio/tar.gz/7aac2a2c5b7c882e68c1ce017d8256be2feea27f /tmp/minio.tgz
RUN mkdir /server && tar -xzf /tmp/minio.tgz -C /server --strip-components=1
WORKDIR /server
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags="-s -w" -o /out/minio .
ADD --checksum=sha256:167415edd21bc29f5360943dac64272aa5cda0a39f3070b15cfeca671c43d975 https://codeload.github.com/minio/mc/tar.gz/77f82e18b5401a65958f1619df6ebb994634bd88 /tmp/mc.tgz
RUN mkdir /client && tar -xzf /tmp/mc.tgz -C /client --strip-components=1
WORKDIR /client
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags="-s -w" -o /out/mc .
FROM alpine:3.23@sha256:469c9ea410b9215eaee7976ba6c0639039b444be8e5d638f7abbada189971eb2
COPY --from=build /out/minio /out/mc /usr/local/bin/
COPY --from=build /server/LICENSE /licenses/minio-LICENSE
COPY --from=build /client/LICENSE /licenses/mc-LICENSE
# Directorio incluido en la imagen: Docker inicializa el volumen conservando propietario.
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
