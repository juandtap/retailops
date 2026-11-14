"""Arranque local con configuración validada y enlace a loopback por defecto."""
import os
import uvicorn

def load_bind() -> tuple[str, int]:
    host = os.environ.get("ML_HOST", "127.0.0.1").strip()
    if not host:
        raise ValueError("ML_HOST no puede estar vacío")
    try:
        port = int(os.environ.get("ML_PORT", "8000"))
    except ValueError as exc:
        raise ValueError("ML_PORT debe ser un entero") from exc
    if not 1 <= port <= 65535:
        raise ValueError("ML_PORT debe estar entre 1 y 65535")
    return host, port

if __name__ == "__main__":
    host, port = load_bind()
    uvicorn.run("app.main:app", host=host, port=port)
