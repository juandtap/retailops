"""Entrada CLI determinista; todos los archivos de trabajo se eliminan al terminar."""
from contextlib import closing
import argparse
import json
import sqlite3
import tempfile
import time
from pathlib import Path

from .core import SCHEMAS, analyze, checksum
from .report import render_report


def safe_output(source: Path, output: Path):
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents:
        raise ValueError('La salida no puede escribirse dentro de SOURCE')
    for name in ('DATA_PROFILING.json','DATA_BATCH_MANIFEST.json','DATA_PROFILING.md'):
        target=(output/name).resolve()
        if target == source or source in target.parents:
            raise ValueError('La salida resuelta apunta a SOURCE')
    return output


def main():
    parser=argparse.ArgumentParser(description='Perfilado local de Favorita; no ingiere ni libera datos.')
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--batch-size',type=int,default=10000)
    args=parser.parse_args()
    if args.batch_size<=0:
        parser.error('--batch-size debe ser positivo')
    if not args.source.is_dir():
        parser.error('--source debe ser un directorio existente')
    try:
        output=safe_output(args.source,args.output)
    except ValueError as exc:
        parser.error(str(exc))
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='retailops-profile-') as scratch:
        with closing(sqlite3.connect(Path(scratch)/'profile.sqlite3')) as conn:
            result,manifest=analyze(args.source,conn,args.batch_size,lambda message: print(message,flush=True))
        # Comprobación global: detectar también cambios después de leer cada fuente.
        for name in SCHEMAS:
            profile=result['files'][name]
            if profile['status']=='analizado' and checksum(args.source/name)!=profile['sha256']:
                raise RuntimeError(f'La fuente cambió antes de terminar: {name}')
        output.mkdir(parents=True,exist_ok=True)
        for name,data in [('DATA_PROFILING.json',result),('DATA_BATCH_MANIFEST.json',manifest)]:
            (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        (output/'DATA_PROFILING.md').write_text(render_report(result,manifest))
    print('Perfilado finalizado. Fuentes verificadas; ningún lote liberado.',flush=True)
    print(f'Tiempo de ejecución: {time.monotonic()-started:.2f} s',flush=True)
    try:
        import resource
        print(f'RSS máximo del proceso (Linux): {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss} KiB',flush=True)
    except ImportError:
        pass


if __name__=='__main__':
    main()
