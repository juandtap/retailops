"""RetailOps ML; límites locales de paralelismo antes de cargar NumPy/sklearn."""
import os
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
os.environ.setdefault('MLFLOW_DISABLE_AGENT_HINT','1')
