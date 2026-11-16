"""Validación previa de la opción que impidió arrancar el laboratorio K3s."""
import argparse
from pathlib import Path
import re


def validate_config(text):
    # Este laboratorio usa únicamente node-ip. Una opción omitida no equivale
    # a pasar una cadena vacía a K3s: el valor vacío se valida como IP inválida.
    if re.search(r'^\s*[\'\"]?node-external-ip[\'\"]?\s*:', text, re.MULTILINE):
        raise ValueError('Omitir node-external-ip en el laboratorio local; no usar un valor vacío.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        validate_config(args.path.read_text())
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
