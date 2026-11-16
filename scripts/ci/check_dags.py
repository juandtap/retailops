"""Contrato estático de DAGs; no importa Airflow ni ejecuta tareas."""
import ast
from pathlib import Path

path = Path(__file__).resolve().parents[2] / 'infra/airflow/dags/retailops.py'
tree = ast.parse(path.read_text())
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
factory = next(n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'DAG')
args = {k.arg: k.value for k in factory.keywords}
assert ast.literal_eval(args['schedule']) is None
assert ast.literal_eval(args['catchup']) is False
assert ast.literal_eval(args['max_active_runs']) == 1
expected = {'retailops_monthly_release', 'retailops_train_candidate', 'retailops_full_pipeline', 'retailops_validate_existing'}
actual = {ast.literal_eval(n.args[0]) for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'make'}
assert actual == expected
assert not any(isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) for n in tree.body), 'Llamada ejecutable fuera de la fábrica de DAGs'
print('Cuatro DAGs manuales; sin calendario ni ejecución de tareas en validación estática')
