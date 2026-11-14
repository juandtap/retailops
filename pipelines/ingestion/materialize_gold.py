"""Ejecutar únicamente GOLD v1 del bootstrap autorizado, nunca libera datos."""
import argparse
from retailops_gold.pipeline import materialize
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',required=True)
    parser.parse_args()
    materialize()
